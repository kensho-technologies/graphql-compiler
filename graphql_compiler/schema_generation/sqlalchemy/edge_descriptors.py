# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

import six

from ...schema import INBOUND_EDGE_FIELD_PREFIX, OUTBOUND_EDGE_FIELD_PREFIX
from ...schema.schema_info import DirectJoinDescriptor
from ..exceptions import InvalidSQLEdgeError


DirectEdgeDescriptor = namedtuple(
    'DirectEdgeDescriptor',
    (
        'from_vertex',  # Name of the source vertex.
        'from_column',  # Name of the column of the underlying source table to use for SQL join.
        'to_vertex',  # Name of the destination vertex.
        'to_column',  # Name of the column of the underlying destination table to use for SQL join.
    )
)


def get_join_descriptors_from_edge_descriptors(direct_edges):
    """Return the SQL edges in a format more suited to resolving vertex fields."""
    join_descriptors = {}
    for edge_name, direct_edge_descriptor in direct_edges.items():
        from_column = direct_edge_descriptor.from_column
        to_column = direct_edge_descriptor.to_column
        join_descriptors.setdefault(direct_edge_descriptor.from_vertex, {})
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


def validate_edge_descriptors(vertex_name_to_table, direct_edges):
    """Validate that the edge descriptors do not reference non-existent vertices or columns."""
    # TODO(pmantica1): Validate that columns in a direct SQL edge have comparable types.
    # TODO(pmantica1): Validate that columns don't have types that probably shouldn't be used for
    #                  joins, (e.g. array types).
    for edge_name, direct_edge_descriptor in six.iteritems(direct_edges):
        for vertex_name, column_name in (
            (direct_edge_descriptor.from_vertex, direct_edge_descriptor.from_column),
            (direct_edge_descriptor.to_vertex, direct_edge_descriptor.to_column)
        ):
            if vertex_name not in vertex_name_to_table:
                raise InvalidSQLEdgeError('SQL edge {} with edge descriptor {} references a '
                                          'non-existent vertex {}'
                                          .format(edge_name, direct_edge_descriptor, vertex_name))
            if column_name not in vertex_name_to_table[vertex_name].columns:
                raise InvalidSQLEdgeError('SQL edge {} with edge descriptor {} references a '
                                          'non-existent column {}'
                                          .format(edge_name, direct_edge_descriptor, column_name))
