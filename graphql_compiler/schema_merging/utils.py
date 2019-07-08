# Copyright 2019-present Kensho Technologies, LLC.
from graphql.type.definition import GraphQLScalarType


class SchemaError(Exception):
    """Parent of specific error classes. Raised if schema's structure is illegal."""


class SchemaRenameConflictError(SchemaError):
    """Raised when renaming types or root fields cause name conflicts."""


def get_query_type_name(schema):
    """Get the name of the query type of the input schema.

    Args:
        schema: GraphQLSchema

    Returns:
        str, name of the query type (e.g. RootSchemaQuery)
    """
    return schema.get_query_type().name


def get_scalar_names(schema):
    """Get names of all scalars used in the input schema.

    Includes all user defined scalars, as well as any builtin scalars used in the schema; excludes
    builtin scalars not used in the schema.

    Returns:
        Set[str], set of names of scalars used in the schema
    """
    type_map = schema.get_type_map()
    scalars = {
        type_name for type_name in type_map if isinstance(type_map[type_name], GraphQLScalarType)
    }
    return scalars
