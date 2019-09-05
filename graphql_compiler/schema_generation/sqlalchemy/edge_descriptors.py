# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from ...schema import OUTBOUND_EDGE_FIELD_PREFIX, INBOUND_EDGE_FIELD_PREFIX
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


JunctionTableEnd = namedtuple(
    'JunctionTableEnd',
    (
        'junction_table_column',  # Name of the junction table column to use for SQL join.
        'foreign_vertex',  # Name of the foreign vertex.
        'foreign_column',  # Name of the column in the underlying foreign table to use for SQL join.
    )
)

JunctionTableEdgeDescriptor = namedtuple(
    'JunctionTableEdgeDescriptor',
    (
        'junction_table',  # SQLAlchemy Table.
        'inbound_edge_end',
        # JunctionTableEnd specifying how to execute joins with the source table.
        'outbound_edge_end',
        # JunctionTableEnd specifying how to execute joins with the destination table.
    )
)


def get_join_descriptors(direct_edges, junction_table_edges):
    """Return the SQL edges in a format more suited to resolving vertex fields."""
    join_descriptors = {}
    for edge_name, direct_edge_descriptor in direct_edges.items():
        direct_join_descriptor = DirectJoinDescriptor(direct_edge_descriptor.from_column,
                                                      direct_edge_descriptor.to_column)
        join_descriptors.setdefault(direct_edge_descriptor.from_vertex, {})
        join_descriptors.setdefault(direct_edge_descriptor.to_vertex, {})
        out_edge_name = OUTBOUND_EDGE_FIELD_PREFIX + edge_name
        in_edge_name = INBOUND_EDGE_FIELD_PREFIX + edge_name
        join_descriptors[direct_edge_descriptor.from_vertex][out_edge_name] = direct_join_descriptor
        join_descriptors[direct_edge_descriptor.to_vertex][in_edge_name] = direct_join_descriptor
    return join_descriptors
