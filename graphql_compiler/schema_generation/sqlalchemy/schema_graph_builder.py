# Copyright 2019-present Kensho Technologies, LLC.
import warnings

from graphql.type import GraphQLBoolean, GraphQLFloat, GraphQLString
import six
import sqlalchemy.sql.sqltypes as sqltypes

from ...schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal, GraphQLInt
from ..schema_graph import PropertyDescriptor, SchemaGraph, VertexType


# TODO(pmantica1): Add scalar mapping for the following classes: Interval.
# We do not currently plan to add a mapping for JSON and Binary objects.
SQL_CLASS_TO_GRAPHQL_TYPE = {
    sqltypes.BIGINT: GraphQLInt,
    sqltypes.BigInteger: GraphQLInt,
    sqltypes.Boolean: GraphQLBoolean,
    sqltypes.CHAR: GraphQLString,
    sqltypes.CLOB: GraphQLString,
    sqltypes.Date: GraphQLDate,
    sqltypes.DATE: GraphQLDate,
    sqltypes.DateTime: GraphQLDateTime,
    sqltypes.DATETIME: GraphQLDateTime,
    sqltypes.Enum: GraphQLString,
    sqltypes.Float: GraphQLFloat,
    sqltypes.FLOAT: GraphQLFloat,
    sqltypes.INT: GraphQLInt,
    sqltypes.Integer: GraphQLInt,
    sqltypes.INTEGER: GraphQLInt,
    sqltypes.NCHAR: GraphQLString,
    sqltypes.Numeric: GraphQLDecimal,
    sqltypes.NUMERIC: GraphQLDecimal,
    sqltypes.NVARCHAR: GraphQLString,
    sqltypes.REAL: GraphQLFloat,
    sqltypes.SMALLINT: GraphQLInt,
    sqltypes.SmallInteger: GraphQLInt,
    sqltypes.String: GraphQLString,
    sqltypes.Text: GraphQLString,
    sqltypes.TEXT: GraphQLString,
    sqltypes.Time: GraphQLDateTime,
    sqltypes.TIME: GraphQLDateTime,
    sqltypes.TIMESTAMP: GraphQLDateTime,
    sqltypes.Unicode: GraphQLString,
    sqltypes.UnicodeText: GraphQLString,
    sqltypes.VARCHAR: GraphQLString,
}

UNSUPPORTED_PRIMITIVE_TYPES = frozenset({
    sqltypes.ARRAY,
    sqltypes.Binary,
    sqltypes.BINARY,
    sqltypes.Interval,
    sqltypes.JSON,
    sqltypes.LargeBinary,
    sqltypes.PickleType,
    sqltypes.VARBINARY,
})


# TODO(pmantica1): Map foreign keys to edges.
# TODO(pmantica1): Represent table inheritance in SchemaGraph.
# TODO(pmantica1): Add option to map tables to EdgeTypes instead of VertexTypes.
# TODO(pmantica1): Map arrays to GraphQLLists once the compiler is able to handle them.
def get_schema_graph_from_sql_alchemy_metadata(sqlalchemy_metadata):
    """Return the matching SchemaGraph for the SQLAlchemy Metadata object"""
    elements = dict()
    for table_name, table in six.iteritems(sqlalchemy_metadata.tables):
        elements[table_name] = _get_vertex_type_from_sqlalchemy_table(table)
    inheritance_sets = {element_name: {element_name} for element_name in elements}
    return SchemaGraph(elements, inheritance_sets)


def _try_get_graphql_scalar_type(column_name, column_type):
    """Return the matching GraphQLScalarType for the SQL datatype or None if none is found."""
    maybe_graphql_type = SQL_CLASS_TO_GRAPHQL_TYPE.get(type(column_type), None)
    if not maybe_graphql_type:
        # Trying to get the string representation of the SQLAlchemy JSON and ARRAY types
        # will lead to an error. We therefore use repr instead.
        warnings.warn(u'Ignoring column "{}" with unsupported SQL datatype class: {}'
                      .format(column_name, repr(column_type)))
    return maybe_graphql_type


# TODO(pmantica1): Address nullable types.
# TODO(pmantica1): Address default values of columns.
# TODO(pmantica1): Map Enum to the GraphQL Enum type.
def _get_vertex_type_from_sqlalchemy_table(table):
    """Return the VertexType corresponding to the SQLALchemyTable object."""
    properties = dict()
    for column in table.get_children():
        name = column.key
        default = None
        maybe_property_type = _try_get_graphql_scalar_type(name, column.type)
        if maybe_property_type:
            properties[name] = PropertyDescriptor(maybe_property_type, default)
    return VertexType(table.name, False, properties, {})
