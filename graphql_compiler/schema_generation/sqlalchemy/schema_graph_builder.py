# Copyright 2019-present Kensho Technologies, LLC.
from ...global_utils import merge_non_overlapping_dicts
from ..schema_graph import (
    EdgeType, InheritanceStructure, PropertyDescriptor, SchemaGraph, VertexType,
    link_schema_elements
)
from .scalar_type_mapper import try_get_graphql_scalar_type


def get_sqlalchemy_schema_graph(vertex_name_to_table, direct_edges):
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

    Returns:
        SchemaGraph reflecting the specified metadata.
    """
    vertex_types = {
        vertex_name: _get_vertex_type_from_sqlalchemy_table(vertex_name, table)
        for vertex_name, table in vertex_name_to_table.items()
    }
    edge_types = {
        edge_name: _get_edge_type_from_direct_edge(edge_name, direct_edge_descriptor)
        for edge_name, direct_edge_descriptor in direct_edges.items()
    }
    elements = merge_non_overlapping_dicts(vertex_types, edge_types)
    elements.update(vertex_types)
    elements.update(edge_types)
    direct_superclass_sets = {element_name: set() for element_name in elements}
    inheritance_structure = InheritanceStructure(direct_superclass_sets)
    link_schema_elements(elements, inheritance_structure)
    return SchemaGraph(elements, inheritance_structure, set())


def _get_vertex_type_from_sqlalchemy_table(vertex_name, table):
    """Return the VertexType corresponding to the SQLAlchemyTable object."""
    properties = dict()
    for column in table.columns:
        name = column.key
        maybe_property_type = try_get_graphql_scalar_type(name, column.type)
        if maybe_property_type is not None:
            default = None
            properties[name] = PropertyDescriptor(maybe_property_type, default)
    return VertexType(vertex_name, False, properties, {})


def _get_edge_type_from_direct_edge(edge_name, direct_edge_descriptor):
    """Return the EdgeType corresponding to a direct SQL edge."""
    return EdgeType(edge_name, False, {}, {},
                    base_in_connection=direct_edge_descriptor.from_vertex,
                    base_out_connection=direct_edge_descriptor.to_vertex)
