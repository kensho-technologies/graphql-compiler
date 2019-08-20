# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql import GraphQLList
from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType
import six
import sqlalchemy

from . import is_vertex_field_name


# Complete schema information sufficient to compile GraphQL queries to SQLAlchemy
#
# It describes the tables that correspond to each type (object type, interface type or union type),
# and gives instructions on how to perform joins for each vertex field. The property fields on each
# type are implicitly mapped to columns with the same name on the corresponding table.
#
# NOTES:
# - RootSchemaQuery is a special type that does not need a corresponding table.
# - Builtin types like __Schema, __Type, etc. don't need corresponding tables.
# - Builtin fields like _x_count do not need corresponding columns.
SQLAlchemySchemaInfo = namedtuple('SQLAlchemySchemaInfo', (
    # GraphQLSchema
    'schema',

    # dict mapping every graphql object type or interface type name in the schema to
    # a sqlalchemy table
    'tables',

    # dict mapping every graphql object type or interface type name in the schema to:
    #    dict mapping every vertex field name at that type to a dict with keys:
    #        from_column_name: string, column name to join from
    #        to_column_name: string, column name to join to
    'junctions',

    # dict mapping every graphql object type or interface type name in the schema to:
    #    dict mapping every list-valued property field name to a dict with keys:
    #        junction_name: string, previously specified junction that provides the set contents
    #        value_column: string, the column in the junction target table that has the elements
    'set_valued_fields',
))


def make_sqlalchemy_schema_info(schema, tables, junctions, set_valued_fields, validate=True):
    """Make a SQLAlchemySchemaInfo if the input provided is valid.

    Args:
        schema: GraphQLSchema
        tables: dict mapping every graphql object type or interface type name in the schema to
                a sqlalchemy table
        junctions: dict mapping every graphql object type or interface type name in the schema to:
                       dict mapping every vertex field name at that type to a dict with keys:
                           from_column_name: string, column name to join from
                           to_column_name: string, column name to join to
        validate: Optional bool (default True), specifying whether to validate that the given
                  input is valid for creation of a SQLAlchemySchemaInfo. Consider not validating
                  to save on performance when dealing with a large schema.

        set_valued_fields: dict mapping graphql object and interface type names in the schema to:
                  dict mapping every list-valued property field name to a dict with keys:
                      junction_name: string, previously specified junction that provides the
                                     set contents
                      value_column: strine, the column in the junction target table that has
                                    the elements

    Returns:
        SQLAlchemySchemaInfo containing the input arguments provided
    """
    if validate:
        types_to_map = (GraphQLInterfaceType, GraphQLObjectType)
        builtin_fields = {
            '_x_count',
        }
        # TODO(bojanserafimov): More validation can be done:
        # - are the types of the columns compatible with the GraphQL type of the property field?
        # - do junctions join on columns on which the (=) operator makes sense?
        # - do inherited columns have exactly the same type on the parent and child table?
        for type_name, graphql_type in six.iteritems(schema.get_type_map()):
            if isinstance(graphql_type, types_to_map):
                if type_name != 'RootSchemaQuery' and not type_name.startswith('__'):
                    # Check existence of sqlalchemy table for this type
                    if type_name not in tables:
                        raise AssertionError(u'Table for type {} not found'.format(type_name))
                    table = tables[type_name]
                    if not isinstance(table, sqlalchemy.Table):
                        raise AssertionError(u'Table for type {} has wrong type {}'
                                             .format(type_name, type(table)))

                    # Check existence of all fields
                    for field_name, field_type in six.iteritems(graphql_type.fields):
                        if is_vertex_field_name(field_name):
                            if field_name not in junctions.get(type_name, {}):
                                raise AssertionError(u'No junction was specified for vertex '
                                                     u'field {} on type {}'
                                                     .format(field_name, type_name))
                        elif isinstance(field_type.type, GraphQLList):
                            if field_name not in set_valued_fields.get(type_name, {}):
                                raise AssertionError(u'Set valued property field {} on type {} '
                                                     u'has no implementation.'
                                                     .format(field_name, type_name))
                            set_implementation = set_valued_fields[type_name][field_name]
                            junction = set_implementation['junction']
                            if junction not in junctions.get(type_name, {}):
                                raise AssertionError(u'Implementation for set valued property '
                                                     u'field {} on type {} references junction {}, '
                                                     u'which is not specified.'
                                                     .format(field_name, type_name, junction))
                        else:
                            if field_name not in builtin_fields and field_name not in table.c:
                                raise AssertionError(u'Table for type {} has no column '
                                                     u'for property field {}'
                                                     .format(type_name, field_name))

    return SQLAlchemySchemaInfo(schema, tables, junctions, set_valued_fields)
