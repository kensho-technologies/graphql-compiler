from sqlalchemy import select, and_, literal_column, cast, String, case


def emit_code_from_ir(sql_blocks, compiler_metadata):
    sql_query_tree = sql_blocks
    return _query_tree_to_query(sql_query_tree, compiler_metadata)


def _to_query_recursive(node, compiler_metadata, return_final_query, parent_cte=None, link_column=None):
    _collapse_query_tree(node, compiler_metadata)
    outer_link_column = None
    if node.relation.is_recursive:
        outer_link_column = _create_recursive_element(
            node, compiler_metadata, link_column, parent_cte
        )
    query = _create_base_query(node, compiler_metadata)
    _wrap_query_as_cte(node, query)
    recursive_selections = []
    for recursive_node in node.recursions:
        link_column = node.recursion_to_column[recursive_node]
        recursive_link_column = _to_query_recursive(
            recursive_node,compiler_metadata, return_final_query=False,
            parent_cte=node.table, link_column=link_column
        )
        recursive_selections.extend(recursive_node.selections)
        _join_to_recursive_node(node, link_column, recursive_node, recursive_link_column)
    # make sure selections point to the underlying CTE now
    node.selections = node.selections + recursive_selections
    if return_final_query:
        return _create_final_query(node, compiler_metadata)
    return outer_link_column


def _collapse_query_tree(node, compiler_metadata):
    # recursively collapse the children's trees
    for child_node in node.children_nodes:
        _collapse_query_tree(child_node, compiler_metadata)
    # create the current node's table
    _create_table(node, compiler_metadata)
    # ensure that columns required for recursion are present
    _create_links_for_recursions(node, compiler_metadata)
    for child_node in node.children_nodes:
        # pull up the childs SQL blocks
        _pull_up_node_blocks(node, child_node)
        # join to the child
        _join_to_node(node, child_node, compiler_metadata)


def _create_recursive_element(node, compiler_metadata, link_column, parent_cte):
    on_clause = compiler_metadata.get_on_clause(
        node.relation.relative_type, node.relation.edge_name, None
    )
    from_col, to_col = on_clause
    base_col = from_col
    primary_key = node.table.c[base_col]
    if node.relation.direction == 'in':
        from_col, to_col = to_col, from_col

    recursive_table = node.relation.get_table(compiler_metadata)
    table = recursive_table.alias()
    parent_cte_column = parent_cte.c[link_column.name]
    distinct_parent_column_query = select([parent_cte_column.label('link')],
                                          distinct=True).alias()
    anchor_query = (
        select([
            primary_key.label(from_col),
            primary_key.label(to_col),
            literal_column('0').label('__depth_internal_name'),
            cast(primary_key, String()).concat(',').label('path'),
        ], distinct=True)
            .select_from(
            node.table.join(distinct_parent_column_query,
                       primary_key == distinct_parent_column_query.c['link'])
        )
    )
    recursive_cte = anchor_query.cte(recursive=True)
    recursive_query = (
        select([
            table.c[from_col],
            recursive_cte.c[to_col],
            (recursive_cte.c['__depth_internal_name'] + 1).label('__depth_internal_name'),
            recursive_cte.c.path.concat(cast(table.c[from_col], String())).concat(
                ',').label('path'),
        ])
            .select_from(
            table.join(recursive_cte,
                       table.c[to_col] == recursive_cte.c[from_col])
        ).where(and_(
            recursive_cte.c['__depth_internal_name'] < node.relation.recursion_depth,
            case(
                [
                    (recursive_cte.c.path.contains(cast(table.c[from_col], String())), 1)
                ],
                else_=0
            ) == 0
        ))
    )
    recursion_combinator = compiler_metadata.db_backend.recursion_combinator
    recursive_query = getattr(recursive_cte, recursion_combinator)(recursive_query)
    pk = node.table.c[base_col]
    node.from_clause = node.from_clause.join(recursive_query,
                                             pk == recursive_query.c[from_col])
    link_column = recursive_query.c[to_col].label(None)
    node.add_link_column(link_column)
    outer_link_column = link_column
    return outer_link_column


def _create_table(node, compiler_metadata):
    table = node.relation.get_table(compiler_metadata).alias()
    _reference_table(node, table)


def _pull_up_node_blocks(node, child_node):
    node.selections.extend(child_node.selections)
    node.predicates.extend(child_node.predicates)
    node.recursions.extend(child_node.recursions)
    for recursion, link_column in child_node.recursion_to_column.items():
        node.recursion_to_column[recursion] = link_column
    node.link_columns.extend(child_node.link_columns)


def _join_to_node(node, child_node, compiler_metadata):
    # outer table is the current table, inner table is the child's
    onclause = child_node.relation.get_on_clause(node.table, child_node.table,
                                                 compiler_metadata)

    if onclause is None:
        # should only happen at root
        return
    if child_node.relation.in_optional:
        node.from_clause = node.from_clause.outerjoin(
            child_node.from_clause, onclause=onclause
        )
        return
    node.from_clause = node.from_clause.join(
        child_node.from_clause, onclause=onclause
    )


def _reference_table(node, table):
    node.table = table
    node.from_clause = table
    _update_table_for_blocks(table, node.selections)
    _update_table_for_blocks(table, node.predicates)


def _update_table_for_blocks(table, blocks):
    for block in blocks:
        block.table = table


def _query_tree_to_query(node, compiler_metadata):
    query = _to_query_recursive(node, compiler_metadata, return_final_query=True)
    return query


def _create_link_for_recursion(node, recursion, compiler_metadata):
    on_clause = compiler_metadata.get_on_clause(
        recursion.relation.relative_type, recursion.relation.edge_name, None
    )
    from_col, to_col = on_clause
    link_column = node.table.c[from_col]
    node.recursion_to_column[recursion] = link_column
    node.add_link_column(link_column)


def _create_links_for_recursions(node, compiler_metadata):
    if len(node.recursions) == 0:
        return
    for recursion in node.recursions:
        _create_link_for_recursion(node, recursion, compiler_metadata)


def _join_to_recursive_node(node, link_column, recursion, recursive_link_column):
    current_cte_column = node.table.c[link_column.name]
    recursive_cte_column = recursion.table.c[recursive_link_column.name]
    node.from_clause = node.from_clause.join(
        recursion.from_clause, onclause=current_cte_column == recursive_cte_column
    )


def _create_final_query(node, compiler_metadata):
    # no need to adjust predicates, they are already applied
    columns = [selection.get_selection_column(compiler_metadata) for selection in
               node.selections]
    # no predicates required,  since they are captured in the base CTE
    return create_query(node, columns, None)


def _wrap_query_as_cte(node, query):
    cte = query.cte()
    node.from_clause = cte
    node.table = cte
    _update_table_for_blocks(cte, node.selections)
    for selection in node.selections:
        # CTE has assumed the alias columns, make sure the selections know that
        selection.rename()


def _create_base_query(node, compiler_metadata):
    selection_columns = [selection.get_selection_column(compiler_metadata) for selection in
                         node.selections]
    selection_columns += node.link_columns
    predicates = [predicate.to_predicate_statement(compiler_metadata) for predicate in
                  node.predicates]
    query = create_query(node, selection_columns, predicates)
    return query


def create_query(node, columns, predicates):
    query = (
        select(columns, distinct=True)
            .select_from(node.from_clause)
    )
    if predicates is None:
        return query
    return query.where(and_(*predicates))
