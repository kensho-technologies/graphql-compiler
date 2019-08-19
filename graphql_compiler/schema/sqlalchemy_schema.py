# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
import sqlalchemy
import six

from graphql import GraphQLList
from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType, GraphQLUnionType


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
    'schema',     # GraphQLSchema
    'tables',     # dict mapping every graphql object type or interface type name in the schema to
                  # a sqlalchemy table
    'junctions',  # dict mapping every graphql object type or interface type name in the schema to:
                  #    dict mapping every vertex field name at that type to a dict with keys:
                  #        from_column_name: string, column name to join from
                  #        to_column_name: string, column name to join to
))


def make_sqlalchemy_schema_info(schema, tables, junctions, validate=True):
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

    Returns:
        SQLAlchemySchemaInfo containing the input arguments provided
    """
    if validate:
        types_mapped_to_tables = (GraphQLInterfaceType, GraphQLObjectType, GraphQLUnionType)
        builtin_types = {
            '__Schema',
            '__Type',
            '__Field',
            '__InputValue',
            '__EnumValue',
            '__Directive',
        }
        builtin_fields = {
            '_x_count',
        }
        for type_name, graphql_type in six.iteritems(schema.get_type_map()):
            if isinstance(graphql_type, types_mapped_to_tables):
                if type_name != 'RootSchemaQuery' and type_name not in builtin_types:
                    # Check existence of sqlalchemy table for this type
                    if type_name not in tables:
                        raise AssertionError(u'Table for type {} not found'.format(type_name))
                    table = tables[type_name]
                    if not isinstance(table, sqlalchemy.Table):
                        raise AssertionError(u'Table for type {} has wrong type {}'
                                             .format(type_name, type(table)))

                    # Check existence of all fields
                    for field_name, field_type in six.iteritems(graphql_type.fields):
                        is_vertex_field = (field_name.startswith('out_') or
                                           field_name.startswith('in_'))
                        if is_vertex_field:
                            if field_name not in junctions[type_name]:
                                raise AssertionError(u'No junction was specified for vertex '
                                                     u'field {} on type {}'
                                                     .format(field_name, type_name))
                        else:
                            # TODO(bojanserafimov): We have no SQL representation of list types yet,
                            #                       so they are excused.
                            # XXX should I just remove list types from the schema?
                            if not isinstance(field_type.type, GraphQLList):
                                if field_name not in builtin_fields and field_name not in table.c:
                                    raise AssertionError(u'Table for type {} has no column '
                                                         u'for property field {}'
                                                         .format(type_name, field_name))

    return SQLAlchemySchemaInfo(schema, tables, junctions)
