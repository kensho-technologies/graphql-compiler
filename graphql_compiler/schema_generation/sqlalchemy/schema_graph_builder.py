from collections import OrderedDict
from ..schema_graph import SchemaGraph, PropertyDescriptor, VertexType
from ...schema import GraphQLDateTime, GraphQLDate, GraphQLDecimal
import sqlalchemy.sql.sqltypes as sqltypes
from graphql.type import *
import warnings
import six


# TODO(pmantica1): Add scalar mapping for the following classes: Interval, and Time.
# We do not currently plan to add a mapping for JSON and Binary objects.
SQL_CLASS_TO_GRAPHQL_TYPE = OrderedDict({
    sqltypes.String: GraphQLString,
    sqltypes.Integer: GraphQLInt,
    sqltypes.Float: GraphQLFloat,
    sqltypes.Numeric: GraphQLDecimal,
    sqltypes.DateTime: GraphQLDateTime,
    sqltypes.Date: GraphQLDate,
    sqltypes.Boolean: GraphQLBoolean,
})


# TODO(pmantica1): Map foreign keys to edges.
# TODO(pmantica1): Represent table inheritance in SchemaGraph.
# TODO(pmantica1): Add option to map tables to EdgeTypes instead of VertexTypes.
# TODO(pmantica1): Map arrays to GraphQLLists.
def get_schema_graph_from_sql_alchemy_metadata(sqlalchemy_metadata):
    """Return the matching SchemaGraph for the SQLAlchemy Metadata object"""
    _validate_sql_to_graphql_is_toposorted_by_class_inheritance()
    elements = dict()
    for table_name, table in six.iteritems(sqlalchemy_metadata.tables):
        elements[table_name] = _get_vertex_type_from_sqlalchemy_table(table)
    inheritance_sets = {element_name: {element_name} for element_name in elements}
    return SchemaGraph(elements, inheritance_sets)


def _validate_sql_to_graphql_is_toposorted_by_class_inheritance():
    """Validate that SQL_SCALAR_CLASS_TO_GRAPHQL_TYPE dict is toposorted by class inheritance."""
    sql_classes = list(SQL_CLASS_TO_GRAPHQL_TYPE.keys())
    for i, class_ in enumerate(sql_classes):
        for other_class_ in sql_classes[i+1:]:
            assert not issubclass(other_class_, class_)


def _try_get_graphql_scalar_type(column_name, column_type):
    """Return the most precise GraphQLScalarType for the SQL datatype class.

    For instance, if class of the column_type is the Numeric class we return GraphQLDecimal.
    If the class of the column_type is Float, a subclass of Numeric, we return GraphQLFloat.
    """
    maybe_graphql_type = None
    for sql_class, graphql_type in SQL_CLASS_TO_GRAPHQL_TYPE.items():
        if isinstance(column_type, sql_class):
            maybe_graphql_type = graphql_type
            break
    if not maybe_graphql_type:
        # Try get the string representation of SQLAlchemy JSON and ARRAY types
        # will lead to an error. We therefore use repr instead.
        warnings.warn(u'Ignoring column "{}" with unsupported SQL datatype class: 'u'{}'
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
