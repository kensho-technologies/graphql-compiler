# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
from collections import namedtuple

from sqlalchemy import select

from . import sql_context_helpers


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
    selectable = sql_context_helpers.get_node_selectable(node, context)
    query = select(output_columns).select_from(selectable)
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
