# Copyright 2018-present Kensho Technologies, LLC.
"""Collection of helpers for accessing SQL CompilationContext state."""


def get_schema_type_name(node, context):
    """Return the GraphQL type name of a node."""
    query_path = node.query_path
    if query_path not in context.query_path_to_location_info:
        raise AssertionError(u'Unable to find type name for query path {}'.format(query_path))
    location_info = context.query_path_to_location_info[query_path]
    return location_info.type.name


def get_node_selectable(node, context):
    """Return the Selectable Union[Table, CTE] associated with the node."""
    query_path = node.query_path
    if query_path not in context.query_path_to_selectable:
        raise AssertionError(u'Unable to find selectable for query path {}'.format(query_path))
    selectable = context.query_path_to_selectable[query_path]
    return selectable


def try_get_column(column_name, node, context):
    """Attempt to get a column by name from the selectable.

    Args:
        column_name: str, name of the column to retrieve.
        node: SqlNode, the node the column is being retrieved for.
        context: CompilationContext, compilation specific metadata.

    Returns:
        Optional[column], the SQLAlchemy column if found, None otherwise.
    """
    selectable = get_node_selectable(node, context)
    if not hasattr(selectable, 'c'):
        raise AssertionError(u'Selectable "{}" does not have a column collection.'.format(
            selectable))
    return selectable.c.get(column_name, None)


def get_column(column_name, node, context):
    """Get a column by name from the selectable.

    Args:
        column_name: str, name of the column to retrieve.
        node: SqlNode, the node the column is being retrieved for.
        context: CompilationContext, compilation specific metadata.

    Returns:
        column, the SQLAlchemy column if found. Raises an AssertionError otherwise.

    """
    column = try_get_column(column_name, node, context)
    if column is None:
        selectable = get_node_selectable(node, context)
        raise AssertionError(
            u'Column "{}" not found in selectable "{}". Columns present are {}'.format(
                column_name, selectable.original, [col.name for col in selectable.c]))
    return column
