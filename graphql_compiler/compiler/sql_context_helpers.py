# Copyright 2018-present Kensho Technologies, LLC.
"""Collection of helpers for accessing SQL CompilationContext state."""


def get_schema_type_name(node, context):
    """Return the GraphQL type name of a node."""
    query_path = node.query_path
    if query_path not in context.query_path_to_location_info:
        raise AssertionError(
            u'Unable to find type name for query path {} with context {}.'.format(
                query_path, context))
    location_info = context.query_path_to_location_info[query_path]
    return location_info.type.name


def get_node_selectable(node, context):
    """Return the Selectable Union[Table, CTE] associated with the node."""
    query_path = node.query_path
    if query_path not in context.query_path_to_selectable:
        raise AssertionError(
            u'Unable to find selectable for query path {} with context {}.'.format(
                query_path, context))
    selectable = context.query_path_to_selectable[query_path]
    return selectable


def get_node_at_path(query_path, context):
    """Return the SqlNode associated with the query path."""
    if query_path not in context.query_path_to_node:
        raise AssertionError(
            u'Unable to find SqlNode for query path {} with context {}.'.format(
                query_path, context))
    node = context.query_path_to_node[query_path]
    return node


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
        raise AssertionError(
            u'Selectable "{}" does not have a column collection. Context is {}.'.format(
                selectable, context))
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
            u'Column "{}" not found in selectable "{}". Columns present are {}. '
            u'Context is {}.'.format(column_name, selectable.original,
                                     [col.name for col in selectable.c], context))
    return column


def get_filters(node, context):
    """Return the filters applied to a SqlNode."""
    return context.query_path_to_filters.get(node.query_path, [])


def get_outputs(node, context):
    """Return the SqlOutputs for a SqlNode."""
    return context.query_path_to_output_fields.get(node.query_path, [])
