from _operator import or_

import six
from sqlalchemy import select, and_, literal_column, cast, String, case, bindparam

from graphql_compiler.compiler import blocks, expressions
from graphql_compiler.compiler.ir_lowering_sql.constants import OPERATORS, Cardinality
from graphql_compiler.compiler.ir_lowering_sql.metadata import BasicEdge, MultiEdge


def emit_code_from_ir(sql_query_tree_root_metadata, compiler_metadata):
    query_path_to_selectable = {}
    sql_query_tree, query_path_to_location_info = sql_query_tree_root_metadata
    return _query_tree_to_query(sql_query_tree, query_path_to_selectable, query_path_to_location_info, compiler_metadata)


def _query_tree_to_query(node, query_path_to_selectable, query_path_to_location_info, compiler_metadata, recursion_in_column=None):
    # step 1: Collapse query tree, ignoring recursive blocks
    paths = _collapse_query_tree(node, query_path_to_selectable, compiler_metadata)
    recursion_out_column = None
    # step 2: If the tree rooted at the current node is recursive, create the recursive element
    if isinstance(node.block, blocks.Recurse):
        recursion_out_column = _create_recursive_clause(
            node, compiler_metadata, recursion_in_column
        )
    # step 3: query tree is collapsed, recursion at current node is created
    # materialize and wrap this query in a CTE
    query = _create_query(node, query_path_to_selectable, query_path_to_location_info, compiler_metadata, use_predicates=True)
    cte = _wrap_query_as_cte(node, query)
    for path in paths:
        query_path_to_selectable[path] = cte

    for child_node in node.children_nodes:
        query_path_to_selectable[child_node.query_path] = cte

    # step 4: collapse and return recursive node trees
    _traverse_recursions(node, query_path_to_selectable, query_path_to_location_info, compiler_metadata)
    if isinstance(node.block, blocks.QueryRoot):
        # This is the root
        return _create_query(node, query_path_to_selectable, query_path_to_location_info, compiler_metadata, use_predicates=False)
    return recursion_out_column


def _traverse_recursions(node, query_path_to_selectable, query_path_to_location_info, compiler_metadata):
    for recursive_node in node.recursions:
        # retrieve the column that will be attached to the recursive element
        recursion_in_column = node.recursion_to_column[recursive_node]
        recursion_out_column = _query_tree_to_query(
            recursive_node, query_path_to_selectable, query_path_to_location_info, compiler_metadata, recursion_in_column=recursion_in_column
        )
        _join_to_recursive_node(node, recursion_in_column, recursive_node, recursion_out_column)
        for field_alias, field_data in six.iteritems(recursive_node.fields):
            node.fields[field_alias] = field_data
            node.fields_to_rename[field_alias] = recursive_node.fields_to_rename[field_alias]


def _collapse_query_tree(node, query_path_to_selectable, compiler_metadata):
    # recursively collapse the children's trees
    paths = [node.query_path]
    for child_node in node.children_nodes:
        paths.extend(_collapse_query_tree(child_node, query_path_to_selectable, compiler_metadata))
    for child_node in node.children_nodes:
        for field_alias, field_data in six.iteritems(child_node.fields):
            node.fields[field_alias] = field_data
            node.fields_to_rename[field_alias] = child_node.fields_to_rename[field_alias]
    # create the current node's table
    table = _create_and_reference_table(node, compiler_metadata)
    query_path_to_selectable[node.query_path] = table
    # ensure that columns required for recursion are present
    _create_links_for_recursions(node, compiler_metadata)
    for child_node in node.children_nodes:
        # pull up the childs SQL blocks
        _pull_up_node_blocks(node, child_node)
        # join to the child
        _join_to_node(node, child_node, compiler_metadata)
    return paths


def _create_recursive_clause(node, compiler_metadata, out_link_column):
    edge = compiler_metadata.get_edge(node)
    if isinstance(edge, BasicEdge):
        source_col = edge.source_col
        sink_col = edge.sink_col
        base_col = source_col
        base_column = node.table.c[base_col]
        if node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col
        recursive_table = compiler_metadata.get_table(node).alias()
    elif isinstance(edge, MultiEdge):
        traversal_edge = edge.junction_edge
        final_edge = edge.final_edge
        sink_col = traversal_edge.sink_col
        source_col = final_edge.source_col
        base_col = traversal_edge.source_col
        base_column = node.table.c[base_col]
        if node.block.direction == 'in':
            source_col, sink_col = sink_col, source_col
        recursive_table = compiler_metadata.get_table_by_name(traversal_edge.table_name).alias()
    else:
        raise AssertionError

    parent_cte_column = node.table.c[out_link_column.name]
    distinct_parent_column_query = select([parent_cte_column.label('link')],
                                          distinct=True).alias()
    anchor_query = (
        select(
            [
                node.table.c[base_col].label(source_col),
                node.table.c[base_col].label(sink_col),
                literal_column('0').label('__depth_internal_name'),
                cast(base_column, String()).concat(',').label('path'),
            ],
            distinct=True)
        .select_from(
            node.table.join(
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
    recursion_combinator = compiler_metadata.db_backend.recursion_combinator
    if not hasattr(recursive_cte, recursion_combinator):
        raise AssertionError(
            'Cannot combine anchor and recursive clauses with operation "{}"'.format(
                recursion_combinator
            )
        )
    recursive_query = getattr(recursive_cte, recursion_combinator)(recursive_query)
    node.from_clause = node.from_clause.join(
        recursive_query,
        node.table.c[base_col] == recursive_query.c[source_col]
    )
    out_link_column = recursive_query.c[sink_col].label(None)
    node.add_recursive_link_column(recursive_query, out_link_column)
    return out_link_column


def _create_and_reference_table(node, compiler_metadata):
    table = compiler_metadata.get_table(node).alias()
    node.table = table
    node.from_clause = table
    # ensure SQL blocks hold reference to Relation's table
    return table



def _pull_up_node_blocks(node, child_node):
    node.filters.extend(child_node.filters)
    node.recursions.extend(child_node.recursions)
    for recursion, link_column in child_node.recursion_to_column.items():
        node.recursion_to_column[recursion] = link_column
    node.link_columns.extend(child_node.link_columns)


def _join_to_node(node, child_node, compiler_metadata):
    # outer table is the current table, inner table is the child's
    onclauses = compiler_metadata.get_on_clause_for_node(child_node)
    if child_node.in_optional:
        for table, onclause in onclauses:
            node.from_clause = node.from_clause.outerjoin(
                child_node.from_clause, onclause=onclause
            )
        return
    for table, onclause in onclauses:
        node.from_clause = node.from_clause.join(
            child_node.from_clause, onclause=onclause
        )


def _update_table_for_blocks(table, blocks):
    for block in blocks:
        block.table = table


def _create_link_for_recursion(node, recursion_node, compiler_metadata):
    edge = compiler_metadata.get_edge(recursion_node)
    if isinstance(edge, BasicEdge):
        from_col = edge.source_col
        recursion_in_column = node.table.c[from_col]
        node.add_recursive_link_column(recursion_node, recursion_in_column)
        return
    elif isinstance(edge, MultiEdge):
        from_col = edge.junction_edge.source_col
        recursion_in_column = node.table.c[from_col]
        node.add_recursive_link_column(recursion_node, recursion_in_column)
        return
    raise AssertionError



def _create_links_for_recursions(node, compiler_metadata):
    if len(node.recursions) == 0:
        return
    for recursion in node.recursions:
        _create_link_for_recursion(node, recursion, compiler_metadata)


def _join_to_recursive_node(node, recursion_in_column, recursive_node, recursion_out_column):
    current_cte_column = node.table.c[recursion_in_column.name]
    recursive_cte_column = recursive_node.table.c[recursion_out_column.name]
    node.from_clause = node.from_clause.join(
        recursive_node.from_clause, onclause=current_cte_column == recursive_cte_column
    )


def get_output_columns(node, query_path_to_selectable, compiler_metadata):
    columns = []
    for field_alias, (field, schema_type) in six.iteritems(node.fields):
        is_renamed = node.fields_to_rename[field_alias]
        selectable = query_path_to_selectable[field.location.query_path]
        if is_renamed:
            column = selectable.c[field_alias]
        else:
            field_name = field.location.field
            column_name = compiler_metadata.get_column_name_for_type(schema_type.name, field_name)
            column = selectable.c[column_name].label(field_alias)
            node.fields_to_rename[field_alias] = True
        columns.append(column)
    return columns


def _wrap_query_as_cte(node, query):
    cte = query.cte()
    node.from_clause = cte
    node.table = cte
    return cte


def _create_query(node, query_path_to_selectable, query_path_to_location_info, compiler_metadata, use_predicates):
    columns = get_output_columns(node, query_path_to_selectable, compiler_metadata)
    columns += node.link_columns
    node.link_columns = []
    query = select(columns, distinct=True).select_from(node.from_clause)
    if not use_predicates:
        return query

    predicates = [
        convert_filter_to_sql(filter_block, query_path, query_path_to_selectable, query_path_to_location_info, location_info, compiler_metadata)
        for filter_block, query_path, location_info in node.filters
    ]
    return query.where(and_(*predicates))


def convert_filter_to_sql(filter_block, query_path, query_path_to_selectable, query_path_to_location_info, location_info, compiler_metadata):
    selectable = query_path_to_selectable[query_path]
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
    column_name = compiler_metadata.get_column_name_for_type(location_info.type.name, field.field_name)
    column = selectable.c[column_name]
    if isinstance(variable, expressions.ContextField):
        tag_field_name = variable.location.field
        tag_query_path = variable.location.query_path
        tag_location_info = query_path_to_location_info[tag_query_path]
        tag_column_name = compiler_metadata.get_column_name_for_type(tag_location_info.type.name, tag_field_name)
        tag_selectable = query_path_to_selectable[tag_query_path]
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

