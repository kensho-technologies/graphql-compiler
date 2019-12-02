# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
import warnings

import six

from ...schema import INBOUND_EDGE_FIELD_PREFIX, OUTBOUND_EDGE_FIELD_PREFIX
from ...schema.schema_info import DirectJoinDescriptor
from ..exceptions import InvalidSQLEdgeError


DirectEdgeDescriptor = namedtuple(
    "DirectEdgeDescriptor",
    (
        "from_vertex",  # Name of the source vertex.
        "from_column",  # Name of the column of the underlying source table to use for SQL join.
        "to_vertex",  # Name of the destination vertex.
        "to_column",  # Name of the column of the underlying destination table to use for SQL join.
    ),
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
        join_descriptors[direct_edge_descriptor.from_vertex][out_edge_name] = DirectJoinDescriptor(
            from_column, to_column
        )
        join_descriptors[direct_edge_descriptor.to_vertex][in_edge_name] = DirectJoinDescriptor(
            to_column, from_column
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
            (direct_edge_descriptor.to_vertex, direct_edge_descriptor.to_column),
        ):
            if vertex_name not in vertex_name_to_table:
                raise InvalidSQLEdgeError(
                    "SQL edge {} with edge descriptor {} references a "
                    "non-existent vertex {}".format(edge_name, direct_edge_descriptor, vertex_name)
                )
            if column_name not in vertex_name_to_table[vertex_name].columns:
                raise InvalidSQLEdgeError(
                    "SQL edge {} with edge descriptor {} references a "
                    "non-existent column {}".format(edge_name, direct_edge_descriptor, column_name)
                )


def generate_direct_edge_descriptors_from_foreign_keys(vertex_name_to_table):
    """Return a set of DirectEdgeDescriptor objects from the foreign keys in the SQLAlchemy tables.

    Args:
        vertex_name_to_table: Dict[str, Table], a mapping of vertex type names to the underlying
                              SQLAlchemy table objects.

    Return:
        set of DirectEdgeDescriptor objects extrapolated from the foreign keys.
    """
    table_to_vertex_name = _get_table_to_vertex_name(vertex_name_to_table)
    direct_edge_descriptors = set()

    number_of_composite_foreign_keys = 0
    for vertex_name, table in vertex_name_to_table.items():
        for fk_constraint in table.foreign_key_constraints:
            foreign_key_columns = fk_constraint.columns
            # The .elements attribute refers to a list of ForeignKey objects.
            referenced_columns = [element.column for element in fk_constraint.elements]
            if len(foreign_key_columns) == 1 and len(referenced_columns) == 1:
                foreign_key_column = next(iter(foreign_key_columns))
                referenced_column = next(iter(referenced_columns))
                referenced_table = referenced_column.table
                referenced_vertex_name = table_to_vertex_name[referenced_table]
                direct_edge_descriptors.add(
                    DirectEdgeDescriptor(
                        from_vertex=vertex_name,
                        from_column=foreign_key_column.name,
                        to_vertex=referenced_vertex_name,
                        to_column=referenced_column.name,
                    )
                )
            elif len(foreign_key_columns) == 0 or len(referenced_columns) == 0:
                raise AssertionError(
                    "Found invalid foreign key in table {}. Foreign key "
                    "columns {}. Referenced primary key columns {}.".format(
                        table.fullname, foreign_key_columns, referenced_columns
                    )
                )
            else:
                number_of_composite_foreign_keys += 1

    if number_of_composite_foreign_keys:
        warnings.warn(
            "Ignored {} edges implied by composite foreign keys. We currently do not "
            "support SQL edges with multiple source/destination columns."
        )

    return direct_edge_descriptors


def _get_table_to_vertex_name(vertex_name_to_table):
    """Return a mapping of SQLAlchemy Table objects to their vertex type names."""
    table_to_vertex_name = {}

    for vertex_name, table in vertex_name_to_table.items():
        if table in table_to_vertex_name:
            other_vertex_name = table_to_vertex_name[table]
            raise AssertionError(
                "Table {} is associated with multiple vertex types: {} and {}.".format(
                    table.fullname, vertex_name, other_vertex_name
                )
            )
        table_to_vertex_name[table] = vertex_name

    return table_to_vertex_name
