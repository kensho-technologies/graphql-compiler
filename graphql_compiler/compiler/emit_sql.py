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
    output_columns = _get_output_columns(node, context)
    filters = _get_filters(node, context)
    selectable = sql_context_helpers.get_node_selectable(node, context)
    query = select(output_columns).select_from(selectable).where(and_(*filters))
    return query


def _get_output_columns(node, context):
    """Get the output columns required by the query.

    Args:
        node: SqlNode, the current node.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        List[Column], list of SqlAlchemy Columns to output for this query.
    """
    sql_outputs = context.query_path_to_output_fields[node.query_path]
    columns = []
    for sql_output in sql_outputs:
        field_name = sql_output.field_name
        column = sql_context_helpers.get_column(field_name, node, context)
        column = column.label(sql_output.output_name)
        columns.append(column)
    return columns


def _get_filters(node, context):
    """Get filters to apply to a SqlNode.

    Args:
        node: SqlNode, the SqlNode to get filters for.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        List[Expression], list of SQLAlchemy expressions.
    """
    filters = [
        _transform_filter_to_sql(filter_block, filter_query_path, context)
        for filter_block, filter_query_path in sql_context_helpers.get_filters(node, context)
    ]
    return filters


def _transform_filter_to_sql(filter_block, filter_query_path, context):
    """Transform a Filter block to its corresponding SQLAlchemy expression.

    Args:
        filter_block: Filter, the Filter block to transform.
        filter_query_path: Tuple[str], the query_path the Filter block applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy expression equivalent to the Filter.predicate expression.
    """
    filter_node = sql_context_helpers.get_node_at_path(filter_query_path, context)
    expression = filter_block.predicate
    return _expression_to_sql(expression, filter_node, context)


def _expression_to_sql(expression, node, context):
    """Recursively transform a Filter block predicate to its SQLAlchemy expression representation.

    Args:
        expression: expression, the compiler expression to transform.
        node: SqlNode, the SqlNode the expression applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SqlAlchemy expression equivalent to the passed compiler expression.
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
    if expression.operator in constants.UNSUPPORTED_OPERATOR_NAMES:
        raise NotImplementedError(
            u'Filter operation "{}" is not supported by the SQL backend.'.format(
                expression.operator))
    sql_operator = constants.SUPPORTED_OPERATORS[expression.operator]
    left = _expression_to_sql(expression.left, node, context)
    right = _expression_to_sql(expression.right, node, context)
    if sql_operator.cardinality == constants.Cardinality.UNARY:
        # ensure the operator is grabbed from the Column object
        if not isinstance(left, Column) and isinstance(right, Column):
            left, right = right, left
        clause = getattr(left, sql_operator.name)(right)
        return clause
    elif sql_operator.cardinality == constants.Cardinality.BINARY:
        clause = getattr(sql_expressions, sql_operator.name)(left, right)
        return clause
    elif sql_operator.cardinality == constants.Cardinality.LIST_VALUED:
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
    else:
        raise AssertionError(u'Unknown operator cardinality {}'.format(sql_operator.cardinality))


def _transform_literal_to_expression(expression, node, context):
    """Transform a Literal compiler expression into it's SQLAlchemy expression representation.

    Args:
        expression: expression, Literal compiler expression.
        node: SqlNode, the SqlNode the expression applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy expression.
    """
    return expression.value


def _transform_variable_to_expression(expression, node, context):
    """Transform a Variable compiler expression into it's SQLAlchemy expression representation.

    Args:
        expression: expression, Variable compiler expression.
        node: SqlNode, the SqlNode the expression applies to.
        context: CompilationContext, global compilation state and metadata.

    Returns:
        Expression, SQLAlchemy expression.
    """
    variable_name = expression.variable_name
    if variable_name.startswith(u'$'):
        variable_name = variable_name[1:]
    return bindparam(variable_name)


def _transform_local_field_to_expression(expression, node, context):
    """Transform a LocalField compiler expression into it's SQLAlchemy expression representation.

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
