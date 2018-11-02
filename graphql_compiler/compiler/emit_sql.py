# Copyright 2018-present Kensho Technologies, LLC.
"""Recursively converts a SqlNode tree to an executable SQLAlchemy query.

The complexity here comes from @recurse directives, which become the Recurse blocks in the compiler
IR. To match the semantics of the GraphQL compiler, recursive common table expressions (CTEs) are
required. SQL backends are good at pushing predicates down into subqueries and CTEs, however this
does not generally extend to recursive CTEs. This means that it is very easy to write a recursive
CTE that will scan an entire table, even if all but a few starting points of that recursion are
eventually discarded later.


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
recursion depth per the compiler's semantics.


WITH RECURSIVE recursive_cte AS (
    -- anchor query
    SELECT DISTINCT
        animal_parentof.animal_id AS animal_id,
        animal_parentof.parentof_id AS parentof_id,
        0 AS __depth_internal_name
    FROM
        animal_parentof
        JOIN base_cte ON base_cte.link_column == animal_parentof.animal_id
    UNION ALL
    -- recursive query
    SELECT
        recursive_cte.animal_id,
        animal_parentof.parentof_id,
        -- increment the depth
        recursive_cte.__depth_internal_name + 1 AS __depth_internal_name
    FROM
        animal_parentof
        JOIN recursive_cte ON recursive_cte.parentof_id = animal_parentof.animal_id
    WHERE
        recursive_cte.__depth_internal_name < :depth -- depth from recurse directive
)

4. JOIN the recursive clause to the recursive table (here animal_parentof) to create output columns,
and join back to base cte to carry along tag columns.
WITH recursive_cte_outputs AS (
    SELECT
        animal.name AS animal_or_descendant_name,
        anon_3.animal_id AS recursive_link_column -- anonymously aliased column
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
from collections import namedtuple

import six
from sqlalchemy import Column, and_, bindparam, literal_column, select
from sqlalchemy.sql import expression as sql_expressions
from sqlalchemy.sql.elements import BindParameter

from graphql_compiler import exceptions
from graphql_compiler.compiler import blocks, expressions
from graphql_compiler.compiler.helpers import INBOUND_EDGE_DIRECTION
from graphql_compiler.compiler.ir_lowering_sql import constants


# The compilation context holds state that changes during compilation as the tree is traversed
CompilationContext = namedtuple('CompilationContext', (
    'query_path_to_selectable',
    'query_path_to_from_clause',
    'query_path_to_location_info',
    'query_path_to_recursion_in_columns',
    'query_path_to_recursion_out_columns',
    'query_path_to_filter',
    'query_path_to_output_fields',
    'query_path_field_renames',
    'query_path_to_tag_fields',
    'join_filters',
    'compiler_metadata',
))

# A many-to-many join is a SQL JOIN that requires an intermediate junction table to fully resolve
ManyToManyJoin = namedtuple('JunctionJoinExpression', (
    'join_to_junction_expression',
    'junction_table',
    'join_from_junction_expression'
))

# The recursive clause requires a large collection of metadata for construction
RecursiveClauseMetadata = namedtuple('RecursiveClauseMetadata', (
    'base_column',
    'base_column_name',
    'left_column_name',
    'right_column_name',
    'recursive_table',
    'parent_cte_column',
    'recursive_selectable',
))


def emit_code_from_ir(sql_query_tree, compiler_metadata):
    """
    Return a SQLAlchemy selectable from a passed SQLQueryTree based on the supplied compilation
    metadata.
    Args:
        sql_query_tree: SqlQueryTree, tree representation of the query to emit.
        compiler_metadata: CompilerMetadata, SQLAlchemy specific metadata.

    Returns:

    """
    context = CompilationContext(
        query_path_to_selectable={},
        query_path_to_from_clause={},
        query_path_to_recursion_in_columns={},
        query_path_to_recursion_out_columns={},
        query_path_field_renames={},
        query_path_to_tag_fields=sql_query_tree.query_path_to_tag_fields,
        query_path_to_location_info=sql_query_tree.query_path_to_location_info,
        query_path_to_filter=sql_query_tree.query_path_to_filter,
        query_path_to_output_fields=sql_query_tree.query_path_to_output_fields,
        join_filters=[],
        compiler_metadata=compiler_metadata,
    )
    return _query_tree_to_query(sql_query_tree.root, context, None, None)


def _query_tree_to_query(node, context, recursion_link_column, outer_cte):
    """
    Recursively convert this node into its corresponding SQL representation.

    The steps to do so are:

    1. Visit and join all non-recursive children nodes to the current node.
        a. Create recursive link columns for any (currently) skipped recursive child nodes.
    2. Materialize current query as a CTE.
        a. Output any columns required for tagging or recursion from this CTE.
    3. Visit and join all previously skipped recursive child nodes of the current node,
       passing current query CTE.
    4. Return final query, omitting tag columns and recursive link columns.

    Args:
        node: The current node to recursively convert to SQL.
        context: CompilationContext, compilation specific metadata
        recursion_link_column: Optional, column to the link the current recursive node to.
        outer_cte: Optional, CTE to use in construction of recursive clause of current recursive
                   node.

    Returns:
        SQLAlchemy selectable, if called from tree root or
        SQLAlchemy column, the column to link to recursive clauses with.

    """
    # Step 1: Collapse query tree, ignoring recursive nodes
    visited_nodes = _flatten_and_join_nonrecursive_nodes(node, context)
    # Step 3: Create the recursive element (only occurs on a recursive call of this function)
    recursion_out_column = _create_recursive_clause(node, context, recursion_link_column, outer_cte)
    # Step 2: Materialize query as a CTE.
    cte = _create_query(node, is_final_query=False, context=context).cte()
    # Output fields from individual tables become output fields from the CTE
    _update_context_paths(node, visited_nodes, cte, context)
    # Step 3: collapse and return recursive node trees, passing the CTE to the recursive element
    _flatten_and_join_recursive_nodes(node, cte, context)
    if isinstance(node.block, blocks.QueryRoot):
        # Step 4: filters have already been applied within the CTE, no need to reapply
        # tag columns and recursive link columns do not need to be output
        return _create_query(node, is_final_query=True, context=context)
    else:
        return recursion_out_column


def _flatten_and_join_recursive_nodes(node, cte, context):
    """Join recursive child nodes of the current node to the current node.

    References in the compilation context that were pointing to the recursive node
    are flattened to point to the current node.

    Args:
        node: The current node.
        cte: The CTE representing the current query of the node.
        context: CompilationContext containing required columns to link the CTE to the
                 recursive clause.

    Returns: None, the recursive clause is joined to the CTE.

    """
    for recursive_node in node.recursions:
        # retrieve the column that will be used to attach the outer CTE to the recursive element
        recursion_in_column = context.query_path_to_recursion_in_columns[
            recursive_node.query_path]
        recursion_sink_column = _query_tree_to_query(
            recursive_node, context, recursion_link_column=recursion_in_column, outer_cte=cte
        )
        _flatten_output_fields(node, recursive_node, context)
        join_expression = _get_recursive_node_join_expression(
            node, recursive_node, recursion_in_column, recursion_sink_column, context)
        _join_nodes(node, recursive_node, join_expression, context)


def _update_context_paths(node, visited_nodes, cte, context):
    """ Update the visited node's paths to point to a constructed CTE. This ensures that things
    like outputs pointing previously to the selectable of the visited node now point to the CTE
    with that output.

    Args:
        node: The current node.
        visited_nodes: The nodes that were visited while generating this nodes CTE.
        cte: The CTE representing the query at the current node.
        context: CompilationContext that needs to be updated.

    Returns:

    """
    # this should be where the tag fields get updated, so that they continue to propagate
    context.query_path_to_from_clause[node.query_path] = cte
    for visited_node in visited_nodes:
        context.query_path_to_selectable[visited_node.query_path] = cte


def _flatten_and_join_nonrecursive_nodes(node, context):
    """Join non-recursive child nodes to parent, flattening child's references.
    Args:
        node: The current node to flatten and join to.
        context: CompilationContext containing locations and metadata related to the ongoing
                 compilation.

    Returns: List[SqlNode], list of non-recursive nodes visited from this node.

    """
    # recursively collapse the children's trees
    visited_nodes = [node]
    for child_node in node.children_nodes:
        nodes_visited_from_child = _flatten_and_join_nonrecursive_nodes(child_node, context)
        visited_nodes.extend(nodes_visited_from_child)
    # create the current node's table
    _create_and_reference_table(node, context)
    # ensure that columns required to link recursion are present
    _get_links_for_recursive_clauses(node, context)
    for child_node in node.children_nodes:
        _flatten_node(node, child_node, context)
        join_expression = _get_node_join_expression(node, child_node, context)
        _join_nodes(node, child_node, join_expression, context)
    return visited_nodes


def _get_node_selectable(node, context):
    """Return the selectable (Table, CTE) associated with the node."""
    query_path = node.query_path
    if query_path not in context.query_path_to_selectable:
        raise AssertionError(u'Unable to find selectable for query path {}'.format(query_path))
    selectable = context.query_path_to_selectable[query_path]
    return selectable


def _get_node_from_clause(node, context):
    """Return the FromClause associated with the node.

    A FromClause differs from a Selectable mainly in that the FromClause is a partially constructed
    component of a query, whereas the Selectable is a complete entity with outputs and filters.
    """
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
    """Get the direction of a Traverse/Recurse block."""
    if not isinstance(block, (blocks.Traverse, blocks.Recurse)):
        raise AssertionError(u'Attempting to get direction of block of type "{}"'.format(
            type(block)))
    return block.direction


def _get_block_edge_name(block):
    """Get the edge name associated with a Traverse/Recurse block."""
    if not isinstance(block, (blocks.Traverse, blocks.Recurse)):
        raise AssertionError(u'Attempting to get edge name of block of type "{}"'.format(
            type(block)))
    return block.edge_name


def _create_recursive_clause(node, context, out_link_column, outer_cte):
    """Create a recursive clause for a Recurse block.

    Args:
        node: The root of the recursion
        context: CompilationContext, contains tables and selectables required for the construction
                 of the recursive clause.
        out_link_column: The column of the outer CTE to link to.
        outer_cte: CTE representing the query of the nodes parent, used in construction
                   of the recursive clause.

    Returns: None, if current block is not Recursive OR SQLAlchemy column, the column to join
             the outer CTE back to the recursive clause.

    """
    if not isinstance(node.block, blocks.Recurse):
        return None
    if out_link_column is None or outer_cte is None:
        raise AssertionError(
            u'The recursive clause requires an on outer CTE and the column of this CTE to link to.')
    # setup the column names and selectables required to construct the recursive element
    recursive_metadata = _get_recursive_element_metadata(context, node, out_link_column, outer_cte)
    # create the recursive element
    recursive_query = _create_recursive_element(node, recursive_metadata, outer_cte, context)
    # grab the column necessary to link the recursive element to the outer_cte
    recursive_link_column = _get_column(
        recursive_query, recursive_metadata.right_column_name).label(None)
    context.query_path_to_recursion_out_columns[node.query_path] = recursive_link_column
    return recursive_link_column


def _create_recursive_element(node, recursive_metadata, outer_cte, context):
    """Generate the SQL for the recursive clause.

    For details on the SQL generated here, see parts 3 and 4 of the file docstring.

    Args:
        node: The current recursive node.
        recursive_metadata: The metadata to use in constructing this recursive clause.
        outer_cte: The CTE containing the query of the parent node and its non-recursive children.
        context: Global compilation state and metadata.

    Returns: SQLAlchemy Column, the column required to link the created recursive clause back to the
                                parent CTE.
    """
    anchor_query = (
        select(
            [
                recursive_metadata.base_column.label(recursive_metadata.left_column_name),
                recursive_metadata.base_column.label(recursive_metadata.right_column_name),
                literal_column('0').label(constants.DEPTH_INTERNAL_NAME),
            ],
            # take DISTINCT to ensure the anchor clause is as small as possible. This is allowable
            # because the recursive clause is later joined back to the original CTE.
            distinct=True)
        .select_from(
            recursive_metadata.recursive_selectable.join(
                outer_cte,
                recursive_metadata.base_column ==
                recursive_metadata.parent_cte_column
            )
        )
    )
    recursive_cte = anchor_query.cte(recursive=True)
    recursive_query = (
        select(
            [
                _get_column(
                    recursive_metadata.recursive_table, recursive_metadata.left_column_name
                ),
                _get_column(
                    recursive_cte, recursive_metadata.right_column_name
                ),
                ((_get_column(recursive_cte, constants.DEPTH_INTERNAL_NAME) + 1)
                    .label(constants.DEPTH_INTERNAL_NAME)),
            ]
        )
        .select_from(
            recursive_metadata.recursive_table.join(
                recursive_cte,
                _get_column(
                    recursive_metadata.recursive_table, recursive_metadata.right_column_name) ==
                _get_column(recursive_cte, recursive_metadata.left_column_name)
            )
        )
        .where(_get_column(recursive_cte, constants.DEPTH_INTERNAL_NAME) < node.block.depth)
    )
    # Combine the anchor query with the recursive clause using the UNION ALL operation.
    recursive_query = recursive_cte.union_all(recursive_query)
    from_clause = _get_node_from_clause(node, context)
    from_clause = from_clause.join(
        recursive_query,
        _get_column(recursive_metadata.recursive_selectable, recursive_metadata.base_column_name) ==
        _get_column(recursive_query, recursive_metadata.left_column_name)
    )
    from_clause = from_clause.join(
        outer_cte,
        _get_column(recursive_query, recursive_metadata.right_column_name) ==
        recursive_metadata.parent_cte_column
    )
    context.query_path_to_from_clause[node.query_path] = from_clause
    return recursive_query


def _get_recursive_element_metadata(context, node, out_link_column, outer_cte):
    """Compute requisite metadata based on the JOIN type to construct a recursive clause."""
    recursive_selectable = _get_node_selectable(node, context)
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
    base_column = _get_column(recursive_selectable, base_column_name)
    if _get_block_direction(node.block) == INBOUND_EDGE_DIRECTION:
        left_column_name, right_column_name = right_column_name, left_column_name
    parent_cte_column = _get_column(outer_cte, out_link_column.name)
    return RecursiveClauseMetadata(
        base_column=base_column,
        base_column_name=base_column_name,
        left_column_name=left_column_name,
        right_column_name=right_column_name,
        parent_cte_column=parent_cte_column,
        # The recursive table differs from the recursive selectable when a many-to-many JOIN
        # is involved, in which case the recursive_table is the table of the recursive node,
        # and the recursive_selectable is the many-to-many junction table
        recursive_table=recursive_table,
        recursive_selectable=recursive_selectable,
    )


def _create_and_reference_table(node, context):
    """Create an aliased table for a node, and update the relevant Selectable and FromClause
    global state.

    Args:
        node: The current SqlNode.
        context: Global compilation state and metadata.

    Returns: SqlAlchemy table, the newly aliased table.
    """

    schema_type = _get_schema_type_name(node, context)
    table = context.compiler_metadata.get_table(schema_type).alias()
    context.query_path_to_from_clause[node.query_path] = table
    context.query_path_to_selectable[node.query_path] = table
    return table


def _flatten_node(parent_node, child_node, context):
    """Flatten a child node's outputs, filters, and recursions onto its parent.

    Updates global context for children output and filter locations to be associated with the
    parent location, and adds any child recursive nodes to the parent.

    Args:
        parent_node: The parent SqlNode to update with the child SqlNode.
        child_node: The child SqlNode to pull filters, outputs and recursive nodes from.
        context: Global compilation state and metadata.

    Returns: None, CompilationContext is updated.

    """
    _flatten_output_fields(parent_node, child_node, context)
    parent_node.recursions.extend(child_node.recursions)
    del child_node.recursions[:]
    if child_node.query_path in context.query_path_to_filter:
        context.query_path_to_filter.setdefault(parent_node.query_path, []).extend(
            context.query_path_to_filter[child_node.query_path]
        )
        del context.query_path_to_filter[child_node.query_path]


def _flatten_output_fields(parent_node, child_node, context):
    """Flatten child node output and tag fields onto parent node

    This occurs after a JOIN operation has been performed.

    Args:
        parent_node: The parent SqlNode that will receive the output and tag fields.
        child_node: The child SqlNode to pull output and tag fields from.
        context: Global compilation state and metadata.

    Returns: None, updates global CompilationContext.

    """
    if child_node.query_path in context.query_path_to_tag_fields:
        context.query_path_to_tag_fields.setdefault(parent_node.query_path, []).extend(
            context.query_path_to_tag_fields[child_node.query_path])
    if child_node.query_path not in context.query_path_to_output_fields:
        return
    child_output_fields = context.query_path_to_output_fields[child_node.query_path]
    parent_output_fields = context.query_path_to_output_fields.setdefault(parent_node.query_path, {})
    for field_alias, (field, field_type, is_renamed) in six.iteritems(child_output_fields):
        parent_output_fields[field_alias] = (field, field_type, is_renamed)
    del context.query_path_to_output_fields[child_node.query_path]


def _join_nodes(parent_node, child_node, join_expression, context):
    """Join two nodes and update compilation context.

    The rule of thumb for mapping an edge to a JOIN statement is that if the edge is required,
    an INNER JOIN should be used, and if the edge is optional a LEFT JOIN should be used. This
    applies to all tables involved in both direct and many-to-many JOINs, with one notable
    exception.

    When an edge is required within an optional scope, the compiler semantics state that if the
    outer optional edge is present, but the inner required edge is not, this result should be
    excluded. For example with the GraphQL query:
    {
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
                out_Animal_ParentOf {
                    name @output(out_name: "grandchild_name")
                }
            }
        }
    }

    An animal that has a child (satisfying the first optional ParentOf edge), but where that child
    has no children (failing to satisfy the second required ParentOf edge) should produce no result.

    Using nested INNER JOINs here from the outer LEFT JOIN, like

    SELECT
        animal.name as name,
        child.name as child_name,
        grandchild.name as grandchild_name
    FROM animal
    LEFT JOIN (
        animal AS child
        INNER JOIN (
            animal as grandchild
        ) ON child.parentof_id = grandchild.animal_id
    ) ON animal AS child ON animal.parentof_id = child.animal_id

    will have a NULL value returned for the grandchild.name property. The LEFT JOIN condition is
    fulfilled but the INNER JOIN condition is not, which doesn't exclude the result but rather
    includes it with a NULL value.

    To get the correct semantics, the result when the INNER JOIN condition is not fulfilled needs to
    be filtered out. This is done explicitly by replacing the INNER JOIN with a LEFT JOIN, and then
    applying the JOIN condition in the WHERE clause to the rows that are non-null from the
    LEFT JOIN. For this example this looks like:

    SELECT
        animal.name as name,
        child.name as child_name,
        grandchild.name as grandchild_name
    FROM animal
    LEFT JOIN (
        animal AS child
        INNER JOIN (
            animal as grandchild
        ) ON child.parentof_id = grandchild.animal_id
    ) ON animal AS child ON animal.parentof_id = child.animal_id
    WHERE
        child.animal_id IS NULL
        OR
        child.parentof_id = grandchild.animal_id -- reapply JOIN condition in WHERE clause

    The null check ensures that the filter is only applied iff the LEFT JOIN condition is actually
    satisfied.
    """
    location_info = context.query_path_to_location_info[child_node.query_path]
    parent_location_info = context.query_path_to_location_info[parent_node.query_path]
    within_optional_scope = location_info.optional_scopes_depth > 0
    current_node_required = (
            location_info.optional_scopes_depth == parent_location_info.optional_scopes_depth)
    parent_from_clause = _get_node_from_clause(parent_node, context)
    child_from_clause = _get_node_from_clause(child_node, context)
    if within_optional_scope:
        # use LEFT JOINs
        if isinstance(join_expression, ManyToManyJoin):
            parent_from_clause = parent_from_clause.outerjoin(
                join_expression.junction_table,
                onclause=join_expression.join_to_junction_expression)
            parent_from_clause = parent_from_clause.outerjoin(
                child_from_clause, onclause=join_expression.join_from_junction_expression)

            if current_node_required:
                # special case (see docstring), capture the JOIN expressions in context to later be
                # used in the WHERE clause
                parent_selectable = _get_node_selectable(parent_node, context)
                outer_primary_key = _get_selectable_primary_key(parent_selectable)
                context.join_filters.append(
                    sql_expressions.or_(
                        outer_primary_key == None,
                        join_expression.join_to_junction_expression
                    )
                )
                junction_table_primary_key = join_expression.join_to_junction_expression.right
                if not any(junction_table_primary_key is column for column in join_expression.junction_table.c):
                    raise AssertionError(
                        u'The right side of the join expression "{}" between parent "{}" and '
                        u'junction table "{}" is expected to come from the junction table.'.format(
                            join_expression.join_to_junction_expression, parent_selectable,
                            join_expression.junction_table
                        ))
                context.join_filters.append(
                    sql_expressions.or_(
                        junction_table_primary_key == None,
                        join_expression.join_from_junction_expression
                    )
                )

        else:
            parent_from_clause = parent_from_clause.outerjoin(
                child_from_clause, onclause=join_expression)
            if current_node_required:
                # special case (see docstring), capture the JOIN expression in context to later be
                # used in the WHERE clause
                parent_selectable = _get_node_selectable(parent_node, context)
                outer_primary_key = _get_selectable_primary_key(parent_selectable)
                context.join_filters.append(
                    sql_expressions.or_(
                        outer_primary_key == None,
                        join_expression
                    )
                )
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


def _get_links_for_recursive_clauses(node, context):
    """Ensure that the columns to link to all children recursive clauses will be included in the
    CTE's outputs.
    """
    for recursive_node in node.recursions:
        link_column = _get_link_for_recursive_clause(recursive_node, context)
        context.query_path_to_recursion_in_columns[recursive_node.query_path] = link_column


def _get_link_for_recursive_clause(recursive_node, context):
    """Get the column necessary to link a recursive clause to its parent CTE"""
    parent_selectable = _get_node_selectable(recursive_node.parent, context)
    # pre-populate the recursive nodes selectable for the purpose of computing the join
    _create_and_reference_table(recursive_node, context)
    join_expression = _get_node_join_expression(recursive_node.parent, recursive_node, context)
    # the left side of the expression is the column from the node that is later needed to join to
    recursion_in_col = None
    if isinstance(join_expression, ManyToManyJoin):
        recursion_in_col = _get_column(
            parent_selectable, join_expression.join_to_junction_expression.left.name)
    elif isinstance(join_expression, sql_expressions.BinaryExpression):
        recursion_in_col = _get_column(parent_selectable, join_expression.right.name)
    else:
        raise AssertionError(
            u'Unknown JOIN expression of type "{}" encountered for recursive link.'.format(
                type(join_expression)))
    return recursion_in_col


def _get_output_columns(node, context):
    """Get the output columns required by the query.

    Args:
        node: The current SqlNode.
        context: Global compilation state and metadata.

    Returns: List[Column], list of SqlAlchemy columns to output for this query.
    """
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
                    u'Column with name "{}" was not found on table "{}"'.format(
                        field_name, selectable.original))
            column = column.label(field_alias)
            output_fields[field_alias] = (field, field_type, True)
            field_renames = context.query_path_field_renames.setdefault(
                field.location.query_path, {})
            field_renames[field_name] = field_alias
        columns.append(column)
    return columns


def _get_tag_output_columns(node, context):
    """Get columns required to for @tag directives.

    Args:
        node: The current SqlNode.
        context: Global context containing compiler state and metadata.

    Returns: List[Column], List of SQLAlchemy columns to output.
    """

    tag_output_columns = []
    if node.query_path not in context.query_path_to_tag_fields:
        return tag_output_columns
    for tag_field in context.query_path_to_tag_fields[node.query_path]:
        selectable = context.query_path_to_selectable[tag_field.location.query_path]
        field_name = tag_field.location.field
        column = _get_column(selectable, field_name).label(None)
        tag_output_columns.append(column)
        field_renames = context.query_path_field_renames.setdefault(
            tag_field.location.query_path, {})
        field_renames[field_name] = column.name
    return tag_output_columns


def _create_query(node, is_final_query, context):
    """Create a query from a SqlNode.

    If this query is the final query, filters do not need to be applied, and intermediate recursive
    link columns and tag columns do not need to be included in output.
    """
    # filters are computed before output columns, so that tag columns can be resolved before any
    # renames occur for columns involved in output
    filter_clauses = []
    if not is_final_query:
        # filters do not need to be applied to the final query, they exist in the CTE
        filter_clauses.extend(_get_filter_clauses(node, context))
    output_columns = _get_output_columns(node, context)
    if not is_final_query:
        # tag output columns do not need to be applied to the final query, they exist in the CTE
        tag_columns = _get_tag_output_columns(node, context)
        output_columns.extend(tag_columns)
    if not is_final_query:
        # recursive link columns should not appear in the final query
        recursive_output_columns = _get_recursive_output_columns(node, context)
        output_columns.extend(recursive_output_columns)
    from_clause = _get_node_from_clause(node, context)
    query = select(output_columns).select_from(from_clause)
    # an empty list of filters will result in no attached WHERE clause
    return query.where(and_(*filter_clauses))


def _get_filter_clauses(node, context):
    """Get filters required by any JOIN expressions and return along with GraphQL filter predicates
    converted to SQL.

    Args:
        node: The current SqlNode.
        context: Global context containing compiler state and metadata.

    Returns: List[Expression], list of SQLAlchemy expressions to include in the query's
                               WHERE clause.

    """
    filter_clauses = _get_and_cleanup_join_filters(context)
    if node.query_path in context.query_path_to_filter:
        filter_clauses.extend(
            _transform_filter_to_sql(filter_block, filter_query_path, context)
            for filter_block, filter_query_path in context.query_path_to_filter[node.query_path]
        )
    return filter_clauses


def _get_recursive_output_columns(node, context):
    """Get columns into and out of recursions, and ensure they are included for output.

    Args:
        node: SqlNode, node that may be recursive itself or the root of one or more recursions.
        context:

    Returns: List[Column], list of SQLAlchemy columns required to correctly attach the recursive
                           clause
    """
    recursive_output_columns = []
    # for every recursion that is a child of this node, include the link column to the child
    # recursion in this node's query's outputs
    for recursive_node in node.recursions:
        if recursive_node.query_path not in context.query_path_to_recursion_in_columns:
            raise AssertionError(
                u'Recursive node at query path {} is expected to have an inbound column to '
                u'link from in {}.'.format(
                    recursive_node.query_path, context.query_path_to_recursion_in_columns))

        in_col = context.query_path_to_recursion_in_columns[recursive_node.query_path]
        recursive_output_columns.append(in_col)
    # If this node is completing a recursion, include the outward column in this node's outputs
    if isinstance(node.block, blocks.Recurse):
        if node.query_path not in context.query_path_to_recursion_out_columns:
            raise AssertionError(
                u'Recursive clause at query path {} is expected to have an outbound column to link '
                u'to in {}.'.format(node.query_path, context.query_path_to_recursion_out_columns))
        out_col = context.query_path_to_recursion_out_columns[node.query_path]
        recursive_output_columns.append(out_col)
    return recursive_output_columns


def _get_and_cleanup_join_filters(context):
    """Return a copy of the CompilationContext join filters and return them.

    Clears all copied filters from the global CompilationContext.

    Args:
        context: Global compilation state and metadata.

    Returns: List[Expression], list of SQLAlchemy expressions.

    """
    filter_clauses = [filter for filter in context.join_filters]
    del context.join_filters[:]
    return filter_clauses


def _transform_filter_to_sql(filter_block, filter_query_path, context):
    """Transform a Filter block to its corresponding SQLAlchemy expression.
    Args:
        filter_block: Filter, the Filter block to transform.
        filter_query_path: The location the Filter block applies to.
        context: Global compilation state and metadata.

    Returns: SQLAlchemy expression, equivalent to the Filter.predicate expression.

    """
    filter_location_info = context.query_path_to_location_info[filter_query_path]
    filter_selectable = context.query_path_to_selectable[filter_query_path]
    expression = filter_block.predicate
    return _expression_to_sql(expression, filter_selectable, filter_location_info, context)


def _expression_to_sql(expression, selectable, location_info, context):
    """Recursively transform a compiler expression corresponding to a Filter block predicate to its
    SQLAlchemy expression representation.

    Args:
        expression: The compiler expression to transform.
        selectable: The selectable the Filter predicate applies to
        location_info: LocationInfo object corresponding to the location of the Filter block.
        context: CompilationContext, contains metadata related to tags and any field renames that
                 have occurred.

    Returns: SQLAlchemy expression

    """
    if isinstance(expression, expressions.LocalField):
        column_name = expression.field_name
        column = _get_column(selectable, column_name)
        return column
    if isinstance(expression, expressions.Variable):
        variable_name = expression.variable_name
        if variable_name.startswith(u'$'):
            variable_name = variable_name[1:]
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
    """Get a column by name from the selectable, raise an AssertionError if not found."""
    column = _try_get_column(selectable, column_name)
    if column is None:
        raise AssertionError(
            u'Column "{}" not found in selectable "{}". Columns present are {}'.format(
                column_name, selectable.original, [col.name for col in selectable.c]))
    return column


def _try_get_column(selectable, column_name):
    """Attempt to get a column by name from the selectable."""
    if not hasattr(selectable, 'c'):
        raise AssertionError(u'Selectable "{}" does not have a column collection.'.format(
            selectable))
    return selectable.c.get(column_name, None)


def _get_recursive_node_join_expression(node, recursive_node, in_column, out_column, context):
    """Determine the join expression to join an outer table to a recursive clause.

    In this case there is a constructed join between the two nodes with an aliased column that
    breaks the naming convention expected by _get_node_join_expression.
    """
    selectable = _get_node_selectable(node, context)
    recursive_selectable = _get_node_selectable(recursive_node, context)
    return _try_get_selectable_join_expression(
        selectable, in_column.name, recursive_selectable, out_column.name)


def _get_node_join_expression(outer_node, inner_node, context):
    """Determine the join expression to join the outer node to the inner node.

    For both cases below it is assumed that columns used for an edge correspond to that edge's
    components, eg edge Animal_Eats is expected to be comprised of columns animal_id and eats_id.

    The process to determine this join expression is as follows:
    1. Attempt to resolve the join expression as a many-many edge.
    2. If there are no results from (1), look for a direct join expression between the two tables.

    Args:
        outer_node: The source SqlNode of the edge.
        inner_node: The sink SqlNode of the edge.
        context: Global compilation state and metadata.

    Returns: SQLAlchemy expression corresponding to the onclause of the JOIN statement.
    """
    # Attempt to resolve via case (1)
    join_expression = _try_get_many_to_many_join_expression(outer_node, inner_node, context)
    if join_expression is not None:
        return join_expression
    # No results, attempt to resolve via case (2)
    return _get_direct_join_expression(outer_node, inner_node, context)


def _get_direct_join_expression(outer_node, inner_node, context):
    """Get a direct join expression between the selectables of two nodes.

    A direct JOIN expression is one that does not require an intermediate junction table to resolve.
    The foreign key exists on one of the tables of the relationship and points to the other.
    Args:
        outer_node: The source SqlNode of the edge.
        inner_node: The sink SqlNode of the edge.
        context: Global compilation state and metadata.

    Returns: JOIN expression, if found, raises GraphQLCompilationError otherwise.

    """
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
    natural_join_expression = _try_get_selectable_join_expression(
        outer_selectable, outer_column_name, inner_selectable, inner_column_name)
    if natural_join_expression is not None:
        return natural_join_expression
    # The inverse join direction is Table A <FK- Table B, with table B holding the foreign key
    inverse_join_expression = _try_get_selectable_join_expression(
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
    """Attempt to resolve a join condition that uses an underlying many-many junction table.

    To do so, one the following must hold:
        - There is a table of the correct edge name, eg. for an edge out_Animal_FriendsWith,
        there is a table of name "animal_friendswith".
        - there is a table of the correct edge name, with a type suffix. eg. for an edge
        out_Animal_Eats of union type [FoodOrSpecies] that is coerced to Food in the given
        query context, there is a table of name "animal_eats_food"
        - If both of these tables exist, a GraphQLCompilationError is raised.
        context:

    Args:
        outer_node: The source SqlNode of the edge.
        inner_node: The sink SqlNode of the edge.
        context: Global compilation state and metadata.

    Returns: ManyToMany JOIN expression, if resolved, None otherwise.

    """
    outer_selectable = _get_node_selectable(outer_node, context)
    inner_selectable = _get_node_selectable(inner_node, context)
    edge_name = _get_block_edge_name(inner_node.block)
    outer_column_name, inner_column_name = _get_column_names_for_edge(edge_name)

    target_type_name = None
    if _get_block_direction(inner_node.block) == INBOUND_EDGE_DIRECTION:
        target_type_name = _get_schema_type_name(outer_node, context)
    else:
        target_type_name = _get_schema_type_name(inner_node, context)

    short_junction_table_name = u'{junction_table_name}'.format(junction_table_name=edge_name)
    has_short_table_name = context.compiler_metadata.has_table(short_junction_table_name)
    long_junction_table_name = u'{junction_table_name}_{target_type_name}'.format(
            junction_table_name=edge_name, target_type_name=target_type_name
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
    outer_primary_key = _get_selectable_primary_key(outer_selectable)
    inner_primary_key = _get_selectable_primary_key(inner_selectable)
    outer_pk_name = outer_primary_key.name
    inner_pk_name = inner_primary_key.name
    direction = _get_block_direction(inner_node.block)
    if direction == INBOUND_EDGE_DIRECTION:
        inner_column_name, outer_column_name = outer_column_name, inner_column_name
    join_to_junction_expression = _try_get_selectable_join_expression(
        outer_selectable, outer_pk_name, junction_table, inner_column_name)
    join_from_junction_expression = _try_get_selectable_join_expression(
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
        join_to_junction_expression=join_to_junction_expression,
        junction_table=junction_table,
        join_from_junction_expression=join_from_junction_expression,
    )


def _get_selectable_primary_key(selectable):
    """Get a selectable's primary key.

    The compiler requires that the primary key be non-composite, i.e. that the primary key is
    comprised of only one column.
    """
    if len(selectable.primary_key) != 1:
        raise exceptions.GraphQLCompilationError(
            u'Selectable "{}" is expected to have exactly one primary key.'.format(
                selectable.original))
    return selectable.primary_key[0]


def _get_column_names_for_edge(edge_name):
    """Return the expected column names for the given edge."""
    inner_prefix, outer_prefix = edge_name.lower().split('_')
    outer_column_name = u'{column_prefix}_id'.format(column_prefix=outer_prefix)
    inner_column_name = u'{column_prefix}_id'.format(column_prefix=inner_prefix)
    return outer_column_name, inner_column_name


def _try_get_selectable_join_expression(outer_selectable, outer_name, inner_selectable, inner_name):
    """Get a join expression between two selectables with the designated column names.

    Return None if such an expression does not exist.
    """
    outer_column = _try_get_column(outer_selectable, outer_name)
    inner_column = _try_get_column(inner_selectable, inner_name)
    if outer_column is None or inner_column is None:
        return None
    return outer_column == inner_column
