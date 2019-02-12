from graphql_compiler.compiler import blocks, sql_context_helpers


def get_block_direction(block):
    """Get the direction of a Traverse block."""
    if not isinstance(block, (blocks.Traverse,)):
        raise AssertionError(
            u'Cannot get direction of block "{}" of type "{}"'.format(block, type(block)))
    return block.direction


def get_block_edge_name(block):
    """Get the edge name associated with a Traverse block."""
    if not isinstance(block, (blocks.Traverse,)):
        raise AssertionError(
            u'Cannot get edge name of block "{}" of type "{}"'.format(block, type(block)))
    return block.edge_name


def get_column_names_for_edge(edge_name):
    """Return the expected column names for a given edge.

    For an edge out_Foo_Bar, the expected columns names would be the tuple ("foo_id", "bar_id").
    Args:
        edge_name:str, the name of the edge to return column names from.

    Returns: Tuple[str, str], the expected column names.
    """
    inner_prefix, outer_prefix = edge_name.lower().split('_')
    outer_column_name = u'{column_prefix}_id'.format(column_prefix=outer_prefix)
    inner_column_name = u'{column_prefix}_id'.format(column_prefix=inner_prefix)
    return outer_column_name, inner_column_name


def try_get_join_expression(source_node, source_name, sink_node, sink_name, context):
    """Attempt to get a join expression between two nodes with the designated column names.

    Return None if such an expression does not exist.

    Args:
        source_node: SqlNode, the source SqlNode of the edge.
        source_name: str, The name of the column to retrieve from the source node.
        sink_node: SqlNode, the sink SqlNode of the edge.
        sink_name: str, The name of the column to get from the sink node.
        context: CompilationContext, global compilation state and metadata.

    Returns: Optional[expression], SQLAlchemy expression corresponding to the JOIN onclause
    """
    outer_column = sql_context_helpers.try_get_column(source_name, source_node, context)
    inner_column = sql_context_helpers.try_get_column(sink_name, sink_node, context)
    if outer_column is None or inner_column is None:
        return None
    return outer_column == inner_column


def validate_join(outer_node, inner_node, context):
    """Ensure that a JOIN is supported by the SQL backend, raise AssertionError otherwise.

    Args:
        outer_node: SqlNode, the source node of the JOIN.
        inner_node: SqlNode, the sink node of the JOIN....
        context: CompilationContext, global compilation state and metadata.

    """
    outer_type = sql_context_helpers.get_schema_type_name(outer_node, context)
    inner_type = sql_context_helpers.get_schema_type_name(inner_node, context)
    if outer_type == inner_type:
        raise AssertionError(
            u'Self-joins are not yet supported by the SQL backend of the GraphQL compiler.')
