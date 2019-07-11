# Copyright 2019-present Kensho Technologies, LLC.
import re

from graphql.language.ast import NamedType
from graphql.language.visitor import Visitor, visit
from graphql.type.definition import GraphQLScalarType
import six


class SchemaTransformError(Exception):
    """Parent of specific error classes."""


class SchemaStructureError(SchemaTransformError):
    """Raised if an input schema's structure is illegal.

    This may happen if an AST cannot be built into a schema, if the schema contains disallowed
    components, or if the schema contains some field of the query type that is named differently
    from the type it queries.
    """


class InvalidTypeNameError(SchemaTransformError):
    """Raised if a type/field name is not valid.

    This may be raised if the input schema contains invalid names, or if the user attempts to
    rename a type/field to an invalid name. A name is considered valid if it consists of
    alphanumeric characters and underscores and doesn't start with a numeric character (as
    required by GraphQL), and doesn't start with double underscores as such type names are
    reserved for GraphQL internal use.
    """


class SchemaNameConflictError(SchemaTransformError):
    """Raised when renaming types or fields cause name conflicts."""


_graphql_type_name_pattern = re.compile(r'^[_a-zA-Z][_a-zA-Z0-9]*$')


def check_type_name_is_valid(name):
    """Check if input is a valid, nonreserved GraphQL type name.

    Args:
        name: str

    Raises:
        InvalidTypeNameError if the name doesn't consist of only alphanumeric characters and
        underscores, starts with a numeric character, or starts with double underscores
    """
    if not isinstance(name, str):
        raise InvalidTypeNameError(u'Name "{}" is not a string.'.format(name))
    if not _graphql_type_name_pattern.match(name):
        raise InvalidTypeNameError(u'"{}" is not a valid GraphQL name.'.format(name))
    if name.startswith('__'):
        raise InvalidTypeNameError(u'"{}" starts with two underscores, which is reserved for '
                               u'GraphQL internal use and is not allowed.'.format(name))


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

    Note: If the user defined a scalar that shares its name with a builtin introspection type
    (such as __Schema, __Directive, etc), it will not be listed in type_map and thus will not
    be included in the output.

    Returns:
        Set[str], set of names of scalars used in the schema
    """
    type_map = schema.get_type_map()
    scalars = {
        type_name
        for type_name, type_object in six.iteritems(type_map)
        if isinstance(type_object, GraphQLScalarType)
    }
    return scalars


class CheckQueryTypeFieldsNameMatchVisitor(Visitor):
    """Check that every query type field's name is identical to the type it queries.

    If not, raise SchemaStructureError.
    """
    def __init__(self, query_type):
        """Create a visitor for checking query type field names.

        Args:
            query_type: str, name of the query type (e.g. RootSchemaQuery)
        """
        self.query_type = query_type
        self.in_query_type = False

    def enter_ObjectTypeDefinition(self, node, *args):
        """If the node's name matches the query type, record that we entered the query type."""
        if node.name.value == self.query_type:
            self.in_query_type = True

    def leave_ObjectTypeDefinition(self, node, *args):
        """If the node's name matches the query type, record that we left the query type."""
        if node.name.value == self.query_type:
            self.in_query_type = False

    def enter_FieldDefinition(self, node, *args):
        """If inside the query type, check that the field and queried type names match.

        Raises:
            SchemaStructureError if the field name is not identical to the name of the type
            that it queries
        """
        if self.in_query_type:
            field_name = node.name.value
            type_node = node.type
            # NamedType node may be wrapped in several layers of NonNullType or ListType
            while not isinstance(type_node, NamedType):
                type_node = type_node.type
            queried_type_name = type_node.name.value
            if field_name != queried_type_name:
                raise SchemaStructureError(
                    u'Query type\'s field name "{}" does not match corresponding queried type '
                    u'name "{}"'.format(field_name, queried_type_name)
                )


def _check_query_type_fields_name_match(ast, query_type):
    """Check every query type field's name is identical to the type it queries.

    Args:
        ast: Document representing a schema
        query_type: str, name of the query type

    Raises:
        SchemaStructureError if any query type field name is not identical to the name of the
        type that it queries
    """
    visitor = CheckQueryTypeFieldsNameMatchVisitor(query_type)
    visit(ast, visitor)


def check_ast_schema_is_valid(ast, schema):
    """Check the schema satisfies structural requirements for rename and merge.

    In particular, check that the schema contains no mutations, no subscriptions, and all query
    type field names match the types they query.

    Args:
        ast: Document, representing a schema
        schema: GraphQLSchema, representing the same schema as ast

    Raises:
        SchemaStructureError if the schema contains mutations, contains subscriptions, or some
        query type field name does not match the type it queries.
    """
    if schema.get_mutation_type() is not None:
        raise SchemaStructureError(
            u'Renaming schemas that contain mutations is currently not supported.'
        )
    if schema.get_subscription_type() is not None:
        raise SchemaStructureError(
            u'Renaming schemas that contain subscriptions is currently not supported.'
        )

    query_type = get_query_type_name(schema)

    _check_query_type_fields_name_match(ast, query_type)
