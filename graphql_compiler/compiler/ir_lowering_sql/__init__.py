# Copyright 2018-present Kensho Technologies, LLC.

import six

from .sql_tree import SqlNode, SqlQueryTree
from .. import blocks
from ...compiler import expressions
from ...compiler.helpers import Location
from ..ir_lowering_sql import constants
from ..metadata import LocationInfo

##############
# Public API #
##############


def lower_ir(ir_blocks, query_metadata_table, type_equivalence_hints=None):
    """Lower the IR blocks into a form that can be represented by a SQL query.

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
    _validate_all_blocks_supported(ir_blocks, query_metadata_table)
    construct_result = _get_construct_result(ir_blocks)
    query_path_to_location_info = _map_query_path_to_location_info(query_metadata_table)
    query_path_to_output_fields = _map_query_path_to_outputs(
        construct_result, query_path_to_location_info)
    block_index_to_location = _map_block_index_to_location(ir_blocks)

    # perform lowering steps
    ir_blocks = lower_unary_transformations(ir_blocks)
    ir_blocks = lower_unsupported_metafield_expressions(ir_blocks)

    # iteratively construct SqlTree
    query_path_to_node = {}
    query_path_to_filters = {}
    tree_root = None
    for index, block in enumerate(ir_blocks):
        if isinstance(block, constants.SKIPPABLE_BLOCK_TYPES):
            continue
        location = block_index_to_location[index]
        if isinstance(block, (blocks.QueryRoot,)):
            query_path = location.query_path
            if tree_root is not None:
                raise AssertionError(
                    u'Encountered QueryRoot {} but tree root is already set to {} during '
                    u'construction of SQL query tree for IR blocks {} with query '
                    u'metadata table {}'.format(
                        block, tree_root, ir_blocks, query_metadata_table))
            tree_root = SqlNode(block=block, query_path=query_path)
            query_path_to_node[query_path] = tree_root
        elif isinstance(block, blocks.Filter):
            query_path_to_filters.setdefault(query_path, []).append(block)
        else:
            raise AssertionError(
                u'Unsupported block {} unexpectedly passed validation for IR blocks '
                u'{} with query metadata table {} .'.format(block, ir_blocks, query_metadata_table))

    return SqlQueryTree(tree_root, query_path_to_location_info, query_path_to_output_fields,
                        query_path_to_filters, query_path_to_node)


def _validate_all_blocks_supported(ir_blocks, query_metadata_table):
    """Validate that all IR blocks and ConstructResult fields passed to the backend are supported.

    Args:
        ir_blocks: List[BasicBlock], IR blocks to validate.
        query_metadata_table: QueryMetadataTable, object containing all metadata collected during
                              query processing, including location metadata (e.g. which locations
                              are folded or optional).

    Raises:
        NotImplementedError, if any block or ConstructResult field is unsupported.
    """
    if len(ir_blocks) < 3:
        raise AssertionError(
            u'Unexpectedly attempting to validate IR blocks with fewer than 3 blocks. A minimal '
            u'query is expected to have at least a QueryRoot, GlobalOperationsStart, and '
            u'ConstructResult block. The query metadata table is {}.'.format(query_metadata_table))
    construct_result = _get_construct_result(ir_blocks)
    unsupported_blocks = []
    unsupported_fields = []
    for block in ir_blocks[:-1]:
        if isinstance(block, constants.SUPPORTED_BLOCK_TYPES):
            continue
        if isinstance(block, constants.SKIPPABLE_BLOCK_TYPES):
            continue
        unsupported_blocks.append(block)

    for field_name, field in six.iteritems(construct_result.fields):
        if not isinstance(field, constants.SUPPORTED_OUTPUT_EXPRESSION_TYPES):
            unsupported_fields.append((field_name, field))
        elif field.location.field in constants.UNSUPPORTED_META_FIELDS:
            unsupported_fields.append((field_name, field))

    if len(unsupported_blocks) > 0 or len(unsupported_fields) > 0:
        raise NotImplementedError(
            u'Encountered unsupported blocks {} and unsupported fields {} during construction of '
            u'SQL query tree for IR blocks {} with query metadata table {}.'.format(
                unsupported_blocks, unsupported_fields, ir_blocks, query_metadata_table))


def _get_construct_result(ir_blocks):
    """Return the ConstructResult block from a list of IR blocks."""
    last_block = ir_blocks[-1]
    if not isinstance(last_block, blocks.ConstructResult):
        raise AssertionError(
            u'The last IR block {} for IR blocks {} was unexpectedly not '
            u'a ConstructResult block.'.format(last_block, ir_blocks))
    return last_block


def _map_query_path_to_location_info(query_metadata_table):
    """Create a map from each query path to a LocationInfo at that path.

    Args:
        query_metadata_table: QueryMetadataTable, object containing all metadata collected during
                              query processing, including location metadata (e.g. which locations
                              are folded or optional).

    Returns:
        Dict[Tuple[str], LocationInfo], dictionary mapping query path to LocationInfo at that path.
    """
    query_path_to_location_info = {}
    for location, location_info in query_metadata_table.registered_locations:
        if not isinstance(location, Location):
            continue
        if location.query_path in query_path_to_location_info:
            # make sure the stored location information equals the new location information
            # for the fields the SQL backend requires.
            equivalent_location_info = query_path_to_location_info[location.query_path]
            if not _location_infos_equal(location_info, equivalent_location_info):
                raise AssertionError(
                    u'Differing LocationInfos at query_path {} between {} and {}. Expected '
                    u'parent_location.query_path, optional_scopes_depth, recursive_scopes_depth '
                    u'and types to be equal for LocationInfos sharing the same query path.'.format(
                        location.query_path, location_info, equivalent_location_info))

        query_path_to_location_info[location.query_path] = location_info
    return query_path_to_location_info


def _location_infos_equal(left, right):
    """Return True if LocationInfo objects are equivalent for the SQL backend, False otherwise.

    LocationInfo objects are considered equal for the SQL backend iff the optional scopes depth,
    recursive scopes depth, types and parent query paths are equal.

    Args:
        left: LocationInfo, left location info object to compare.
        right: LocationInfo, right location info object to compare.

    Returns:
        bool, True if LocationInfo objects equivalent, False otherwise.
    """
    if not isinstance(left, LocationInfo) or not isinstance(right, LocationInfo):
        raise AssertionError(
            u'Unsupported LocationInfo comparison between types {} and {} '
            u'with values {}, {}'.format(type(left), type(right), left, right))
    optional_scopes_depth_equal = (left.optional_scopes_depth == right.optional_scopes_depth)

    parent_query_paths_equal = (
        (left.parent_location is None and right.parent_location is None) or
        (left.parent_location.query_path == right.parent_location.query_path))

    recursive_scopes_depths_equal = (left.recursive_scopes_depth == right.recursive_scopes_depth)

    types_equal = left.type == right.type

    return all([
        optional_scopes_depth_equal,
        parent_query_paths_equal,
        recursive_scopes_depths_equal,
        types_equal,
    ])


def _map_query_path_to_outputs(construct_result, query_path_to_location_info):
    """Assign the output fields of a ConstructResult block to their respective query_path."""
    query_path_to_output_fields = {}
    for output_name, field in six.iteritems(construct_result.fields):
        field_name = field.location.field
        output_query_path = field.location.query_path
        output_field_info = constants.SqlOutput(
            field_name=field_name,
            output_name=output_name,
            graphql_type=query_path_to_location_info[output_query_path].type)
        output_field_mapping = query_path_to_output_fields.setdefault(output_query_path, [])
        output_field_mapping.append(output_field_info)
    return query_path_to_output_fields


def _map_block_index_to_location(ir_blocks):
    """Associate each IR block with its corresponding location, by index."""
    block_index_to_location = {}
    # MarkLocation blocks occur after the blocks related to that location.
    # The core approach here is to buffer blocks until their MarkLocation is encountered
    # after which all buffered blocks can be associated with the encountered MarkLocation.location.
    current_block_ixs = []
    for num, ir_block in enumerate(ir_blocks):
        if isinstance(ir_block, blocks.GlobalOperationsStart):
            if len(current_block_ixs) > 0:
                unassociated_blocks = [ir_blocks[ix] for ix in current_block_ixs]
                raise AssertionError(
                    u'Unexpectedly encountered global operations before mapping blocks '
                    u'{} to their respective locations.'.format(unassociated_blocks))
            break
        current_block_ixs.append(num)
        if isinstance(ir_block, blocks.MarkLocation):
            for ix in current_block_ixs:
                block_index_to_location[ix] = ir_block.location
            current_block_ixs = []
    return block_index_to_location


def lower_unary_transformations(ir_blocks):
    """Raise exception if any unary transformation block encountered."""
    def visitor_fn(expression):
        """Raise error if current expression is a UnaryTransformation."""
        if not isinstance(expression, expressions.UnaryTransformation):
            return expression
        raise NotImplementedError(
            u'UnaryTransformation expression "{}" encountered with IR blocks {} is unsupported by '
            u'the SQL backend.'.format(expression, ir_blocks)
        )

    new_ir_blocks = [
        block.visit_and_update_expressions(visitor_fn)
        for block in ir_blocks
    ]
    return new_ir_blocks


def lower_unsupported_metafield_expressions(ir_blocks):
    """Raise exception if an unsupported metafield is encountered in any LocalField expression."""
    def visitor_fn(expression):
        """Visitor function raising exception for any unsupported metafield."""
        if not isinstance(expression, expressions.LocalField):
            return expression
        if expression.field_name not in constants.UNSUPPORTED_META_FIELDS:
            return expression
        raise NotImplementedError(
            u'Encountered unsupported metafield {} in LocalField {} during construction of '
            u'SQL query tree for IR blocks {}.'.format(
                constants.UNSUPPORTED_META_FIELDS[expression.field_name], expression, ir_blocks))

    new_ir_blocks = [
        block.visit_and_update_expressions(visitor_fn)
        for block in ir_blocks
    ]
    return new_ir_blocks
