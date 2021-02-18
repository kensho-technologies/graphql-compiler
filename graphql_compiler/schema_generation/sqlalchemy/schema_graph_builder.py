# Copyright 2019-present Kensho Technologies, LLC.
from sqlalchemy import PrimaryKeyConstraint, UniqueConstraint

from ...global_utils import merge_non_overlapping_dicts
from ..schema_graph import (
    EdgeType,
    IndexDefinition,
    InheritanceStructure,
    PropertyDescriptor,
    SchemaGraph,
    VertexType,
    link_schema_elements,
)
from .edge_descriptors import validate_edge_descriptors
from .scalar_type_mapper import try_get_graphql_scalar_type
from .utils import (
    validate_that_tables_belong_to_the_same_metadata_object,
    validate_that_tables_have_primary_keys,
)


def get_sqlalchemy_schema_graph(vertex_name_to_table, edges):
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
        edges: dict, str -> EdgeDescriptor. This dictionary will be used to generate
                      EdgeType objects. The name of the EdgeType objects will be dictionary keys and
                      the connections will be deduced from the EdgeDescriptor objects.

    Returns:
        SchemaGraph reflecting the specified metadata.
    """
    validate_that_tables_belong_to_the_same_metadata_object(vertex_name_to_table.values())
    validate_edge_descriptors(vertex_name_to_table, edges)
    validate_that_tables_have_primary_keys(vertex_name_to_table.values())

    vertex_types = {
        vertex_name: _get_vertex_type_from_sqlalchemy_table(vertex_name, table)
        for vertex_name, table in vertex_name_to_table.items()
    }
    edge_types = {
        edge_name: _get_edge_type_from_edge(edge_name, edge_descriptor)
        for edge_name, edge_descriptor in edges.items()
    }
    elements = merge_non_overlapping_dicts(vertex_types, edge_types)
    elements.update(vertex_types)
    elements.update(edge_types)
    direct_superclass_sets = {element_name: set() for element_name in elements}
    inheritance_structure = InheritanceStructure(direct_superclass_sets)
    link_schema_elements(elements, inheritance_structure)
    indexes = _get_sqlalchemy_indexes(vertex_name_to_table, vertex_types)
    return SchemaGraph(elements, inheritance_structure, indexes)


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


def _get_edge_type_from_edge(edge_name, edge_descriptor):
    """Return the EdgeType corresponding to a SQL edge."""
    return EdgeType(
        edge_name,
        False,
        {},
        {},
        base_in_connection=edge_descriptor.from_vertex,
        base_out_connection=edge_descriptor.to_vertex,
    )


def _get_sqlalchemy_indexes(vertex_name_to_table, vertex_types):
    """Return the IndexDefinition objects corresponding to the indexes in the SQL tables."""
    # TODO(pmantica): Add indexes that do not correspond to either unique constraints nor
    #                 primary keys.
    index_definitions = set()
    for vertex_name, table in vertex_name_to_table.items():
        vertex_type = vertex_types[vertex_name]

        primary_key_constraints = []
        unique_constraints = []

        for constraint in table.constraints:
            if isinstance(constraint, PrimaryKeyConstraint):
                primary_key_constraints.append(constraint)
            elif isinstance(constraint, UniqueConstraint):
                unique_constraints.append(constraint)

        for primary_key_constraint in primary_key_constraints:
            # When a primary key constraint is created in a SQL database, an accompanying
            # primary key index is also created. However, SQLAlchemy explicitly does not include
            # primary key indexes in table.indexes. Therefore, we use the PrimaryKeyConstraint
            # to create the IndexDefinition.
            index_definition = _build_unique_index_definition(
                vertex_name, primary_key_constraint.columns, False
            )
            if _is_vertex_type_index_representable(index_definition, vertex_type):
                index_definitions.add(index_definition)

        # We choose to generate indexes directly from unique constraints instead of the
        # underlying unique indexes for two reasons:
        #   1. Unique indexes may be partial, meaning that they only index a subset of a
        #      table's rows, amd we do not have a good way of determining whether an index is
        #      partial or not.
        #      See https://github.com/kensho-technologies/graphql-compiler/issues/629
        #   2. Even though the underlying database might create a unique index for a
        #      unique constraint, SQLAlchemy does not. Meaning that if you create a unique
        #      constraint, you will not see a corresponding index in table.indexes.
        for unique_constraint in unique_constraints:
            # Some SQL backends, e.g. postgres, allow duplicate nulls in columns with covered by
            # unique indexes. However, other backends, e.g. mssql, do not. Therefore, we set
            # ignore_nulls=True to indicate that the backend may have duplicate nulls.
            index_definition = _build_unique_index_definition(
                vertex_name, unique_constraint.columns, True
            )
            if _is_vertex_type_index_representable(index_definition, vertex_type):
                index_definitions.add(index_definition)

    return index_definitions


def _build_unique_index_definition(vertex_name, columns, ignore_nulls):
    """Return the IndexDefinition of a unique index."""
    return IndexDefinition(
        name=None,
        base_classname=vertex_name,
        fields=frozenset(column.name for column in columns),
        unique=True,
        ordered=False,
        ignore_nulls=ignore_nulls,
    )


# The function below only works for indexes corresponding to VertexType objects since EdgeType
# objects have special 'in' and 'out' fields that reference base connections.
def _is_vertex_type_index_representable(index_definition, vertex_type):
    """Return True if all the index fields are represented as properties in the VertexType."""
    for field in index_definition.fields:
        if field not in vertex_type.properties:
            return False
    return True
