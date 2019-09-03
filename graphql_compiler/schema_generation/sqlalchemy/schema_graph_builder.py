# Copyright 2019-present Kensho Technologies, LLC.

def get_sqlalchemy_schema_graph(tables, sql_edge_descriptors, junction_tables):
    """Return a SchemaGraph from the metadata.

    Args:
        tables: dict, str -> SQLAlchemy Table, mapping every VertexType in the SchemaGraph to a
                SQLAlchemy Table. The columns of each table, (with a supported type), will me mapped
                to a property with the same name as the column in the corresponding VertexType.
        sql_edge_descriptors: dict, str-> SQLEdgeDescriptor, mapping the names of EdgeType objects
                              in the SchemaGraph to namedtuple objects specifying the source and
                              destination VertexType objects and which columns of the underlying
                              tables to use when traversing the edges.
        junction_tables: dict, str -> JunctionTableEdgeDescriptor, mapping the names of junction
                         table edges to namedtuple objects specifying the source and destination
                         GraphQL objects and how to use the junction tables as many-to-many edges.

    Returns:
        SchemaGraph reflecting the inputted metadata.
    """
    pass


def get_restructured_edge_descriptors(sql_edges_descriptors):
    """Return the sql edge descriptors in a format more suited to resolving vertex fields."""
    pass
