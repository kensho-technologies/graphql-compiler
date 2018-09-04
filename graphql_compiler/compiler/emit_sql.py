from _operator import or_
from collections import namedtuple, defaultdict

import six
from sqlalchemy import select, and_, literal_column, cast, String, case, bindparam, Column
from sqlalchemy import exc as sqlalchemy_exceptions
from sqlalchemy.sql.elements import BindParameter
from sqlalchemy.sql.util import join_condition

from graphql_compiler import exceptions
from graphql_compiler.compiler import blocks, expressions
from sqlalchemy.sql import expression as sql_expressions, Join
from graphql_compiler.compiler.ir_lowering_sql import constants
from graphql_compiler.compiler.ir_lowering_sql.metadata import DirectEdge, JunctionEdge


SQLALCHEMY_FK_NOT_FOUND_EXCEPTIONS = (
    sqlalchemy_exceptions.AmbiguousForeignKeysError,
    sqlalchemy_exceptions.NoForeignKeysError
)

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
    """Recursively converts a SqlNode tree to a SQLAlchemy query."""
    # step 1: Collapse query tree, ignoring recursive nodes
    visited_nodes = _flatten_and_join_nonrecursive_nodes(node, context)
    # step 2: Create the recursive element (only occurs on a recursive call of this function)
    recursion_out_column = _create_recursive_clause(node, context, recursion_link_column, outer_cte)
    # step 3: Materialize query as a CTE.
    cte = _create_query(node, context, is_final_query=False).cte()
    # Output fields from individual tables become output fields from the CTE
    _update_context_paths(node, visited_nodes, cte, context)
    # step 4: collapse and return recursive node trees, passing the CTE to the recursive element
    _flatten_and_join_recursive_nodes(node, cte, context)
    if isinstance(node.block, blocks.QueryRoot):
        # filters have already been applied within the CTE, no need to reapply
        return _create_query(node, context, is_final_query=True)
    return recursion_out_column


def _flatten_and_join_recursive_nodes(node, cte, context):
    """Join recursive child nodes to parent, flattening child's references."""
    for recursive_node in node.recursions:
        # retrieve the column that will be attached to the recursive element
        recursion_source_column, _ = context.query_path_to_recursion_columns[recursive_node.query_path]
        recursion_sink_column = _query_tree_to_query(
            recursive_node, context, recursion_link_column=recursion_source_column, outer_cte=cte
        )
        _flatten_output_fields(node, recursive_node, context)
        onclause = _get_recursive_onclause(node, recursive_node, recursion_source_column,
                                           recursion_sink_column, context)
        _join_nodes(node, recursive_node, onclause, context)


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
        onclause = _get_on_clause_for_node(node, child_node, context)
        _join_nodes(node, child_node, onclause, context)
    return visited_nodes


def _get_node_selectable(node, context):
    """Return the selectable (Table, CTE) of a node."""
    query_path = node.query_path
    selectable = context.query_path_to_selectable[query_path]
    return selectable


def _get_schema_type(node, context):
    """Return the GraphQL type name of a node."""
    query_path = node.query_path
    location_info = context.query_path_to_location_info[query_path]
    return location_info.type.name


def _create_recursive_clause(node, context, out_link_column, outer_cte):
    """Create a recursive clause for a Recurse block."""
    if not isinstance(node.block, blocks.Recurse):
        return None
    if out_link_column is None or outer_cte is None:
        raise AssertionError()
    schema_type = _get_schema_type(node, context)
    edge = _get_edge(node.block, None, schema_type, None, None, context)
    selectable = _get_node_selectable(node, context)
    if isinstance(edge, sql_expressions.BinaryExpression):
        source_col, sink_col = edge.left, edge.right
        source_col = source_col.name
        sink_col = sink_col.name
        base_col = source_col
        base_column = selectable.c[base_col]
        if node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col
        schema_type = _get_schema_type(node, context)
        recursive_table = context.compiler_metadata.get_table(schema_type).alias()
    elif isinstance(edge, tuple):
        traversal_edge, recursive_table, final_edge = edge
        source_col = final_edge.right.name
        sink_col = traversal_edge.right.name
        base_col = traversal_edge.left.name
        base_column = selectable.c[base_col]
        if node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col
    elif isinstance(edge, DirectEdge):
        source_col = edge.source_col
        sink_col = edge.sink_col
        base_col = source_col
        base_column = selectable.c[base_col]
        if node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col
        schema_type = _get_schema_type(node, context)
        recursive_table = context.compiler_metadata.get_table(schema_type).alias()
    elif isinstance(edge, JunctionEdge):
        traversal_edge = edge.junction_edge
        final_edge = edge.final_edge
        sink_col = traversal_edge.sink_col
        source_col = final_edge.source_col
        base_col = traversal_edge.source_col
        base_column = selectable.c[base_col]
        if node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col
        recursive_table = context.compiler_metadata.get_table(traversal_edge.table_name).alias()
    else:
        raise AssertionError()

    parent_cte_column = outer_cte.c[out_link_column.name]
    anchor_query = (
        select(
            [
                selectable.c[base_col].label(source_col),
                selectable.c[base_col].label(sink_col),
                literal_column('0').label(constants.DEPTH_INTERNAL_NAME),
                cast(base_column, String()).concat(',').label(constants.PATH_INTERNAL_NAME),
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
                recursive_table.c[source_col],
                recursive_cte.c[sink_col],
                ((recursive_cte.c[constants.DEPTH_INTERNAL_NAME] + 1)
                 .label(constants.DEPTH_INTERNAL_NAME)),
                (recursive_cte.c[constants.PATH_INTERNAL_NAME]
                 .concat(cast(recursive_table.c[source_col], String()))
                 .concat(',')
                 .label(constants.PATH_INTERNAL_NAME)),
            ]
        )
        .select_from(
            recursive_table.join(
                recursive_cte,
                recursive_table.c[sink_col] == recursive_cte.c[source_col]
            )
        ).where(and_(
            recursive_cte.c[constants.DEPTH_INTERNAL_NAME] < node.block.depth,
            case(
                [(recursive_cte.c[constants.PATH_INTERNAL_NAME]
                  .contains(cast(recursive_table.c[source_col], String())), 1)],
                else_=0
            ) == 0
        ))
    )
    recursion_combinator = context.compiler_metadata.db_backend.recursion_combinator
    if not hasattr(recursive_cte, recursion_combinator):
        raise AssertionError(
            'Cannot combine anchor and recursive clauses with operation "{}"'.format(
                recursion_combinator
            )
        )
    recursive_query = getattr(recursive_cte, recursion_combinator)(recursive_query)
    from_clause = context.query_path_to_from_clause[node.query_path]
    from_clause = from_clause.join(
        recursive_query,
        selectable.c[base_col] == recursive_query.c[source_col]
    )
    from_clause = from_clause.join(
        outer_cte, recursive_query.c[sink_col] == parent_cte_column
    )
    context.query_path_to_from_clause[node.query_path] = from_clause
    out_link_column = recursive_query.c[sink_col].label(None)
    (in_col, _) = context.query_path_to_recursion_columns[node.query_path]
    context.query_path_to_recursion_columns[node.query_path] = (in_col, out_link_column)
    return out_link_column


def _create_and_reference_table(node, context):
    schema_type = _get_schema_type(node, context)
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
    context.query_path_to_tag_fields[parent_node.query_path].extend(context.query_path_to_tag_fields[child_node.query_path])
    del context.query_path_to_output_fields[child_node.query_path]


def _join_nodes(parent_node, child_node, onclause, context):
    """Join two nodes and update compilation context."""
    location_info = context.query_path_to_location_info[child_node.query_path]
    is_optional = location_info.optional_scopes_depth > 0
    parent_from_clause = context.query_path_to_from_clause[parent_node.query_path]
    child_from_clause = context.query_path_to_from_clause[child_node.query_path]
    if is_optional:
        if isinstance(onclause, tuple):
            parent_to_junction_onclause, junction_table, junction_to_child_onclause = onclause
            parent_from_clause = parent_from_clause.outerjoin(junction_table, onclause=parent_to_junction_onclause)
            parent_from_clause = parent_from_clause.outerjoin(child_from_clause, onclause=junction_to_child_onclause)
        else:
            parent_from_clause = parent_from_clause.outerjoin(child_from_clause, onclause=onclause)
    else:
        if isinstance(onclause, tuple):
            parent_to_junction_onclause, junction_table, junction_to_child_onclause = onclause
            parent_from_clause = parent_from_clause.join(junction_table, onclause=parent_to_junction_onclause)
            parent_from_clause = parent_from_clause.join(child_from_clause, onclause=junction_to_child_onclause)
        else:
            parent_from_clause = parent_from_clause.join(child_from_clause, onclause=onclause)
    context.query_path_to_from_clause[parent_node.query_path] = parent_from_clause
    del context.query_path_to_from_clause[child_node.query_path]


def _get_on_clause_for_node(parent_node, child_node, context):
    """Get an onclause for joining two nodes."""
    parent_selectable = _get_node_selectable(parent_node, context)
    child_selectable = _get_node_selectable(child_node, context)
    child_schema_type = _get_schema_type(child_node, context)
    parent_schema_type = _get_schema_type(parent_node, context)
    edge = _get_edge(child_node.block, parent_schema_type, child_schema_type, parent_selectable, child_selectable, context)
    return edge

def _create_link_for_recursion(node, recursion_node, context):
    """Ensure that the column necessary to link to a recursion is present in the CTE columns."""
    recursion_schema_type = _get_schema_type(recursion_node, context)
    parent_schema_type = _get_schema_type(node, context)
    selectable = _get_node_selectable(node, context)
    recursive_selectable = _get_node_selectable(node, context)
    edge = _get_edge(recursion_node.block, parent_schema_type, recursion_schema_type, selectable, recursive_selectable, context)
    recursion_in_col = None
    if isinstance(edge, tuple):
        recursion_on_clause, _, _ = edge
        recursion_in_col = recursion_on_clause.left
    else:
        recursion_in_col = edge.left
    context.query_path_to_recursion_columns[recursion_node.query_path] = (recursion_in_col, None)
    return recursion_in_col


def _create_links_for_recursions(node, context):
    for recursion in node.recursions:
        _create_link_for_recursion(node, recursion, context)


def _get_recursive_onclause(node, recursive_node, in_column, out_column, context):
    """Return an onclause for linking a node to a recursive child node."""
    selectable = _get_node_selectable(node, context)
    recursive_selectable = _get_node_selectable(recursive_node, context)
    current_cte_column = selectable.c[in_column.name]
    recursive_cte_column = recursive_selectable.c[out_column.name]
    onclause = current_cte_column == recursive_cte_column
    return onclause


def _get_output_columns(node, is_final_query, context):
    """Convert the output fields of a SqlNode to aliased Column objects."""
    output_fields = context.query_path_to_output_fields[node.query_path]
    columns = []
    for field_alias, (field, field_type, is_renamed) in six.iteritems(output_fields):
        selectable = context.query_path_to_selectable[field.location.query_path]
        if is_renamed:
            column = selectable.c[field_alias]
        else:
            field_name = field.location.field
            column = selectable.c[field_name].label(field_alias)
            output_fields[field_alias] = (field, field_type, True)
            context.query_path_field_renames[field.location.query_path][field_name] = field_alias
        columns.append(column)
    if not is_final_query:
        for tag_field in context.query_path_to_tag_fields[node.query_path]:
            selectable = context.query_path_to_selectable[tag_field.location.query_path]
            field_name = tag_field.location.field
            column = selectable.c[field_name].label(None)
            columns.append(column)
            context.query_path_field_renames[tag_field.location.query_path][field_name] = column.name
    return columns


def _create_query(node, context, is_final_query):
    """Create a query from a SqlNode. If this query is the final query, we do not need to apply
    filters, or include intermediate link columns in the output."""
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
        # for every recursion that is a child of this node, include the link column inward to the
        # recursion in this node's query's outputs
        for recursion in node.recursions:
            in_col, _ = context.query_path_to_recursion_columns[recursion.query_path]
            columns.append(in_col)
    # If this node is completing a recursion, include the outward column in this node's outputs
    if node.query_path in context.query_path_to_recursion_columns:
        _, out_col = context.query_path_to_recursion_columns[node.query_path]
        columns.append(out_col)

    from_clause = context.query_path_to_from_clause[node.query_path]
    query = select(columns).select_from(from_clause)
    if is_final_query:
        return query
    return query.where(and_(*filter_clauses))


def _convert_filter_to_sql(filter_block, query_path, context):
    """Return the SQLAlchemy expression for a Filter predicate."""
    location_info = context.query_path_to_location_info[query_path]
    selectable = context.query_path_to_selectable[query_path]
    expression = filter_block.predicate
    return _expression_to_sql(expression, selectable, location_info, context)


def _expression_to_sql(expression, selectable, location_info, context):
    """Recursively convert a compiler expression to a SQLAlchemy expression."""
    if isinstance(expression, expressions.LocalField):
        column_name = expression.field_name
        column = selectable.c[column_name]
        return column
    elif isinstance(expression, expressions.Variable):
        variable_name = expression.variable_name
        return bindparam(variable_name)
    elif isinstance(expression, expressions.Literal):
        return expression.value
    elif isinstance(expression, expressions.ContextField):
        tag_field_name = expression.location.field
        tag_query_path = expression.location.query_path
        tag_column_name = tag_field_name
        if tag_query_path in context.query_path_field_renames:
            if tag_field_name in context.query_path_field_renames[tag_query_path]:
                tag_column_name = context.query_path_field_renames[tag_query_path][tag_field_name]
        tag_selectable = context.query_path_to_selectable[tag_query_path]
        tag_column = tag_selectable.c[tag_column_name]
        return tag_column
    elif isinstance(expression, expressions.BinaryComposition):
        sql_operator = constants.OPERATORS[expression.operator]
        left = _expression_to_sql(expression.left, selectable, location_info, context)
        right = _expression_to_sql(expression.right, selectable, location_info, context)
        if sql_operator.cardinality == constants.Cardinality.SINGLE:
            if right is None and left is None:
                raise AssertionError()
            if left is None and right is not None:
                left, right = right, left
            clause = getattr(left, sql_operator.name)(right)
        elif sql_operator.cardinality == constants.Cardinality.DUAL:
            clause = getattr(sql_expressions, sql_operator.name)(left, right)
        elif sql_operator.cardinality == constants.Cardinality.MANY:
            if not isinstance(left, BindParameter):
                raise AssertionError()
            if not isinstance(right, Column):
                raise AssertionError()
            left.expanding = True
            clause = getattr(right, sql_operator.name)(left)
        else:
            raise AssertionError()
        return clause
    else:
        raise AssertionError()


def _get_edge(block, parent_schema_type, child_schema_type, outer_table, inner_table, context):
    """Return the SimpleEdge or MultiEdge linking two GraphQL schema types.

    Note that this edge may be overridden in the external configuration.
    """
    edge_name = block.edge_name
    if not isinstance(block, blocks.Recurse):
        outer_type_name = parent_schema_type
        relative_type = child_schema_type
    else:
        # this is a recursive edge, from a type back onto itself
        outer_type_name = child_schema_type
        relative_type = child_schema_type
    if outer_table is None and inner_table is None:
        outer_table = context.compiler_metadata.get_table(outer_type_name)
        inner_table = context.compiler_metadata.get_table(relative_type)
    return find_join_condition(block, outer_table, inner_table, relative_type, context)
    # edge_override = context.compiler_metadata.get_edge(outer_type_name, relative_type, edge_name)
    # if edge_override is not None:
    #     return edge_override


def find_join_condition(block, outer_table, inner_table, type_name, context):
    onclause = find_many_to_many_join_condition(block, outer_table, inner_table, type_name, context)
    if onclause is not None:
        return onclause
    onclause = _try_get_on_clause(outer_table, inner_table)
    if onclause is not None:
        # handle the case where a table holds a foreign key back onto itself
        if isinstance(onclause, sql_expressions.BooleanClauseList) and _tables_equal(outer_table, inner_table):
            out_clause, in_clause = onclause.clauses
            if block.direction == 'in':
                return in_clause
            elif block.direction == 'out':
                return out_clause
        return onclause
    raise AssertionError()


def find_many_to_many_join_condition(block, outer_table, inner_table, type_name, context):
    junction_table_name = block.edge_name.lower()
    junction_table = None
    if junction_table_name in context.compiler_metadata.table_name_to_table:
        junction_table = context.compiler_metadata.get_table(junction_table_name)
    junction_table_name = u'{junction_table_name}_{type_name}'.format(junction_table_name=junction_table_name, type_name=type_name.lower())
    if junction_table_name in context.compiler_metadata.table_name_to_table:
        junction_table = context.compiler_metadata.table_name_to_table[junction_table_name]
    if junction_table is None:
        return None
    junction_table = junction_table.alias()
    outer_to_junction_onclause = _try_get_on_clause(outer_table, junction_table)
    is_in_edge = block.direction == 'in'
    if isinstance(outer_to_junction_onclause, list):
        if len(outer_to_junction_onclause) == 1:
            outer_to_junction_onclause = outer_to_junction_onclause[0]
        elif len(outer_to_junction_onclause) == 2:
            if is_in_edge:
                outer_to_junction_onclause = [onclause for onclause in outer_to_junction_onclause
                                              if onclause.right.name.startswith('in_')][0]
            else:
                outer_to_junction_onclause = [onclause for onclause in outer_to_junction_onclause
                                              if onclause.right.name.startswith('out_')][0]
        else:
            raise AssertionError()
    junction_to_inner_onclause = _try_get_on_clause(junction_table, inner_table)
    if isinstance(junction_to_inner_onclause, list):
        if len(junction_to_inner_onclause) == 1:
            outer_to_junction_onclause = junction_to_inner_onclause[0]
        elif len(junction_to_inner_onclause) == 2:
            if is_in_edge:
                junction_to_inner_onclause = [onclause for onclause in junction_to_inner_onclause if onclause.right.name.startswith('out_')][0]
            else:
                junction_to_inner_onclause = [onclause for onclause in junction_to_inner_onclause if onclause.right.name.startswith('in_')][0]
        else:
            raise AssertionError()

    return outer_to_junction_onclause, junction_table, junction_to_inner_onclause


def _try_get_on_clause(outer_table, inner_table):
    """Attempt to find onclause for joining outer_table to inner_table

    Return None if this clause cannot be uniquely determined.
    """
    try:
        return join_condition(outer_table, inner_table)
    except SQLALCHEMY_FK_NOT_FOUND_EXCEPTIONS:
        constraints = Join._joincond_scan_left_right(outer_table, None, inner_table, None)
        onclauses = []
        for constraint_list in constraints.values():
            for x, y in constraint_list:
                onclauses.append(x == y)
        if len(onclauses) == 0:
            return None
        return onclauses

def _tables_equal(right_table, left_table):
    if hasattr(right_table, 'original'):
        right_table = right_table.original
    if hasattr(left_table, 'original'):
        left_table = left_table.original
    return right_table == left_table


