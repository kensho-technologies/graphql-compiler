from _operator import or_
from collections import namedtuple

import six
from sqlalchemy import select, and_, literal_column, cast, String, case, bindparam

from graphql_compiler.compiler import blocks, expressions
from graphql_compiler.compiler.ir_lowering_sql.constants import OPERATORS, Cardinality
from graphql_compiler.compiler.ir_lowering_sql.metadata import BasicEdge, MultiEdge


CompilationContext = namedtuple('CompilationContext', [
    'query_path_to_selectable',
    'query_path_to_location_info',
    'compiler_metadata',
])


def emit_code_from_ir(sql_query_tree_root_metadata, compiler_metadata):
    sql_query_tree, query_path_to_location_info = sql_query_tree_root_metadata
    context = CompilationContext(
        query_path_to_selectable={},
        query_path_to_location_info=query_path_to_location_info,
        compiler_metadata=compiler_metadata,
    )
    return _query_tree_to_query(sql_query_tree, context)


def _query_tree_to_query(node, context, recursion_in_column=None):
    # step 1: Collapse query tree, ignoring recursive
    visited_nodes = _visit_and_flatten_nonrecursive_nodes(node, context)
    recursion_out_column = None
    # step 2: If the tree rooted at the current node is recursive, create the recursive element
    if isinstance(node.block, blocks.Recurse):
        recursion_out_column = _create_recursive_clause(
            node, context, recursion_in_column
        )
    # step 3: query tree is collapsed, recursion at current node is created
    # materialize and wrap this query in a CTE
    query = _create_query(node, context, apply_filters=True)
    cte = query.cte()
    node.from_clause = cte
    for visited_node in visited_nodes:
        context.query_path_to_selectable[visited_node.query_path] = cte

    # step 4: collapse and return recursive node trees
    _traverse_recursions(node, context)
    if isinstance(node.block, blocks.QueryRoot):
        # filters have already been applied within the CTE, no need to reapply
        return _create_query(node, context, apply_filters=False)
    return recursion_out_column


def _traverse_recursions(node, context):
    for recursive_node in node.recursions:
        # retrieve the column that will be attached to the recursive element
        recursion_in_column = node.recursion_to_column[recursive_node]
        recursion_out_column = _query_tree_to_query(
            recursive_node, context, recursion_in_column=recursion_in_column
        )
        _join_to_recursive_node(node, recursive_node, recursion_in_column, recursion_out_column, context)
        for field_alias, field_data in six.iteritems(recursive_node.fields):
            node.fields[field_alias] = field_data
            node.fields_to_rename[field_alias] = recursive_node.fields_to_rename[field_alias]


def _visit_and_flatten_nonrecursive_nodes(node, context):
    # recursively collapse the children's trees
    visited_nodes = [node]
    for child_node in node.children_nodes:
        nodes_visited_from_child = _visit_and_flatten_nonrecursive_nodes(child_node, context)
        visited_nodes.extend(nodes_visited_from_child)

    # create the current node's table
    table = _create_and_reference_table(node, context)
    # ensure that columns required for recursion are present
    _create_links_for_recursions(node, context)
    for child_node in node.children_nodes:
        _flatten_node(node, child_node)
        # join to the child
        _join_to_node(node, child_node, context)
    return visited_nodes


def get_node_selectable(node, context):
    query_path = node.query_path
    selectable = context.query_path_to_selectable[query_path]
    return selectable


def _create_recursive_clause(node, context, out_link_column):
    edge = context.compiler_metadata.get_edge(node)
    selectable = get_node_selectable(node, context)
    if isinstance(edge, BasicEdge):
        source_col = edge.source_col
        sink_col = edge.sink_col
        base_col = source_col
        base_column = selectable.c[base_col]
        if node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col
        recursive_table = context.compiler_metadata.get_table(node).alias()
    elif isinstance(edge, MultiEdge):
        traversal_edge = edge.junction_edge
        final_edge = edge.final_edge
        sink_col = traversal_edge.sink_col
        source_col = final_edge.source_col
        base_col = traversal_edge.source_col
        base_column = selectable.c[base_col]
        if node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col
        recursive_table = context.compiler_metadata.get_table_by_name(traversal_edge.table_name).alias()
    else:
        raise AssertionError

    parent_cte_column = selectable.c[out_link_column.name]
    distinct_parent_column_query = select([parent_cte_column.label('link')],
                                          distinct=True).alias()
    anchor_query = (
        select(
            [
                selectable.c[base_col].label(source_col),
                selectable.c[base_col].label(sink_col),
                literal_column('0').label('__depth_internal_name'),
                cast(base_column, String()).concat(',').label('path'),
            ],
            distinct=True)
        .select_from(
            selectable.join(
                distinct_parent_column_query,
                base_column == distinct_parent_column_query.c['link']
            )
        )
    )
    recursive_cte = anchor_query.cte(recursive=True)
    recursive_query = (
        select(
            [
                recursive_table.c[source_col],
                recursive_cte.c[sink_col],
                (recursive_cte.c['__depth_internal_name'] + 1).label('__depth_internal_name'),
                (recursive_cte.c.path
                 .concat(cast(recursive_table.c[source_col], String()))
                 .concat(',')
                 .label('path')),
            ]
        )
        .select_from(
            recursive_table.join(
                recursive_cte,
                recursive_table.c[sink_col] == recursive_cte.c[source_col]
            )
        ).where(and_(
            recursive_cte.c['__depth_internal_name'] < node.block.depth,
            case(
                [(recursive_cte.c.path.contains(cast(recursive_table.c[source_col], String())), 1)],
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
    node.from_clause = node.from_clause.join(
        recursive_query,
        selectable.c[base_col] == recursive_query.c[source_col]
    )
    out_link_column = recursive_query.c[sink_col].label(None)
    node.add_recursive_link_column(recursive_query, out_link_column)
    return out_link_column


def _create_and_reference_table(node, context):
    table = context.compiler_metadata.get_table(node).alias()
    node.from_clause = table
    context.query_path_to_selectable[node.query_path] = table
    # ensure SQL blocks hold reference to Relation's table
    return table


def _flatten_node(node, child_node):
    for field_alias, field_data in six.iteritems(child_node.fields):
        node.fields[field_alias] = field_data
        node.fields_to_rename[field_alias] = child_node.fields_to_rename[field_alias]
    node.filters.extend(child_node.filters)
    node.recursions.extend(child_node.recursions)
    for recursion, link_column in child_node.recursion_to_column.items():
        node.recursion_to_column[recursion] = link_column
    node.link_columns.extend(child_node.link_columns)


def _join_to_node(node, child_node, context):
    onclauses = get_on_clause_for_node(node, child_node, context)
    location_info = context.query_path_to_location_info[child_node.query_path]
    if location_info.optional_scopes_depth > 0:
        for table, onclause in onclauses:
            node.from_clause = node.from_clause.outerjoin(
                child_node.from_clause, onclause=onclause
            )
        return
    for table, onclause in onclauses:
        node.from_clause = node.from_clause.join(
            child_node.from_clause, onclause=onclause
        )


def get_on_clause_for_node(node, child_node, context):
    parent_selectable = get_node_selectable(node, context)
    child_selectable = get_node_selectable(child_node, context)
    edge = context.compiler_metadata.get_edge(child_node)
    if isinstance(edge, BasicEdge):
        source_col = edge.source_col
        sink_col = edge.sink_col
        if child_node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col
        if edge is None:
            return None
        outer_column = context.compiler_metadata._get_column_from_table(parent_selectable, source_col)
        inner_column = context.compiler_metadata._get_column_from_table(child_selectable, sink_col)
        return [(child_node.from_clause, outer_column == inner_column)]
    elif isinstance(edge, MultiEdge):
        traversal_edge = edge.junction_edge
        junction_table = context.compiler_metadata.get_table_by_name(traversal_edge.table_name).alias()
        source_col = traversal_edge.source_col
        sink_col = traversal_edge.sink_col
        if child_node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col

        outer_column = context.compiler_metadata._get_column_from_table(child_node.parent_node.from_clause, source_col)
        inner_column = context.compiler_metadata._get_column_from_table(junction_table, sink_col)
        traversal_onclause = outer_column == inner_column
        if child_node.in_optional:
            child_node.parent_node.from_clause = child_node.parent_node.from_clause.outerjoin(
                junction_table, onclause=traversal_onclause
            )
        else:
            child_node.parent_node.from_clause = child_node.parent_node.from_clause.join(junction_table, onclause=traversal_onclause)
        final_edge = edge.final_edge
        source_col = final_edge.source_col
        sink_col = final_edge.sink_col
        if child_node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col

        outer_column = context.compiler_metadata._get_column_from_table(junction_table, source_col)
        inner_column = context.compiler_metadata._get_column_from_table(child_selectable, sink_col)
        return [(child_node.from_clause, outer_column == inner_column)]



def _create_link_for_recursion(node, recursion_node, context):
    edge = context.compiler_metadata.get_edge(recursion_node)
    selectable = get_node_selectable(node, context)
    if isinstance(edge, BasicEdge):
        from_col = edge.source_col
        recursion_in_column = selectable.c[from_col]
        node.add_recursive_link_column(recursion_node, recursion_in_column)
        return recursion_in_column
    elif isinstance(edge, MultiEdge):
        from_col = edge.junction_edge.source_col
        recursion_in_column = selectable.c[from_col]
        node.add_recursive_link_column(recursion_node, recursion_in_column)
        return recursion_in_column
    raise AssertionError


def _create_links_for_recursions(node, context):
    if len(node.recursions) == 0:
        return
    for recursion in node.recursions:
        recursion_in_column = _create_link_for_recursion(node, recursion, context)


def _join_to_recursive_node(node, recursive_node, recursion_in_column, recursion_out_column,
                            context):
    selectable = get_node_selectable(node, context)
    recursive_selectable = get_node_selectable(recursive_node, context)
    current_cte_column = selectable.c[recursion_in_column.name]
    recursive_cte_column = recursive_selectable.c[recursion_out_column.name]
    node.from_clause = node.from_clause.join(
        recursive_node.from_clause, onclause=current_cte_column == recursive_cte_column
    )


def _get_output_columns(node, context):
    columns = []
    for field_alias, (field, schema_type) in six.iteritems(node.fields):
        is_renamed = node.fields_to_rename[field_alias]
        selectable = context.query_path_to_selectable[field.location.query_path]
        if is_renamed:
            column = selectable.c[field_alias]
        else:
            field_name = field.location.field
            column_name = context.compiler_metadata.get_column_name_for_type(schema_type.name, field_name)
            column = selectable.c[column_name].label(field_alias)
            node.fields_to_rename[field_alias] = True
        columns.append(column)
    return columns


def _create_query(node, context, apply_filters):
    columns = _get_output_columns(node, context)
    columns.extend(node.link_columns)
    node.link_columns = []
    query = select(columns, distinct=True).select_from(node.from_clause)
    if not apply_filters:
        return query

    filter_clauses = [
        convert_filter_to_sql(filter_block, query_path, location_info, context)
        for filter_block, query_path, location_info in node.filters
    ]
    return query.where(and_(*filter_clauses))


def convert_filter_to_sql(filter_block, query_path, location_info, context):
    selectable = context.query_path_to_selectable[query_path]
    predicate = filter_block.predicate
    if not isinstance(predicate, expressions.BinaryComposition):
        raise AssertionError
    sql_operator = OPERATORS[predicate.operator]
    left = predicate.left
    right = predicate.right
    # todo: Between comes in as x >= lower and x <= upper, which are each
    # themselves BinaryComposition objects
    variable, field = left, right
    if isinstance(variable, expressions.LocalField):
        variable, field = right, left
    column_name = context.compiler_metadata.get_column_name_for_type(location_info.type.name, field.field_name)
    column = selectable.c[column_name]
    if isinstance(variable, expressions.ContextField):
        tag_field_name = variable.location.field
        tag_query_path = variable.location.query_path
        tag_location_info = context.query_path_to_location_info[tag_query_path]
        tag_column_name = context.compiler_metadata.get_column_name_for_type(tag_location_info.type.name, tag_field_name)
        tag_selectable = context.query_path_to_selectable[tag_query_path]
        tag_column = tag_selectable.c[tag_column_name]
        operation = getattr(column, sql_operator.name)
        clause = operation(tag_column)
    else:
        param_name = variable.variable_name
        if sql_operator.cardinality == Cardinality.SINGLE:
            operation = getattr(column, sql_operator.name)
            clause = operation(bindparam(param_name))
        elif sql_operator.cardinality == Cardinality.MANY:
            operation = getattr(column, sql_operator.name)
            clause = operation(bindparam(param_name, expanding=True))

        elif sql_operator.cardinality == Cardinality.DUAL:
            first_param, second_param = filter_block.param_names
            operation = getattr(column, filter_block.operator.name)
            clause = operation(bindparam(first_param), bindparam(second_param))
        else:
            raise AssertionError(
                'Unable to construct where clause with cardinality "{}"'.format(
                    filter_block.operator.cardinality
                )
            )
    if clause is None:
        raise AssertionError("This should be unreachable.")
    if location_info.optional_scopes_depth == 0:
        return clause
    # the == None below is valid SQLAlchemy, the == operator is heavily overloaded.
    return or_(column == None, clause)  # noqa: E711

