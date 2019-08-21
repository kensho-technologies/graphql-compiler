# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType
import six
import sqlalchemy

from . import is_vertex_field_name


# Describes the intent to join two tables on equality of a column of theirs.
# The resulting join expression could be something like:
# JOIN origin_table.from_column = destination_table.to_column
#
# The type of join (inner vs left, etc.) is not specified.
# The tables are not specified.
DirectJoinDescriptor = namedtuple('DirectJoinDescriptor', (
    'from_column',  # The column in the source table we intend to join on.
    'to_column',    # The column in the destination table we intend to join on.
))


# Complete schema information sufficient to compile GraphQL queries to SQLAlchemy
#
# It describes the tables that correspond to each type (object type or interface type),
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

    # sqlalchemy.engine.interfaces.Dialect, specifying the dialect we are compiling for
    # (e.g. sqlalchemy.dialects.mssql.dialect()).
    'dialect',

    # dict mapping every graphql object type or interface type name in the schema to
    # a sqlalchemy table. Column types that do not exist for this dialect are not allowed.
    'tables',

    # dict mapping every graphql object type or interface type name in the schema to:
    #    dict mapping every vertex field name at that type to a DirectJoinDescriptor. The
    #    tables the join is to be performed on are not specified. They are inferred from
    #    the schema and the tables dictionary.
    'join_descriptors',
))


def make_sqlalchemy_schema_info(schema, dialect, tables, join_descriptors, validate=True):
    """Make a SQLAlchemySchemaInfo if the input provided is valid.

    See the documentation of SQLAlchemyschemaInfo for more detailed documentation of the args.

    Args:
        schema: GraphQLSchema
        dialect: sqlalchemy.engine.interfaces.Dialect
        tables: dict mapping every graphql object type or interface type name in the schema to
                a sqlalchemy table
        join_descriptors: dict mapping graphql object and interface type names in the schema to:
                             dict mapping every vertex field name at that type to a
                             DirectJoinDescriptor. The tables the join is to be performed on are not
                             specified. They are inferred from the schema and the tables dictionary.
        validate: Optional bool (default True), specifying whether to validate that the given
                  input is valid for creation of a SQLAlchemySchemaInfo. Consider not validating
                  to save on performance when dealing with a large schema.

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
        # - do joins join on columns on which the (=) operator makes sense?
        # - do inherited columns have exactly the same type on the parent and child table?
        # - are all the column types available in this dialect?
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
                            if field_name not in join_descriptors.get(type_name, {}):
                                raise AssertionError(u'No join descriptor was specified for vertex '
                                                     u'field {} on type {}'
                                                     .format(field_name, type_name))
                        else:
                            if field_name not in builtin_fields and field_name not in table.c:
                                raise AssertionError(u'Table for type {} has no column '
                                                     u'for property field {}'
                                                     .format(type_name, field_name))

    return SQLAlchemySchemaInfo(schema, dialect, tables, join_descriptors)
