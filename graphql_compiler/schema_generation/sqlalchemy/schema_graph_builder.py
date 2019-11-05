# Copyright 2019-present Kensho Technologies, LLC.
from sqlalchemy import PrimaryKeyConstraint, UniqueConstraint

from ...global_utils import merge_non_overlapping_dicts
from ..schema_graph import (
    EdgeType, IndexDefinition, InheritanceStructure, PropertyDescriptor, SchemaGraph, VertexType,
    link_schema_elements
)
from .edge_descriptors import validate_edge_descriptors
from .scalar_type_mapper import try_get_graphql_scalar_type
from .utils import validate_that_tables_have_primary_keys


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
    validate_edge_descriptors(vertex_name_to_table, direct_edges)
    validate_that_tables_have_primary_keys(vertex_name_to_table.values())

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
    all_indexes = _get_sqlalchemy_indexes(vertex_name_to_table, vertex_types)
    return SchemaGraph(elements, inheritance_structure, all_indexes)


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


def _get_sqlalchemy_indexes(vertex_name_to_table, vertex_types):
    """Return the IndexDefinition objects corresponding to the indexes in the SQL tables."""
    index_definitions = set()
    for vertex_name, table in vertex_name_to_table.items():
        vertex_type = vertex_types[vertex_name]

        for index in table.indexes:
            index_definition = _build_index_definition(index.columns, index.unique, vertex_name)
            if _is_index_representable(index_definition, vertex_type):
                index_definitions.add(index_definition)

        for constraint in table.constraints:
            if isinstance(constraint, (PrimaryKeyConstraint, UniqueConstraint)):
                index_definition = _build_index_definition(constraint.columns, True, vertex_name)
                if _is_index_representable(index_definition, vertex_type):
                    index_definitions.add(index_definition)

    return index_definitions


def _build_index_definition(columns, unique, vertex_name):
    """Return an IndexDefinition encompassing specified columns."""
    column_names = frozenset(column.name for column in columns)

    # Some SQL backends allow duplicate nulls in columns with unique indexes.
    # However, other backends do not. Therefore, we set ignore_nulls=True to indicate
    # that the backend may have duplicate nulls.
    #
    # Also, since SQLAlchemy also does not contain information about whether an index is
    # ordered or not, we set ordered=False.
    index_definition = IndexDefinition(
        name=None,
        base_classname=vertex_name,
        fields=column_names,
        unique=unique,
        ordered=False,
        ignore_nulls=True
    )
    return index_definition


def _is_index_representable(index_definition, vertex_type):
    """Return True if all the fields in the index are represented as vertex_type properties."""
    for field in index_definition.fields:
        if field not in vertex_type.properties:
            return False
    return True

