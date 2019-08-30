# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

SQLEdgeDescriptor = namedtuple(
    'SQLEdgeDescriptor',
    (
        'from_table',  # Identifier of the source table.
        'from_column',  # Name of the column in the source table to join on.
        'to_table',  # Identifier of the destination table.
        'to_column',  # Name of the column in the destination table to join on.
    )
)

JunctionTableEnd = namedtuple(
    'JunctionTableEdgeEndDescriptor',
    (
        'local_column',  # Name of the junction table column to join on.
        'foreign_table',  # Identifier of the table to join with.
        'foreign_column',  # Name of the foreign column to join.
    )
)

JunctionTableEdgeDescriptor = namedtuple(
    'JunctionTableEdgeDescriptor',
    (
        'junction_table',  # Identifier of the table to be used as a junction table.
        'inbound_edge_end',
        # JunctionTableEnd specifying how to execute joins with the source table.
        'outbound_edge_end',
        # JunctionTableEnd specifying how to execute joins with the destination table.
    )
)


# TODO(pmantica1): Add functionality to create SQLEdgeDescriptor from foreign keys in tables
# TODO(pmantica1): Add functionality to map tables to edges.
# Note: The index information can be inferred from the SQLAlchemy Table objects. Views do not have
#       index information. However, often views are essentially the same "virtual table" as the
#       underlying so it is often possible to infer the "pseudo-indexes" for views. To pass in this
#       information we could just modify the underlying SQLALchemy Table objects.
#
# Note: I allow the user to be able to choose how to name the corresponding VertexType
#       objects for the SQLAlchemy Table objects. I expect there to be only two
#       naming conventions: <tableName> and <databaseName>+<tableName> to resolve
#       naming conflicts when using multiple databases. So one option was to include
#       a prepend_database_name flag. However, even if I did so I would need to
#       have a way to uniquely identify each table in the SQLEdgeDescriptor objects.
#       To do so, I would probably have to include from_database and to_database
#       fields. However, these two fields would be unnecessary when we only included
#       one database. Therefore, I thought it'd be simpler in general for the user
#       to specify the corresponding VertexType names / GraphQLObject names for the
#       SQLAlchemy tables.
def get_sqlalchemy_schema_graph(tables, sql_edge_descriptors, junction_tables):
    """Return a SchemaGraph from metadata.

    Args:
        tables: dict, str -> SQLAlchemy Table, mapping identifiers for tables in the underlying
                SQL backend to their SQLAlchemy representation. Tables will be by default
                represented as VertexType objects in the SchemaGraph with the table identifiers as
                the names of the VertexType objects. Columns will be represented as properties
                and columns with unsupported types will be ignored. Tables can be also represented
                as EdgeType objects through the junction_tables argument.
        sql_edge_descriptors: dict, str-> SQLEdgeDescriptor, mapping identifiers for edges in
                              the schema to namedtuples specifying the source and destination tables
                              and which columns to use when traversing the edges. This function will
                              map each edge to an EdgeType, using the identifier as the EdgeType
                              name and the SQLEdgeDescriptor to reconstruct the EdgeType
                              connections. The identifiers must not conflict with table identifiers.
        junction_tables: dict, str -> JunctionTableEdgeDescriptor, mapping identifiers for junction
                         table edges to namedtuples specifying how junction tables will
                         be represented as edges in the schema. This function will map each
                         junction table  edge to an EdgeType, using the identifier as the EdgeType
                         name and the JunctionTableEdgeDescriptor to reconstruct the EdgeType
                         connections. The identifiers must not conflict with table or edge
                         identifiers.

    Returns:
        SchemaGraph reflecting the inputted metadata.
    """
    pass


# Note: I think that we should remove join_descriptors from the SQLAlchemySchemaInfo and instead
#       have the sql_edge_descriptors arguments as described above. It would still be easy
#       to resolve vertex fields. For instance to resolve a vertex field called out_A_B simply strip
#       the prefix to get the edge name, (A_B), then use the prefix to determine the direction of
#       the join. Since the prefix is "out_" then we know that the join is from A to B.
#       Also, join_descriptors do not communicate two key properties:
#           1. That edge names are globally unique.
#           2. Vertex fields must be symmetric: if there is a field out_<edgeName>: [B] in
#              object A then there must be a field in_<edgeName>: [A] in object A.
def get_restructured_edge_descriptors(sql_edges_descriptors):
    """Return the sql edge descriptors in a format more suited to resolving vertex fields."""
    pass
