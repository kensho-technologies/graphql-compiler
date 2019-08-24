# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

# A complete specification of a SQL edge.
SQLEdgeDescriptor= namedtuple(
    'SQLEdgeDescriptor',
    (
        'from_vertex',  # Name of the source vertex.
        'to_vertex',  # Name of the target vertex.
        'from_column',  # The column in the source vertex we intend to join on.
        'to_column',  # The column in the destination vertex we intend to join on.
    )
)
# TODO(pmantica1): Add functionality to create SQLEdgeDescriptor from foreign keys in tables
# TODO(pmantica1): Add functionality to map tables to edges.
# Note: The index information can be inferred from the SQLAlchemy Table objects. Views do not have
#       index information. However, often views are essentially the same "virtual table" as the
#       underlying so it is often infer the "pseudo-indexes" for views. To pass in this information
#       we could just modify the underlying SQLALchemy Table objects.
def get_sqlalchemy_schema_graph(tables, sql_edge_descriptors):
    """Return a SchemaGraph from metadata describing a SQL schema.

    Args:
        tables: dict mapping every vertex name in the SchemaGraph to the SQLAlchemy Table from which
                it will be generated from. Columns that cannot be represented in the SchemaGraph
                will be ignored.
                Note: I allow the user to be able to choose how to name the corresponding VertexType
                      objects for the SQLAlchemy Table objects. I expect there to be only two
                      naming conventions: <tableName> and <databaseName>+<tableName> to resolve
                      naming conflicts when using multiple databases. So one option was to include
                      a prepend_database_name flag. However, even if I did so I would need to
                      have a way to uniquely identify each table in the SQLEdgeDescriptor objects.
                      To do so, I would probably have to include from_database and to_database
                      fields. However, these two fields would be unnecessary when we only included
                      one database. Therefore, I thought it'd be simpler in general for the user
                      to specify the corresponding VertexType names / GraphQLObject names for the
                      SQLAlchemy tables.
        sql_edge_descriptors: dict, str -> SQLEdgeDescriptor, mapping the name of an EdgeType in the
                              SchemaGraph to its corresponding SQLEdgeDescriptor.

    Returns:
        SchemaGraph reflecting the SQL metadata.
    """
    pass


# Note: This essentially returns the join_descriptors from the SQLAlchemySchemaInfo
def get_restructured_edge_descriptors(sql_edges_descriptors):
    """Return the sql edge descriptors in a format more suited to resolving vertex fields."""
    pass
