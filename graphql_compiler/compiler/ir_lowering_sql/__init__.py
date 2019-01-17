# Copyright 2018-present Kensho Technologies, LLC.
import six

from ... import exceptions
from ...compiler import blocks, expressions
from .constants import UNSUPPORTED_META_FIELDS
from .sql_tree import SqlNode, SqlQueryTree

##############
# Public API #
##############


def lower_ir(ir_blocks, query_metadata_table, type_equivalence_hints=None):
    """Lower the IR into a form that can be represented by a SQL query.

    Args:
        ir_blocks: list of IR blocks to lower into SQL-compatible form
        query_metadata_table: QueryMetadataTable object containing all metadata collected during
                              query processing, including location metadata (e.g. which locations
                              are folded or optional).
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        tree representation of IR blocks for recursive traversal by SQL backend.
    """
    query_path_to_location_info = {}
    for location, location_info in query_metadata_table.registered_locations:
        if location.query_path in query_path_to_location_info:
            # make sure the stored location information equals the new location information
            # for the fields the SQL backend requires.
            equivalent_location_info = query_path_to_location_info[location.query_path]
            optional_scopes_depth_equal = (location_info.optional_scopes_depth ==
                                           equivalent_location_info.optional_scopes_depth)
            parent_query_paths_equal = (
                (location_info.parent_location is None and
                 equivalent_location_info.parent_location is None) or
                (location_info.parent_location.query_path ==
                 equivalent_location_info.parent_location.query_path))
            recursive_scopes_depths_equal = (location_info.recursive_scopes_depth ==
                                             equivalent_location_info.recursive_scopes_depth)
            types_equal = location_info.type == equivalent_location_info.type
            all_equal = (optional_scopes_depth_equal and parent_query_paths_equal and
                         recursive_scopes_depths_equal and types_equal)
            if not all_equal:
                raise AssertionError(
                    u'Differing LocationInfos at query_path {} between {} and {}. Expected '
                    u'parent_location.query_path, optional_scopes_depth, recursive_scopes_depth '
                    u'and types to be equal for LocationInfos sharing the same query path.'.format(
                        location.query_path, location_info, equivalent_location_info))

        query_path_to_location_info[location.query_path] = location_info

    # Perform lowering passes over IR blocks
    construct_result = ir_blocks.pop()
    construct_result = lower_construct_result(construct_result)
    block_index_to_location = get_block_index_to_location_map(ir_blocks)
    ir_blocks = lower_unary_transformations(ir_blocks)
    ir_blocks = lower_context_field_existence(ir_blocks)
    ir_blocks = lower_optional_fields(
        ir_blocks, block_index_to_location, query_path_to_location_info)
    query_path_to_node = {}
    query_path_to_filter = {}
    query_path_to_tag_fields = {}
    skippable_blocks = (
        # MarkLocation blocks are used in the first pass over the IR blocks
        # (get_block_index_to_location_map) to create a mapping of IR block -> query path for all
        # IR blocks. They can safely be skipped during tree construction.
        blocks.MarkLocation,
        # BackTrack blocks do not affect the generated SQL tree
        blocks.Backtrack,
        # EndOptional blocks are not required, instead the LocationInfo.optional_scopes_depth
        # property is used
        blocks.EndOptional,
        # CoerceType blocks are not required, instead the LocationInfo.type property is used
        blocks.CoerceType,
    )
    tree_root = None
    for index, block in enumerate(ir_blocks):
        if isinstance(block, (blocks.Recurse, blocks.Traverse, blocks.QueryRoot)):
            location = block_index_to_location[index]
            location_info = query_metadata_table.get_location_info(location)
            query_path = location.query_path
            if tree_root is None:
                if not isinstance(block, blocks.QueryRoot):
                    raise AssertionError(
                        u'Encountered QueryRoot {} but tree root is already set to {} during '
                        u'construction of SQL query tree for IR blocks {} with query'
                        u' metadata table {}'.format(
                            block, tree_root, ir_blocks, query_metadata_table))
                tree_root = SqlNode(block=block, query_path=query_path)
                query_path_to_node[query_path] = tree_root
            else:
                parent_location = location_info.parent_location
                parent_query_path = parent_location.query_path
                parent_node = query_path_to_node[parent_query_path]
                child_node = SqlNode(block=block, query_path=query_path)
                parent_node.add_child_node(child_node)
                query_path_to_node[query_path] = child_node
        elif isinstance(block, blocks.Filter):
            for context_field in get_tag_fields(block.predicate):
                context_field_query_path = context_field.location.query_path
                query_path_to_tag_fields.setdefault(context_field_query_path, []).append(
                    context_field)
            query_path_to_filter.setdefault(query_path, []).append((block, query_path))
        elif isinstance(block, skippable_blocks):
            continue
        else:
            raise AssertionError(
                u'Encountered unexpected block {} during construction of SQL query tree for IR '
                u'blocks {} with query metadata table {} .'.format(
                    block, ir_blocks, query_metadata_table))
    location_types = {
        location.query_path: location_info.type
        for location, location_info in query_metadata_table.registered_locations
    }
    query_path_to_output_fields = assign_output_fields_to_nodes(construct_result, location_types)
    return SqlQueryTree(tree_root, query_path_to_location_info, query_path_to_filter,
                        query_path_to_output_fields, query_path_to_tag_fields)


def get_tag_fields(expression):
    """Return an iterator over the ContextFields of an expression."""
    if isinstance(expression, expressions.ContextField):
        yield expression
    if isinstance(expression, expressions.BinaryComposition):
        for context_field in get_tag_fields(expression.left):
            yield context_field
        for context_field in get_tag_fields(expression.right):
            yield context_field


def assign_output_fields_to_nodes(construct_result, location_types):
    """Assign the output fields of a ConstructResult block to their respective SqlNodes."""
    query_path_to_output_fields = {}
    for field_alias, field in six.iteritems(construct_result.fields):
        field_name = field.location.field
        if field_name in UNSUPPORTED_META_FIELDS:
            raise exceptions.GraphQLNotSupportedByBackendError(
                u'"{}" is unsupported for output.'.format(UNSUPPORTED_META_FIELDS[field_name]))
        output_query_path = field.location.query_path
        output_field_info = (field, location_types[output_query_path], False)
        output_field_mapping = query_path_to_output_fields.setdefault(output_query_path, {})
        output_field_mapping[field_alias] = output_field_info
    return query_path_to_output_fields


def get_block_index_to_location_map(ir_blocks):
    """Associate each IR block with it's corresponding location, by index."""
    block_to_location = {}
    current_block_ixs = []
    for num, ir_block in enumerate(ir_blocks):
        current_block_ixs.append(num)
        if isinstance(ir_block, blocks.MarkLocation):
            for ix in current_block_ixs:
                block_to_location[ix] = ir_block.location
            current_block_ixs = []
    return block_to_location


def lower_construct_result(construct_result):
    """Lower the ConstructResult IR Block."""
    def visitor_fn(expression):
        """Rewrite output fields in optional scopes to their if_true branch.

        The SQL backend does not require special handling to get the correct semantics for such
        output fields.
        """
        if not isinstance(expression, expressions.TernaryConditional):
            return expression
        return expression.if_true
    return construct_result.visit_and_update_expressions(visitor_fn)


def lower_unary_transformations(ir_blocks):
    """Raise errors if any unary transformation block encountered."""
    def visitor_fn(expression):
        """Raise error if current expression is a UnaryTransformation."""
        if not isinstance(expression, expressions.UnaryTransformation):
            return expression
        raise exceptions.GraphQLNotSupportedByBackendError(
            u'has_edge_degree filter operation is unsupported by SQL backend.'
        )

    new_ir_blocks = [
        block.visit_and_update_expressions(visitor_fn)
        for block in ir_blocks
    ]
    return new_ir_blocks


def lower_optional_fields(ir_blocks, block_index_to_location, query_path_to_location_info):
    """Lowering step for Filter blocks in an optional scope."""
    def rewrite_left_optional(expression):
        """Rewrite optional predicates to support the compiler's semantics.

        For comparison to a field that originates from an optional context, the field will
        be associated with a table that has been joined to the query with a LEFT JOIN.
        The spec says that a predicate applied to this field should pass if this field doesn't
        exist, which can be expressed in SQL as an (field IS NULL OR predicate) statement,
        which can be constructed with this particular rewrite.
        """
        if not isinstance(expression, expressions.BinaryComposition):
            return expression
        if not isinstance(expression.left, expressions.LocalField):
            return expression
        if not isinstance(expression.right, (expressions.Variable, expressions.ContextField)):
            return expression
        # Either the expression is true, or
        return expressions.BinaryComposition(
            u'||',
            # either the expression is true
            expression,
            # or the field referenced by the expression is NULL (doesn't exist)
            expressions.BinaryComposition(
                u'=',
                expressions.Literal(None),
                expression.left
            )
        )

    def rewrite_right_optional(expression):
        """Rewrite optional predicates to support the compiler's semantics.

        For comparison to a field that originates from an optional context, the field will
        be associated with a table that has been joined to the query with a LEFT JOIN.
        The spec says that a predicate applied to this field should pass if this field doesn't
        exist, which can be expressed in SQL as an (field IS NULL OR predicate) statement,
        which can be constructed with this particular rewrite.
        """
        if not isinstance(expression, expressions.BinaryComposition):
            return expression
        if not isinstance(expression.right, expressions.LocalField):
            return expression
        if not isinstance(expression.left, (expressions.Variable, expressions.ContextField)):
            return expression
        # Either the expression is true, or
        return expressions.BinaryComposition(
            u'||',
            # either the expression is true
            expression,
            # or the field referenced by the expression is NULL (doesn't exist)
            expressions.BinaryComposition(
                u'=',
                expressions.Literal(None),
                expression.right
            )
        )

    def rewrite_optional(expression):
        return rewrite_right_optional(rewrite_left_optional(expression))

    def visit_no_op(expression):
        """No-op visitor for blocks that are not Filter blocks or within an optional scope."""
        return expression

    new_ir_blocks = []
    for index, block in enumerate(ir_blocks):
        visitor_fn = visit_no_op
        if isinstance(block, blocks.Filter):
            query_path = block_index_to_location[index].query_path
            location_info = query_path_to_location_info[query_path]
            if location_info.optional_scopes_depth > 0:
                visitor_fn = rewrite_optional
        new_ir_blocks.append(
            block.visit_and_update_expressions(visitor_fn)
        )
    return new_ir_blocks


def lower_context_field_existence(ir_blocks):
    """Lower ContextFieldExistence blocks emerging from the use of tags in optional scopes."""
    def visitor_fn(expression):
        """Rewrite predicates wrapping ContextFieldExistence expressions.

        This applies to BinaryCompositions of the form:

            BinaryComposition(
                '||',
                BinaryComposition(
                    op,
                    ContextFieldExistence(...),
                    Literal(False),
                ),
                BinaryComposition(
                    op,
                    LocalField(...)
                    ContextField(...),
                )
            )
        """
        if not isinstance(expression, expressions.BinaryComposition):
            return expression
        if not expression.operator == u'||':
            return expression
        if not isinstance(expression.left, expressions.BinaryComposition):
            return expression
        if not isinstance(expression.left.left, expressions.ContextFieldExistence):
            return expression
        if not isinstance(expression.left.right, expressions.Literal):
            return expression
        if not expression.left.right.value == False:  # noqa: E712
            return expression
        if not isinstance(expression.right, expressions.BinaryComposition):
            return expression
        if not isinstance(expression.right.right, expressions.ContextField):
            return expression
        if not isinstance(expression.right.left, expressions.LocalField):
            return expression

        return expressions.BinaryComposition(
            u'||',
            expressions.BinaryComposition(
                u'=',
                expressions.Literal(None),
                expression.right.right
            ),
            expression.right,
        )
    new_ir_blocks = [
        block.visit_and_update_expressions(visitor_fn)
        for block in ir_blocks
    ]
    return new_ir_blocks
