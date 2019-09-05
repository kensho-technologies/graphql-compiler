# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from ...schema import INBOUND_EDGE_FIELD_PREFIX, OUTBOUND_EDGE_FIELD_PREFIX
from ...schema.schema_info import DirectJoinDescriptor


DirectEdgeDescriptor = namedtuple(
    'DirectEdgeDescriptor',
    (
        'from_vertex',  # Name of the source vertex.
        'from_column',  # Name of the column of the underlying source table to use for SQL join.
        'to_vertex',  # Name of the destination vertex.
        'to_column',  # Name of the column of the underlying destination table to use for SQL join.
    )
)


def get_join_descriptors(direct_edges):
    """Return the SQL edges in a format more suited to resolving vertex fields."""
    join_descriptors = {}
    for edge_name, direct_edge_descriptor in direct_edges.items():
        from_column = direct_edge_descriptor.from_column
        to_column = direct_edge_descriptor.to_column
        join_descriptors.setdefault(direct_edge_descriptor.to_vertex, {})
        out_edge_name = OUTBOUND_EDGE_FIELD_PREFIX + edge_name
        in_edge_name = INBOUND_EDGE_FIELD_PREFIX + edge_name
        join_descriptors[direct_edge_descriptor.from_vertex][out_edge_name] = (
            DirectJoinDescriptor(from_column, to_column)
        )
        join_descriptors[direct_edge_descriptor.to_vertex][in_edge_name] = (
            DirectJoinDescriptor(to_column, from_column)
        )
    return join_descriptors
