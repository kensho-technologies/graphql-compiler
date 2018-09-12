# Copyright 2018-present Kensho Technologies, LLC.
"""Recursively converts a SqlNode tree to an executable SQLAlchemy query.

The complexity here comes from @recurse directives (Recurse blocks). To match the semantics of
the GraphQL compiler, recursive common table expressions (CTEs) are required. SQL backends are good
at pushing predicates down into subqueries and CTEs, however this does not generally extend to
recursive CTEs. This means that it is very easy to write a recursive CTE that will scan an entire
table, even if all but a few starting points of that recursion are eventually discarded later.


Using the query

{
    Animal {
        name @output(out_name: "animal_name")
             @filter(op_name: "in_collection", value: ["$names"])
        out_Animal_LivesIn @optional {
            name @output(out_name: "location_name")
        }
        out_Animal_ParentOf @recurse(depth: 2) {
            name @output(out_name: "animal_or_descendant_name")
        }
    }
}
as an example, this is addressed with the following algorithm:

1. Recursively collapse the query, treating the recursive component as a black box. For this
example, this results in the rough SQL:

SELECT
    animal.name AS animal_name,
    location.name AS location_name
FROM
    animal
LEFT JOIN animal_livesin ON animal_livesin.animal_id = animal.animal_id
LEFT JOIN location ON location.location_id = animal_livesin.livesin_id
WHERE
    animal.name IN :names

2. Wrap this query as a CTE, and include any link columns in the output. A link column is the column
that the recursive clause will later be attached to.

WITH base_cte AS ( -- the actual name of the CTE is an anonymous table name
    SELECT
        animal.name as animal_name,
        location.name as location_name
        animal.animal_id as link_column -- the actual name of the column an anonymous column name
    FROM
        animal
    LEFT JOIN animal_livesin ON animal_livesin.animal_id = animal.animal_id
    LEFT JOIN location ON location.location_id = animal_livesin.livesin_id
    WHERE
        animal.name IN :names
)

3. Construct the recursive clause. Here we only recurse on the columns necessary to JOIN before
and after the recursion, output columns are not carried along. The recursion is joined to the
CTE of the base query, ensuring that the recursion only starts at the required starting points,
no more.

Also worth noting with the recursive clause is the __depth_internal_name, which keeps track of
recursion depth per the compiler's semantics, and __path_internal_name, which is used for cycle
detection. Simply using UNION here to join the anchor query to the recursive query is insufficient
to prevent cycles, because the depth column is unique to each row, even in a cycle.


WITH RECURSIVE recursive_cte AS (
    -- anchor query
    SELECT DISTINCT
        animal_parentof.animal_id AS animal_id,
        animal_parentof.parentof_id AS parentof_id,
        0 AS __depth_internal_name,
        CAST(animal_2.animal_id AS VARCHAR) || ',' AS __path_internal_name,
        0 AS __cycle_detected_internal_name
    FROM
        animal_parentof
        JOIN base_cte ON base_cte.link_column == animal_parentof.animal_id
    UNION ALL
    -- recursive query
    SELECT
        recursive_cte.animal_id,
        animal_parentof.parentof_id,
        -- increment the depth
        recursive_cte.__depth_internal_name + 1 AS __depth_internal_name,
        -- append the next element to the path
        recursive_cte.__path_internal_name || CAST(animal_parentof.parentof_id AS VARCHAR) ||
            ',' AS __path_internal_name,
        -- check if a cycle is already present, or if this creates a cycle
        CASE WHEN (recursive_cte.__cycle_detected_internal_name = 1) THEN 1
             WHEN (recursive_cte.__path_internal_name LIKE '%' ||
                   CAST(animal_parentof.parentof_id AS VARCHAR) || '%') THEN 1
             ELSE 0 END as __cycle_detected_internal_name
    FROM
        animal_parentof
        JOIN recursive_cte ON recursive_cte.parentof_id = animal_parentof.animal_id
    WHERE
        recursive_cte.__depth_internal_name < :depth -- depth from recurse directive
        -- only consider recursing if this is a new path
        AND recursive_cte.__cycle_detected_internal_name = 0
)

4. JOIN the recursive clause to the recursive table (here animal_parentof) to create output columns,
and join back to base cte to carry along tag columns.
WITH recursive_cte_outputs AS (
    SELECT
        animal.name AS animal_or_descendant_name,
        anon_3.animal_id AS recursive_link_column -- actually an aliased column
    FROM
        recursive_cte
        JOIN animal on animal.animal_id = recursive_cte.parentof_id
        JOIN base_cte ON recursive_cte.animal_id = base_cte.link_column
)

5. Create the final query

SELECT
    base_cte.animal_name,
    base_cte.location_name,
    recursive_cte_outputs.animal_or_descendant_name
FROM
    base_cte
JOIN
    recursive_cte_outputs ON base_cte.link_column = recursive_cte_outputs.recursive_link_column
"""
from collections import defaultdict, namedtuple

import six
from sqlalchemy import Column, String, and_, bindparam, case, cast, literal_column, select
from sqlalchemy.sql import expression as sql_expressions
from sqlalchemy.sql.elements import BindParameter

from graphql_compiler import exceptions
from graphql_compiler.compiler import blocks, expressions
from graphql_compiler.compiler.helpers import INBOUND_EDGE_DIRECTION
from graphql_compiler.compiler.ir_lowering_sql import constants


# The compilation context holds state that changes during compilation as the tree is traversed
CompilationContext = namedtuple('CompilationContext', [
    'query_path_to_selectable',
    'query_path_to_from_clause',
    'query_path_to_location_info',
    'query_path_to_recursion_columns',
    'query_path_to_filter',
    'query_path_to_output_fields',
    'query_path_field_renames',
    'query_path_to_tag_fields',
    'compiler_metadata',
])

ManyToManyJoin = namedtuple('JunctionJoinExpression', [
    'join_to_junction_expression',
    'junction_table',
    'join_from_junction_expression'
])


def emit_code_from_ir(sql_query_tree, compiler_metadata):
    """Return a SQLAlchemy query from a tree of  SqlNodes."""
    context = CompilationContext(
        query_path_to_selectable={},
        query_path_to_from_clause={},
        query_path_to_recursion_columns={},
        query_path_field_renames=defaultdict(dict),
        query_path_to_tag_fields=sql_query_tree.query_path_to_tag_fields,
        query_path_to_location_info=sql_query_tree.query_path_to_location_info,
        query_path_to_filter=sql_query_tree.query_path_to_filter,
        query_path_to_output_fields=sql_query_tree.query_path_to_output_fields,
        compiler_metadata=compiler_metadata,
    )
    return _query_tree_to_query(sql_query_tree.root, context, None, None)


def _query_tree_to_query(node, context, recursion_link_column, outer_cte):
    """Recursive entry point for converting a SqlNode tree to an executable SQLAlchemy query."""
    # Collapse query tree, ignoring recursive nodes
    visited_nodes = _flatten_and_join_nonrecursive_nodes(node, context)
    # Create the recursive element (only occurs on a recursive call of this function)
    recursion_out_column = _create_recursive_clause(node, context, recursion_link_column, outer_cte)
    # Materialize query as a CTE.
    cte = _create_query(node, is_final_query=False, context=context).cte()
    # Output fields from individual tables become output fields from the CTE
    _update_context_paths(node, visited_nodes, cte, context)
    # collapse and return recursive node trees, passing the CTE to the recursive element
    _flatten_and_join_recursive_nodes(node, cte, context)
    if isinstance(node.block, blocks.QueryRoot):
        # filters have already been applied within the CTE, no need to reapply
        return _create_query(node, is_final_query=True, context=context)
    return recursion_out_column


def _flatten_and_join_recursive_nodes(node, cte, context):
    """Join recursive child nodes to parent, flattening child's references."""
    for recursive_node in node.recursions:
        # retrieve the column that will be attached to the recursive element
        recursion_source_column, _ = context.query_path_to_recursion_columns[
            recursive_node.query_path]
        recursion_sink_column = _query_tree_to_query(
            recursive_node, context, recursion_link_column=recursion_source_column, outer_cte=cte
        )
        _flatten_output_fields(node, recursive_node, context)
        join_expression = _get_recursive_node_join_expression(
            node, recursive_node, recursion_source_column, recursion_sink_column, context)
        _join_nodes(node, recursive_node, join_expression, context)


def _update_context_paths(node, visited_nodes, cte, context):
    """Update the visited node's paths to point to the CTE."""
    # this should be where the tag fields get updated, so that they continue to propagate
    context.query_path_to_from_clause[node.query_path] = cte
    for visited_node in visited_nodes:
        context.query_path_to_selectable[visited_node.query_path] = cte


def _flatten_and_join_nonrecursive_nodes(node, context):
    """Join non-recursive child nodes to parent, flattening child's references."""
    # recursively collapse the children's trees
    visited_nodes = [node]
    for child_node in node.children_nodes:
        nodes_visited_from_child = _flatten_and_join_nonrecursive_nodes(child_node, context)
        visited_nodes.extend(nodes_visited_from_child)
    # create the current node's table
    _create_and_reference_table(node, context)
    # ensure that columns required to link recursion are present
    _create_links_for_recursions(node, context)
    for child_node in node.children_nodes:
        _flatten_node(node, child_node, context)
        join_expression = _get_node_join_expression(node, child_node, context)
        _join_nodes(node, child_node, join_expression, context)
    return visited_nodes


def _get_node_selectable(node, context):
    """Return the selectable (Table, CTE) of a node."""
    query_path = node.query_path
    if query_path not in context.query_path_to_selectable:
        raise AssertionError(u'Unable to find selectable for query path {}'.format(query_path))
    selectable = context.query_path_to_selectable[query_path]
    return selectable


def _get_node_from_clause(node, context):
    """Return the from clause of a node."""
    query_path = node.query_path
    if query_path not in context.query_path_to_from_clause:
        raise AssertionError(u'Unable to find from clause for query path {}'.format(query_path))
    from_clause = context.query_path_to_from_clause[query_path]
    return from_clause


def _get_schema_type_name(node, context):
    """Return the GraphQL type name of a node."""
    query_path = node.query_path
    if query_path not in context.query_path_to_location_info:
        raise AssertionError(u'Unable to find type name for query path {}'.format(query_path))
    location_info = context.query_path_to_location_info[query_path]
    return location_info.type.name


def _get_block_direction(block):
    if not isinstance(block, (blocks.Traverse, blocks.Recurse)):
        raise AssertionError(u'Attempting to get direction of block of type "{}"'.format(
            type(block)))
    return block.direction


def _get_block_edge_name(block):
    if not isinstance(block, (blocks.Traverse, blocks.Recurse)):
        raise AssertionError(u'Attempting to get edge name of block of type "{}"'.format(
            type(block)))
    return block.edge_name


def _create_recursive_clause(node, context, out_link_column, outer_cte):
    """Create a recursive clause for a Recurse block."""
    if not isinstance(node.block, blocks.Recurse):
        return None
    if out_link_column is None or outer_cte is None:
        raise AssertionError()
    selectable = _get_node_selectable(node, context)
    join_expression = _get_node_join_expression(node, node, context)
    if isinstance(join_expression, sql_expressions.BinaryExpression):
        left_column_name = join_expression.left.name
        right_column_name = join_expression.right.name
        base_column_name = right_column_name
        schema_type = _get_schema_type_name(node, context)
        recursive_table = context.compiler_metadata.get_table(schema_type).alias()
    elif isinstance(join_expression, ManyToManyJoin):
        left_column_name = join_expression.join_from_junction_expression.left.name
        right_column_name = join_expression.join_to_junction_expression.right.name
        base_column_name = join_expression.join_to_junction_expression.left.name
        recursive_table = join_expression.junction_table
    else:
        raise AssertionError(
            u'Unknown JOIN expression of type "{}" encountered for recursive clause.'.format(
                type(join_expression)))
    base_column = _get_column(selectable, base_column_name)
    if _get_block_direction(node.block) == INBOUND_EDGE_DIRECTION:
        left_column_name, right_column_name = right_column_name, left_column_name

    parent_cte_column = _get_column(outer_cte, out_link_column.name)
    anchor_query = (
        select(
            [
                base_column.label(left_column_name),
                base_column.label(right_column_name),
                literal_column('0').label(constants.DEPTH_INTERNAL_NAME),
                cast(base_column, String()).concat(',').label(constants.PATH_INTERNAL_NAME),
                literal_column('0').label(constants.CYCLE_DETECTED_INTERNAL_NAME)
            ],
            distinct=True)
        .select_from(
            selectable.join(
                outer_cte,
                base_column == parent_cte_column
            )
        )
    )
    recursive_cte = anchor_query.cte(recursive=True)
    recursive_query = (
        select(
            [
                _get_column(recursive_table, left_column_name),
                _get_column(recursive_cte, right_column_name),
                ((_get_column(recursive_cte, constants.DEPTH_INTERNAL_NAME) + 1)
                 .label(constants.DEPTH_INTERNAL_NAME)),
                (_get_column(recursive_cte, constants.PATH_INTERNAL_NAME)
                 .concat(cast(_get_column(recursive_table, left_column_name), String()))
                 .concat(',')
                 .label(constants.PATH_INTERNAL_NAME)),
                case(
                    [((_get_column(recursive_cte, constants.CYCLE_DETECTED_INTERNAL_NAME) == 1), 1),
                     (_get_column(recursive_cte, constants.PATH_INTERNAL_NAME).contains(
                            cast(_get_column(recursive_table, left_column_name), String())), 1)],
                    else_=0
                )
            ]
        )
        .select_from(
            recursive_table.join(
                recursive_cte,
                _get_column(recursive_table, right_column_name) ==
                _get_column(recursive_cte, left_column_name)
            )
        ).where(and_(
            _get_column(recursive_cte, constants.DEPTH_INTERNAL_NAME) < node.block.depth,
            (_get_column(recursive_cte, constants.CYCLE_DETECTED_INTERNAL_NAME) == 0)
        ))
    )
    recursion_combinator = context.compiler_metadata.db_backend.recursion_combinator
    if not hasattr(recursive_cte, recursion_combinator):
        raise AssertionError(
            'Cannot combine anchor and recursive clauses with operation "{}"'.format(
                recursion_combinator))
    recursive_query = getattr(recursive_cte, recursion_combinator)(recursive_query)
    from_clause = _get_node_from_clause(node, context)
    from_clause = from_clause.join(
        recursive_query,
        _get_column(selectable, base_column_name) == _get_column(recursive_query, left_column_name)
    )
    from_clause = from_clause.join(
        outer_cte, _get_column(recursive_query, right_column_name) == parent_cte_column
    )
    context.query_path_to_from_clause[node.query_path] = from_clause
    out_link_column = _get_column(recursive_query, right_column_name).label(None)
    (in_col, _) = context.query_path_to_recursion_columns[node.query_path]
    context.query_path_to_recursion_columns[node.query_path] = (in_col, out_link_column)
    return out_link_column


def _create_and_reference_table(node, context):
    """Create an aliased table for a node, and update the relevant context."""
    schema_type = _get_schema_type_name(node, context)
    table = context.compiler_metadata.get_table(schema_type).alias()
    context.query_path_to_from_clause[node.query_path] = table
    context.query_path_to_selectable[node.query_path] = table
    return table


def _flatten_node(node, child_node, context):
    """Flatten a child node's references onto it's parent."""
    _flatten_output_fields(node, child_node, context)
    context.query_path_to_filter[node.query_path].extend(
        context.query_path_to_filter[child_node.query_path]
    )
    del context.query_path_to_filter[child_node.query_path]
    node.recursions.extend(child_node.recursions)


def _flatten_output_fields(parent_node, child_node, context):
    """Flatten child node output fields onto parent node after join operation has been performed."""
    child_output_fields = context.query_path_to_output_fields[child_node.query_path]
    parent_output_fields = context.query_path_to_output_fields[parent_node.query_path]
    for field_alias, (field, field_type, is_renamed) in six.iteritems(child_output_fields):
        parent_output_fields[field_alias] = (field, field_type, is_renamed)
    context.query_path_to_tag_fields[parent_node.query_path].extend(
        context.query_path_to_tag_fields[child_node.query_path])
    del context.query_path_to_output_fields[child_node.query_path]


def _join_nodes(parent_node, child_node, join_expression, context):
    """Join two nodes and update compilation context."""
    location_info = context.query_path_to_location_info[child_node.query_path]
    is_optional = location_info.optional_scopes_depth > 0
    parent_from_clause = _get_node_from_clause(parent_node, context)
    child_from_clause = _get_node_from_clause(child_node, context)
    if is_optional:
        # use LEFT JOINs
        if isinstance(join_expression, ManyToManyJoin):
            parent_from_clause = parent_from_clause.outerjoin(
                join_expression.junction_table,
                onclause=join_expression.join_to_junction_expression)
            parent_from_clause = parent_from_clause.outerjoin(
                child_from_clause, onclause=join_expression.join_from_junction_expression)
        else:
            parent_from_clause = parent_from_clause.outerjoin(
                child_from_clause, onclause=join_expression)
    else:
        # use INNER JOINs
        if isinstance(join_expression, ManyToManyJoin):
            parent_from_clause = parent_from_clause.join(
                join_expression.junction_table,
                onclause=join_expression.join_to_junction_expression)
            parent_from_clause = parent_from_clause.join(
                child_from_clause, onclause=join_expression.join_from_junction_expression)
        else:
            parent_from_clause = parent_from_clause.join(
                child_from_clause, onclause=join_expression)
    context.query_path_to_from_clause[parent_node.query_path] = parent_from_clause
    del context.query_path_to_from_clause[child_node.query_path]


def _create_link_for_recursion(node, recursion_node, context):
    """Ensure that the column necessary to link to a recursion is present in the CTE columns."""
    selectable = _get_node_selectable(node, context)
    # pre-populate the recursive nodes selectable for the purpose of computing the join
    _create_and_reference_table(recursion_node, context)
    join_expression = _get_node_join_expression(recursion_node.parent, recursion_node, context)
    # the left side of the expression is the column from the node that is later needed to join to
    recursion_in_col = None
    if isinstance(join_expression, ManyToManyJoin):
        recursion_in_col = _get_column(
            selectable, join_expression.join_to_junction_expression.left.name)
    elif isinstance(join_expression, sql_expressions.BinaryExpression):
        recursion_in_col = _get_column(selectable, join_expression.right.name)
    else:
        raise AssertionError(
            u'Unknown JOIN expression of type "{}" encountered for recursive link.'.format(
                type(join_expression)))
    return recursion_in_col


def _create_links_for_recursions(node, context):
    """Ensure that the columns to link the CTE to the recursive clause are in the CTE's outputs."""
    for recursive_node in node.recursions:
        link_column = _create_link_for_recursion(node, recursive_node, context)
        context.query_path_to_recursion_columns[recursive_node.query_path] = (link_column, None)


def _get_output_columns(node, is_final_query, context):
    """Convert the output fields of a SqlNode to aliased Column objects."""
    output_fields = context.query_path_to_output_fields[node.query_path]
    columns = []
    for field_alias, (field, field_type, is_renamed) in six.iteritems(output_fields):
        selectable = context.query_path_to_selectable[field.location.query_path]
        if is_renamed:
            column = _get_column(selectable, field_alias)
        else:
            field_name = field.location.field
            column = _try_get_column(selectable, field_name)
            if column is None:
                raise exceptions.GraphQLCompilationError(
                    u'Field "{}" was not found on table "{}"'.format(
                        field_name, selectable.original))
            column = column.label(field_alias)
            output_fields[field_alias] = (field, field_type, True)
            context.query_path_field_renames[field.location.query_path][field_name] = field_alias
        columns.append(column)
    # include tags only when we are not outputting the final result
    if not is_final_query:
        for tag_field in context.query_path_to_tag_fields[node.query_path]:
            selectable = context.query_path_to_selectable[tag_field.location.query_path]
            field_name = tag_field.location.field
            column = _get_column(selectable, field_name).label(None)
            columns.append(column)
            field_renames = context.query_path_field_renames[tag_field.location.query_path]
            field_renames[field_name] = column.name
    return columns


def _create_query(node, is_final_query, context):
    """Create a query from a SqlNode.

    If this query is the final query, filters do not need to be applied, and intermediate link
    columns and tag columns do not need to be included in output.
    """
    # filters are computed before output columns, so that tag columns can be resolved before any
    # renames occur for columns involved in output
    filter_clauses = []
    if not is_final_query:
        filter_clauses = [
            _convert_filter_to_sql(filter_block, filter_query_path, context)
            for filter_block, filter_query_path in context.query_path_to_filter[node.query_path]
        ]

    columns = _get_output_columns(node, is_final_query, context)
    if not is_final_query:
        # for every recursion that is a child of this node, include the link column to the child
        # recursion in this node's query's outputs
        for recursion in node.recursions:
            in_col, _ = context.query_path_to_recursion_columns[recursion.query_path]
            columns.append(in_col)
    # If this node is completing a recursion, include the outward column in this node's outputs
    if node.query_path in context.query_path_to_recursion_columns:
        _, out_col = context.query_path_to_recursion_columns[node.query_path]
        columns.append(out_col)

    from_clause = _get_node_from_clause(node, context)
    query = select(columns).select_from(from_clause)
    if is_final_query:
        return query
    return query.where(and_(*filter_clauses))


def _convert_filter_to_sql(filter_block, filter_query_path, context):
    """Return the SQLAlchemy expression for a Filter predicate."""
    filter_location_info = context.query_path_to_location_info[filter_query_path]
    filter_selectable = context.query_path_to_selectable[filter_query_path]
    expression = filter_block.predicate
    return _expression_to_sql(expression, filter_selectable, filter_location_info, context)


def _expression_to_sql(expression, selectable, location_info, context):
    """Recursively convert a compiler predicate to it's SQLAlchemy expression representation."""
    if isinstance(expression, expressions.LocalField):
        column_name = expression.field_name
        column = _get_column(selectable, column_name)
        return column
    if isinstance(expression, expressions.Variable):
        variable_name = expression.variable_name
        return bindparam(variable_name)
    if isinstance(expression, expressions.Literal):
        return expression.value
    if isinstance(expression, expressions.ContextField):
        tag_field_name = expression.location.field
        tag_query_path = expression.location.query_path
        tag_column_name = tag_field_name
        if tag_query_path in context.query_path_field_renames:
            if tag_field_name in context.query_path_field_renames[tag_query_path]:
                tag_column_name = context.query_path_field_renames[tag_query_path][tag_field_name]
        tag_selectable = context.query_path_to_selectable[tag_query_path]
        tag_column = _get_column(tag_selectable, tag_column_name)
        return tag_column
    if isinstance(expression, expressions.BinaryComposition):
        if expression.operator in constants.UNSUPPORTED_OPERATOR_NAMES:
            raise exceptions.GraphQLNotSupportedByBackendError(
                u'Filter operation "{}" is not supported by the SQL backend.'.format(
                    expression.operator))
        sql_operator = constants.OPERATORS[expression.operator]
        left = _expression_to_sql(expression.left, selectable, location_info, context)
        right = _expression_to_sql(expression.right, selectable, location_info, context)
        if sql_operator.cardinality == constants.Cardinality.UNARY:
            # ensure the operator is grabbed from the Column object
            if not isinstance(left, Column) and isinstance(right, Column):
                left, right = right, left
            clause = getattr(left, sql_operator.name)(right)
            return clause
        if sql_operator.cardinality == constants.Cardinality.BINARY:
            clause = getattr(sql_expressions, sql_operator.name)(left, right)
            return clause
        if sql_operator.cardinality == constants.Cardinality.LIST_VALUED:
            if isinstance(left, BindParameter) and isinstance(right, Column):
                left, right = right, left
            if not isinstance(right, BindParameter):
                raise AssertionError(
                    u'List valued operator expects column as left side of expression')
            if not isinstance(left, Column):
                raise AssertionError(
                    u'List valued operator expects bind parameter as right side of expression')
            # ensure that SQLAlchemy treats the left bind parameter as list valued
            right.expanding = True
            clause = getattr(left, sql_operator.name)(right)
            return clause
        raise AssertionError(u'Unknown operator cardinality {}'.format(sql_operator.cardinality))
    raise AssertionError(u'Unknown expression "{}" cannot be converted to SQL expression'.format(
        type(expression)))


def _get_column(selectable, column_name):
    column = _try_get_column(selectable, column_name)
    if column is None:
        raise AssertionError(
            u'Column "{}" not found in selectable "{}". Columns present are {}'.format(
                column_name, selectable, [col.name for col in selectable.c]))
    return column


def _try_get_column(selectable, column_name):
    if not hasattr(selectable, 'c'):
        raise AssertionError(u'Selectable "{}" does not have a column collection.'.format(
            selectable))
    if column_name not in selectable.c:
        return None
    return selectable.c[column_name]


def _get_recursive_node_join_expression(node, recursive_node, in_column, out_column, context):
    """Determine the join expression to join an outer table to a recursive clause.

    In this case there is a constructed join between the two nodes with an aliased column that
    breaks the naming convention expected by _get_node_join_expression.
    """
    selectable = _get_node_selectable(node, context)
    recursive_selectable = _get_node_selectable(recursive_node, context)
    return _get_selectable_join_expression(
        selectable, in_column.name, recursive_selectable, out_column.name)


def _get_node_join_expression(outer_node, inner_node, context):
    """Determine the join expression to join the outer node to the inner node.

    For both cases below it is assumed that columns used for an edge correspond to that edge's
    components, eg edge Animal_Eats is expected to be comprised of columns animal_id and eats_id.

    The process to determine this join expression is as follows:
    1. Attempt to resolve the join expression as a many-many edge. To do so, one the following must
       hold:
       - There is a table of the correct edge name, eg. for an edge out_Animal_FriendsWith,
         there is a table of name animal_friendswith.
       - there is a table of the correct edge name, with a type suffix. eg. for an edge
         out_Animal_Eats of union type [FoodOrSpecies] that is coerced to Food in the given
         context, there is a table of name animal_eats_food
       - If both of these tables exist, a GraphQLCompilationError is raised.
    2. If there are no results from (1), look for a direct join expression between the two tables.
    """
    # Attempt to resolve via case (1)
    join_expression = _try_get_many_to_many_join_expression(outer_node, inner_node, context)
    if join_expression is not None:
        return join_expression
    # No results, attempt to resolve via case (2)
    return _get_direct_join_expression(outer_node, inner_node, context)


def _get_direct_join_expression(outer_node, inner_node, context):
    """Get a direct join expression between the selectables of two nodes."""
    direction = _get_block_direction(inner_node.block)
    edge_name = _get_block_edge_name(inner_node.block)
    outer_selectable = _get_node_selectable(outer_node, context)
    inner_selectable = _get_node_selectable(inner_node, context)
    outer_column_name, inner_column_name = _get_column_names_for_edge(edge_name)
    if direction == INBOUND_EDGE_DIRECTION:
        # Flip so that the inner -> outer relationship is considered first
        # This is important for tables with foreign keys onto themselves
        outer_selectable, inner_selectable = inner_selectable, outer_selectable
    # The natural join direction is Table A -FK> Table B, with Table A holding the foreign key
    natural_join_expression = _get_selectable_join_expression(
        outer_selectable, outer_column_name, inner_selectable, inner_column_name)
    if natural_join_expression is not None:
        return natural_join_expression
    # The inverse join direction is Table A <FK- Table B, with table B holding the foreign key
    inverse_join_expression = _get_selectable_join_expression(
        inner_selectable, outer_column_name, outer_selectable, inner_column_name)
    if inverse_join_expression is not None:
        return inverse_join_expression
    raise exceptions.GraphQLCompilationError(
        (u'Table "{}" is expected to have foreign key "{}" to column "{}" of table "{}" or '
         u'table "{}" is expected to have foreign key "{}" to column "{}" of table "{}".').format(
            outer_selectable.original, outer_column_name, inner_column_name,
            inner_selectable.original, inner_selectable.original, outer_column_name,
            inner_column_name, outer_selectable.original
        )
    )


def _try_get_many_to_many_join_expression(outer_node, inner_node, context):
    """Attempt to resolve a join condition that uses an underlying many-many junction table."""
    outer_selectable = _get_node_selectable(outer_node, context)
    inner_selectable = _get_node_selectable(inner_node, context)
    edge_name = _get_block_edge_name(inner_node.block)
    outer_column_name, inner_column_name = _get_column_names_for_edge(edge_name)
    type_name = _get_schema_type_name(inner_node, context)
    short_junction_table_name = u'{junction_table_name}'.format(junction_table_name=edge_name)
    has_short_table_name = context.compiler_metadata.has_table(short_junction_table_name)
    long_junction_table_name = u'{junction_table_name}_{type_name}'.format(
            junction_table_name=edge_name, type_name=type_name
        )
    has_long_table_name = context.compiler_metadata.has_table(long_junction_table_name)
    if not has_long_table_name and not has_short_table_name:
        return None
    if has_long_table_name and has_short_table_name:
        raise exceptions.GraphQLCompilationError(
            u'Ambiguous junction tables "{}" and "{}" found for edge "{}".'.format(
                short_junction_table_name, long_junction_table_name, edge_name)
        )
    junction_table_name = (long_junction_table_name
                           if has_long_table_name
                           else short_junction_table_name)
    junction_table = context.compiler_metadata.get_table(junction_table_name).alias()
    junction_table = junction_table.alias()
    if len(outer_selectable.primary_key) != 1:
        raise exceptions.GraphQLCompilationError(
            u'Table "{}" is expected to have exactly one primary key.'.format(
                outer_selectable.original))
    if len(inner_selectable.primary_key) != 1:
        raise exceptions.GraphQLCompilationError(
            u'Table "{}" is expected to have exactly one primary key.'.format(
                inner_selectable.original))
    outer_pk_name = outer_selectable.primary_key[0].name
    inner_pk_name = inner_selectable.primary_key[0].name
    direction = _get_block_direction(inner_node.block)
    if direction == INBOUND_EDGE_DIRECTION:
        inner_column_name, outer_column_name = outer_column_name, inner_column_name
    join_to_junction_expression = _get_selectable_join_expression(
        outer_selectable, outer_pk_name, junction_table, inner_column_name)
    join_from_junction_expression = _get_selectable_join_expression(
        junction_table, outer_column_name, inner_selectable, inner_pk_name)
    if join_to_junction_expression is None or join_from_junction_expression is None:
        raise exceptions.GraphQLCompilationError(
            (u'Junction table "{}" is expected to have foreign key "{}" to column "{}" of table '
             u'"{}" and foreign key "{}" to column "{}" of table "{}".').format(
                junction_table.original, inner_column_name, outer_pk_name,
                outer_selectable.original, outer_column_name, inner_pk_name,
                inner_selectable.original
            )
        )
    return ManyToManyJoin(
        join_to_junction_expression, junction_table, join_from_junction_expression)


def _get_column_names_for_edge(edge_name):
    """Return the expected column names for the given edge."""
    inner_prefix, outer_prefix = edge_name.lower().split('_')
    outer_column_name = u'{column_prefix}_id'.format(column_prefix=outer_prefix)
    inner_column_name = u'{column_prefix}_id'.format(column_prefix=inner_prefix)
    return outer_column_name, inner_column_name


def _get_selectable_join_expression(outer_selectable, outer_name, inner_selectable, inner_name):
    """Get a join expression between two selectables with the designated column names.

    Return None if such an expression does not exist.
    """
    outer_column = _try_get_column(outer_selectable, outer_name)
    inner_column = _try_get_column(inner_selectable, inner_name)
    if outer_column is None or inner_column is None:
        return None
    return outer_column == inner_column
