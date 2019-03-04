# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
from collections import namedtuple

from sqlalchemy import Column, bindparam, select
from sqlalchemy.sql import expression as sql_expressions
from sqlalchemy.sql.elements import BindParameter, and_

from . import sql_context_helpers
from ..compiler import expressions
from ..compiler.ir_lowering_sql import constants


# The compilation context holds state that changes during compilation as the tree is traversed
CompilationContext = namedtuple('CompilationContext', (
    # 'query_path_to_selectable': Dict[Tuple[str, ...], Selectable], mapping from each
    # query_path to the Selectable located at that query_path.
    'query_path_to_selectable',
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
    # 'compiler_metadata': SqlMetadata, SQLAlchemy metadata about Table objects, and
    # further backend specific configuration.
    'compiler_metadata',
))


def emit_code_from_ir(sql_query_tree, compiler_metadata):
    """Return a SQLAlchemy Query from a passed SqlQueryTree.

    Args:
        sql_query_tree: SqlQueryTree, tree representation of the query to emit.
        compiler_metadata: SqlMetadata, SQLAlchemy specific metadata.

    Returns:
        SQLAlchemy Query
    """
    context = CompilationContext(
        query_path_to_selectable=dict(),
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
    _create_table_and_update_context(node, context)
    return _create_query(node, context)


def _create_table_and_update_context(node, context):
    """Create an aliased table for a SqlNode.

    Updates the relevant Selectable global context.

    Args:
        node: SqlNode, the current node.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Table, the newly aliased SQLAlchemy table.
    """
    schema_type_name = sql_context_helpers.get_schema_type_name(node, context)
    table = context.compiler_metadata.get_table(schema_type_name).alias()
    context.query_path_to_selectable[node.query_path] = table
    return table


def _create_query(node, context):
    """Create a query from a SqlNode.

    Args:
        node: SqlNode, the current node.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Selectable, selectable of the generated query.
    """
    visited_nodes = [node]
    output_columns = _get_output_columns(visited_nodes, context)
    filters = _get_filters(visited_nodes, context)
    selectable = sql_context_helpers.get_node_selectable(node, context)
    query = select(output_columns).select_from(selectable).where(and_(*filters))
    return query


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
        expression: expression, Variable compiler expression.
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
