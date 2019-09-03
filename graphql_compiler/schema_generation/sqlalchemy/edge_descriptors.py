# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

SQLEdgeDescriptor = namedtuple(
    'SQLEdgeDescriptor',
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
