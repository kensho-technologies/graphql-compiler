# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType
import six
import sqlalchemy

from . import is_vertex_field_name


# Complete schema information sufficient to compile GraphQL queries for most backends
CommonSchemaInfo = namedtuple('CommonSchemaInfo', (
    # GraphQLSchema
    'schema',

    # optional dict of GraphQL interface or type -> GraphQL union.
    # Used as a workaround for GraphQL's lack of support for
    # inheritance across "types" (i.e. non-interfaces), as well as a
    # workaround for Gremlin's total lack of inheritance-awareness.
    # The key-value pairs in the dict specify that the "key" type
    # is equivalent to the "value" type, i.e. that the GraphQL type or
    # interface in the key is the most-derived common supertype
    # of every GraphQL type in the "value" GraphQL union.
    # Recursive expansion of type equivalence hints is not performed,
    # and only type-level correctness of this argument is enforced.
    # See README.md for more details on everything this parameter does.
    # *****
    # Be very careful with this option, as bad input here will
    # lead to incorrect output queries being generated.
    # *****
    'type_equivalence_hints',
))


# Describes the intent to join two tables using the specified columns.
#
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

    # optional dict of GraphQL interface or type -> GraphQL union.
    # Used as a workaround for GraphQL's lack of support for
    # inheritance across "types" (i.e. non-interfaces), as well as a
    # workaround for Gremlin's total lack of inheritance-awareness.
    # The key-value pairs in the dict specify that the "key" type
    # is equivalent to the "value" type, i.e. that the GraphQL type or
    # interface in the key is the most-derived common supertype
    # of every GraphQL type in the "value" GraphQL union.
    # Recursive expansion of type equivalence hints is not performed,
    # and only type-level correctness of this argument is enforced.
    # See README.md for more details on everything this parameter does.
    # *****
    # Be very careful with this option, as bad input here will
    # lead to incorrect output queries being generated.
    # *****
    'type_equivalence_hints',

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
