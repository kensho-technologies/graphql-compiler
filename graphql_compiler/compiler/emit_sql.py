import six
from sqlalchemy import select, and_, literal_column, cast, String, case

from graphql_compiler.compiler import blocks
from graphql_compiler.compiler.ir_lowering_sql.metadata import BasicEdge, MultiEdge


def emit_code_from_ir(sql_query_tree, compiler_metadata):
    query_path_to_selectable = {}
    return _query_tree_to_query(sql_query_tree, query_path_to_selectable, compiler_metadata)


def _query_tree_to_query(node, query_path_to_selectable, compiler_metadata, recursion_in_column=None):
    # step 1: Collapse query tree, ignoring recursive blocks
    paths = _collapse_query_tree(node, query_path_to_selectable, compiler_metadata)
    recursion_out_column = None
    # step 2: If the tree rooted at the current node is recursive, create the recursive element
    if isinstance(node.block, blocks.Recurse):
        # this node is itself recursive, setup recursion linked to supplied link column
        recursion_out_column = _create_recursive_clause(
            node, compiler_metadata, recursion_in_column
        )
    # step 3: query tree is collapsed, recursion at current node is created
    # materialize and wrap this query in a CTE
    query = _create_base_query(node, query_path_to_selectable, compiler_metadata)
    cte = _wrap_query_as_cte(node, query)
    for path in paths:
        query_path_to_selectable[path] = cte

    for child_node in node.children_nodes:
        query_path_to_selectable[child_node.query_path] = cte

    # step 4: collapse and return recursive node trees
    _traverse_recursions(node, query_path_to_selectable, compiler_metadata)
    if node.parent_node is None:
        # This is the root
        return _create_final_query(node, query_path_to_selectable, compiler_metadata)
    return recursion_out_column


def _traverse_recursions(node, query_path_to_selectable, compiler_metadata):
    for recursive_node in node.recursions:
        # retrieve the column that will be attached to the recursive element
        recursion_in_column = node.recursion_to_column[recursive_node]
        recursion_out_column = _query_tree_to_query(
            recursive_node, query_path_to_selectable, compiler_metadata, recursion_in_column=recursion_in_column
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
    _update_table_for_blocks(table, node.predicates)
    return table



def _pull_up_node_blocks(node, child_node):
    node.predicates.extend(child_node.predicates)
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


def _create_final_query(node, query_path_to_selectable, compiler_metadata):
    # no need to adjust predicates, they are already
    columns = get_output_columns(node, query_path_to_selectable, compiler_metadata)
    # no predicates required,  since they are captured in the base CTE
    return _create_query(node, columns, None)


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


def _create_base_query(node, query_path_to_selectable, compiler_metadata):
    selection_columns = []
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
        selection_columns.append(column)
    selection_columns += node.link_columns
    predicates = [
        compiler_metadata.get_predicate_condition(node, predicate) for predicate in node.predicates
    ]
    return _create_query(node, selection_columns, predicates)


def _create_query(node, columns, predicates):
    query = select(columns, distinct=True).select_from(node.from_clause)
    if predicates is None:
        return query
    return query.where(and_(*predicates))
