# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
from collections import namedtuple

from sqlalchemy import Column, bindparam, select
from sqlalchemy.sql import expression as sql_expressions
from sqlalchemy.sql.elements import BindParameter, and_

from . import sql_context_helpers, sql_join_helpers
from ..compiler import expressions
from ..compiler.ir_lowering_sql import constants


# The compilation context holds state that changes during compilation as the tree is traversed
CompilationContext = namedtuple('CompilationContext', (
    # 'query_path_to_selectable': Dict[Tuple[str, ...], Selectable], mapping from each
    # query_path to the Selectable located at that query_path.
    'query_path_to_selectable',
    # 'query_path_to_from_clause': Dict[Tuple[str, ...], FromClause] mapping from each query
    # path to the FromClause at that query path, where the FromClause is a collection of joined
    # Selectables.
    'query_path_to_from_clause',
    # 'query_path_to_location_info': Dict[Tuple[str, ...], LocationInfo], inverse mapping from
    # each query_path to the LocationInfo located at that query_path
    'query_path_to_location_info',
    # 'query_path_to_output_fields': Dict[Tuple[str, ...], Dict[str, Tuple[str, type, bool]]]
    # mapping from each query path to a mapping from field alias to the field name, type, and
    # renamed status. This tuple is used to construct the query outputs, and track when a name
    # changes due to collapsing into a CTE.
    'query_path_to_output_fields',
    # 'query_path_to_filters': Dict[Tuple[str, ...], List[Filter]], mapping from each query_path
    # to the Filter blocks that apply to that query path
    'query_path_to_filters',
    # 'query_path_to_node': Dict[Tuple[str, ...], SqlNode], mapping from each
    # query_path to the SqlNode located at that query_path.
    'query_path_to_node',
    # 'compiler_metadata': CompilerMetadata, SQLAlchemy metadata about Table objects, and
    # further backend specific configuration.
    'compiler_metadata',
))


def emit_code_from_ir(sql_query_tree, compiler_metadata):
    """Return a SQLAlchemy Query from a passed SqlQueryTree.

    Args:
        sql_query_tree: SqlQueryTree, tree representation of the query to emit.
        compiler_metadata: CompilerMetadata, SQLAlchemy specific metadata.

    Returns:
        SQLAlchemy Query
    """
    context = CompilationContext(
        query_path_to_selectable=dict(),
        query_path_to_from_clause=dict(),
        query_path_to_location_info=sql_query_tree.query_path_to_location_info,
        query_path_to_output_fields=sql_query_tree.query_path_to_output_fields,
        query_path_to_filters=sql_query_tree.query_path_to_filters,
        query_path_to_node=sql_query_tree.query_path_to_node,
        compiler_metadata=compiler_metadata,
    )

    return _query_tree_to_query(sql_query_tree.root, context)


def _query_tree_to_query(node, context):
    """Convert this node into its corresponding SQL representation.

    Args:
        node: SqlNode, the node to convert to SQL.
        context: CompilationContext, compilation specific metadata

    Returns:
        Query, the compiled SQL query
    """
    return _create_query(node, context)


def _create_query(node, context):
    """Create a query from a SqlNode.

    Args:
        node: SqlNode, the current node.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Selectable, selectable of the generated query.
    """
    visited_nodes = []
    _recursively_join_tree_nodes(node, visited_nodes, context)
    output_columns = _get_output_columns(visited_nodes, context)
    filters = _get_filters(visited_nodes, context)
    from_clause = sql_context_helpers.get_node_from_clause(node, context)
    query = select(output_columns).select_from(from_clause).where(and_(*filters))
    return query


def _recursively_join_tree_nodes(node, visited_nodes, context):
    """Join non-recursive child nodes to parent, flattening child's references.

    Args:
        node: The current node to flatten and join to.
        context: CompilationContext containing locations and metadata related to the ongoing
                 compilation.

    Returns: List[SqlNode], list of non-recursive nodes visited from this node.
    """
    # recursively collapse the children's trees
    for child_node in node.children:
        _recursively_join_tree_nodes(child_node, visited_nodes, context)
    # create the current node's table
    sql_context_helpers.create_table(node, context)
    for child_node in node.children:
        join_expression = _get_direct_join_expression(node, child_node, context)
        _join_nodes(node, child_node, join_expression, context)
    visited_nodes.append(node)


def _join_nodes(parent_node, child_node, join_expression, context):
    """Join two nodes and update compilation context.

    Returns:
        None, performs JOIN and updates relevant FromClause context.
    """
    parent_from_clause = sql_context_helpers.get_node_from_clause(parent_node, context)
    child_from_clause = sql_context_helpers.get_node_from_clause(child_node, context)
    # JOIN parent to child
    parent_from_clause = parent_from_clause.join(child_from_clause, onclause=join_expression)
    # Update parent to hold joined FromClause
    sql_context_helpers.update_node_from_clause(parent_node, parent_from_clause, context)
    # Cleanup child FromClause
    sql_context_helpers.remove_node_from_clause(child_node, context)


def _get_output_columns(nodes, context):
    """Get the output columns for a list of SqlNodes.

    Args:
        nodes: List[SqlNode], the nodes to get output columns from.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        List[Column], list of SqlAlchemy Columns to output for this query.
    """
    columns = []
    for node in nodes:
        for sql_output in sql_context_helpers.get_outputs(node, context):
            field_name = sql_output.field_name
            column = sql_context_helpers.get_column(field_name, node, context)
            column = column.label(sql_output.output_name)
            columns.append(column)
    return columns


def _get_filters(nodes, context):
    """Get filters to apply to a list of SqlNodes.

    Args:
        nodes: List[SqlNode], the SqlNodes to get filters for.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        List[Expression], list of SQLAlchemy expressions.
    """
    filters = []
    for node in nodes:
        for filter_block in sql_context_helpers.get_filters(node, context):
            filter_sql_expression = _transform_filter_to_sql(filter_block, node, context)
            filters.append(filter_sql_expression)
    return filters


def _transform_filter_to_sql(filter_block, node, context):
    """Transform a Filter block to its corresponding SQLAlchemy expression.

    Args:
        filter_block: Filter, the Filter block to transform.
        node: SqlNode, the node Filter block applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy expression equivalent to the Filter.predicate expression.
    """
    expression = filter_block.predicate
    return _expression_to_sql(expression, node, context)


def _expression_to_sql(expression, node, context):
    """Recursively transform a Filter block predicate to its SQLAlchemy expression representation.

    Args:
        expression: expression, the compiler expression to transform.
        node: SqlNode, the SqlNode the expression applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy Expression equivalent to the passed compiler expression.
    """
    _expression_transformers = {
        expressions.LocalField: _transform_local_field_to_expression,
        expressions.Variable: _transform_variable_to_expression,
        expressions.Literal: _transform_literal_to_expression,
        expressions.BinaryComposition: _transform_binary_composition_to_expression,
    }
    expression_type = type(expression)
    if expression_type not in _expression_transformers:
        raise NotImplementedError(
            u'Unsupported compiler expression "{}" of type "{}" cannot be converted to SQL '
            u'expression.'.format(expression, type(expression)))
    return _expression_transformers[expression_type](expression, node, context)


def _transform_binary_composition_to_expression(expression, node, context):
    """Transform a BinaryComposition compiler expression into a SQLAlchemy expression.

    Recursively calls _expression_to_sql to convert its left and right sub-expressions.

    Args:
        expression: expression, BinaryComposition compiler expression.
        node: SqlNode, the SqlNode the expression applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy expression.
    """
    if expression.operator not in constants.SUPPORTED_OPERATORS:
        raise NotImplementedError(
            u'Filter operation "{}" is not supported by the SQL backend.'.format(
                expression.operator))
    sql_operator = constants.SUPPORTED_OPERATORS[expression.operator]
    left = _expression_to_sql(expression.left, node, context)
    right = _expression_to_sql(expression.right, node, context)
    if sql_operator.cardinality == constants.CARDINALITY_UNARY:
        left, right = _get_column_and_bindparam(left, right, sql_operator)
        clause = getattr(left, sql_operator.name)(right)
        return clause
    elif sql_operator.cardinality == constants.CARDINALITY_BINARY:
        clause = getattr(sql_expressions, sql_operator.name)(left, right)
        return clause
    elif sql_operator.cardinality == constants.CARDINALITY_LIST_VALUED:
        left, right = _get_column_and_bindparam(left, right, sql_operator)
        # ensure that SQLAlchemy treats the right bind parameter as list valued
        right.expanding = True
        clause = getattr(left, sql_operator.name)(right)
        return clause
    raise AssertionError(u'Unreachable, operator cardinality {} for compiler expression {} is '
                         u'unknown'.format(sql_operator.cardinality, expression))


def _get_column_and_bindparam(left, right, operator):
    """Return left and right expressions in (Column, BindParameter) order."""
    if not isinstance(left, Column):
        left, right = right, left
    if not isinstance(left, Column):
        raise AssertionError(
            u'SQLAlchemy operator {} expects Column as left side the of expression, got {} '
            u'of type {} instead.'.format(operator, left, type(left)))
    if not isinstance(right, BindParameter):
        raise AssertionError(
            u'SQLAlchemy operator {} expects BindParameter as the right side of the expression, '
            u'got {} of type {} instead.'.format(operator, right, type(right)))
    return left, right


def _transform_literal_to_expression(expression, node, context):
    """Transform a Literal compiler expression into its SQLAlchemy expression representation.

    Args:
        expression: expression, Literal compiler expression.
        node: SqlNode, the SqlNode the expression applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy expression.
    """
    return expression.value


def _transform_variable_to_expression(expression, node, context):
    """Transform a Variable compiler expression into its SQLAlchemy expression representation.

    Args:
        expression: expressian, Variable compiler expression.
        node: SqlNode, the SqlNode the expression applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy expression.
    """
    variable_name = expression.variable_name
    if not variable_name.startswith(u'$'):
        raise AssertionError(u'Unexpectedly received variable name {} that is not '
                             u'prefixed with "$"'.format(variable_name))
    return bindparam(variable_name[1:])


def _transform_local_field_to_expression(expression, node, context):
    """Transform a LocalField compiler expression into its SQLAlchemy expression representation.

    Args:
        expression: expression, LocalField compiler expression.
        node: SqlNode, the SqlNode the expression applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy expression.
    """
    column_name = expression.field_name
    column = sql_context_helpers.get_column(column_name, node, context)
    return column


def _get_direct_join_expression(outer_node, inner_node, context):
    """Get a direct JOIN expression between the Selectables of two nodes.

    A direct JOIN expression is one that does not require an intermediate junction table to resolve.
    The foreign key exists on one of the tables of the relationship and points to the other.
    Args:
        outer_node: SqlNode, the source node of the edge.
        inner_node: SqlNode, the sink node of the edge.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy expression representing JOIN onclause, if found.
    """
    edge_name = sql_join_helpers.get_block_edge_name(inner_node.block)
    outer_column_name, inner_column_name = sql_join_helpers.get_column_names_for_edge(edge_name)
    # The natural JOIN direction is when outer table -FK> inner table, with the outer table holding
    # the foreign key
    natural_join_expression = sql_join_helpers.try_get_join_expression(
        outer_node, outer_column_name, inner_node, inner_column_name, context)
    if natural_join_expression is not None:
        return natural_join_expression
    # The inverse JOIN direction is when inner table -FK> outer table, with the inner table holding
    # the foreign key
    inverse_join_expression = sql_join_helpers.try_get_join_expression(
        outer_node, inner_column_name, inner_node, outer_column_name, context)
    if inverse_join_expression is not None:
        return inverse_join_expression
    outer_selectable = sql_context_helpers.get_node_selectable(outer_node, context)
    inner_selectable = sql_context_helpers.get_node_selectable(inner_node, context)
    raise AssertionError(
        u'Table "{}" is expected to have foreign key "{}" to column "{}" of table "{}" or '
        u'Table "{}" is expected to have foreign key "{}" to column "{}" of table "{}".'.format(
            outer_selectable.original, outer_column_name, inner_column_name,
            inner_selectable.original, inner_selectable.original, outer_column_name,
            inner_column_name, outer_selectable.original,
        )
    )
