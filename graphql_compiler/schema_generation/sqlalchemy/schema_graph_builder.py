# Copyright 2019-present Kensho Technologies, LLC.


def get_sqlalchemy_schema_graph(vertex_name_to_table, direct_edges, junction_table_edges):
    """Return a SchemaGraph from the metadata.

    Args:
        vertex_name_to_table: dict, str -> SQLAlchemy Table.  This dictionary is used to generate
                              the VertexType objects in the SchemaGraph. Each SQLAlchemyTable will
                              be represented as a VertexType. The VertexType names are the
                              dictionary keys. The properties of the VertexType objects will be
                              inferred from the columns of the underlying tables. The properties
                              will have the same name as the underlying columns and columns with
                              unsupported types, (SQL types with no matching GraphQL type), will be
                              ignored.
        direct_edges: dict, str -> DirectEdgeDescriptor. This dictionary will be used to generate
                      EdgeType objects. The name of the EdgeType objects will be dictionary keys and
                      the connections will be deduced from the DirectEdgeDescriptor objects.
        junction_table_edges: dict, str -> JunctionTableEdgeDescriptor. This dictionary will be
                              used to generate EdgeType objects. The name of the EdgeType objects
                              will be dictionary keys and the connections will be deduced from the
                              JunctionTableEdgeDescriptor objects.

    Returns:
        SchemaGraph reflecting the inputted metadata.
    """
    pass
