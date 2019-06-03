# Copyright 2019-present Kensho Technologies, LLC.
import six
from sqlalchemy.schema import ColumnDefault

from ..schema_graph import InheritanceStructure, PropertyDescriptor, SchemaGraph, VertexType
from ..sqlalchemy.scalar_type_mapper import try_get_graphql_scalar_type


# TODO(pmantica1): Map foreign keys to edges.
# TODO(pmantica1): Represent table inheritance in SchemaGraph.
# TODO(pmantica1): Add option to map tables to EdgeTypes instead of VertexTypes.
# TODO(pmantica1): Parse SQLAlchemy indexes.
def get_schema_graph_from_sql_alchemy_metadata(sqlalchemy_metadata):
    """Return the matching SchemaGraph for the SQLAlchemy Metadata object"""
    elements = dict()
    for table_name, table in six.iteritems(sqlalchemy_metadata.tables):
        elements[table_name] = _get_vertex_type_from_sqlalchemy_table(table)
    direct_superclass_sets = {element_name: set() for element_name in elements}
    return SchemaGraph(elements, InheritanceStructure(direct_superclass_sets), set())


# TODO(pmantica1): Address nullable types.
# TODO(pmantica1): Map Enum to the GraphQL Enum type.
# TODO(pmantica1): Map arrays to GraphQLLists once the compiler is able to handle them.
# TODO(pmantica1): Possibly add a GraphQLInt64 type for SQL BigIntegers.
def _get_vertex_type_from_sqlalchemy_table(table):
    """Return the VertexType corresponding to the SQLALchemyTable object."""
    properties = dict()
    for column in table.get_children():
        name = column.key
        maybe_property_type = try_get_graphql_scalar_type(name, column.type)
        if maybe_property_type is not None:
            default = None
            # TODO(pmantica1): Parse Sequence type default values.
            # The type of default field of a Column object is either Sequence or ColumnDefault.
            if isinstance(column.default, ColumnDefault):
                default = column.default.arg if column.default is not None else None
            properties[name] = PropertyDescriptor(maybe_property_type, default)
    return VertexType(table.name, False, properties, {})
