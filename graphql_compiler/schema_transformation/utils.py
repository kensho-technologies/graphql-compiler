# Copyright 2019-present Kensho Technologies, LLC.
import string

from graphql import build_ast_schema
from graphql.language.ast import NamedType
from graphql.language.visitor import Visitor, visit
from graphql.type.definition import GraphQLScalarType
from graphql.utils.assert_valid_name import COMPILED_NAME_PATTERN
import six

from ..exceptions import GraphQLError


class SchemaTransformError(GraphQLError):
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
    """Raised when renaming or merging types or fields cause name conflicts."""


_alphanumeric_and_underscore = frozenset(six.text_type(string.ascii_letters + string.digits + '_'))


def check_schema_identifier_is_valid(identifier):
    """Check if input is a valid identifier, made of alphanumeric and underscore characters.

    Args:
        identifier: str, used for identifying input schemas when merging multiple schemas

    Raises:
        - ValueError if the name is the empty string, or if it consists of characters other
          than alphanumeric characters and underscores
    """
    if not isinstance(identifier, str):
        raise ValueError(u'Schema identifier "{}" is not a string.'.format(identifier))
    if identifier == '':
        raise ValueError(u'Schema identifier must be a nonempty string.')
    illegal_characters = frozenset(identifier) - _alphanumeric_and_underscore
    if illegal_characters:
        raise ValueError(
            u'Schema identifier "{}" contains illegal characters: {}'.format(
                identifier, illegal_characters
            )
        )


def check_type_name_is_valid(name):
    """Check if input is a valid, nonreserved GraphQL type name.

    Args:
        name: str

    Raises:
        - InvalidTypeNameError if the name doesn't consist of only alphanumeric characters and
          underscores, starts with a numeric character, or starts with double underscores
    """
    if not isinstance(name, str):
        raise InvalidTypeNameError(u'Name "{}" is not a string.'.format(name))
    if not COMPILED_NAME_PATTERN.match(name):
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


class CheckValidTypesAndNamesVisitor(Visitor):
    """Check that the AST does not contain invalid types or types with invalid names.

    If AST contains invalid types, raise SchemaStructureError; if AST contains types with
    invalid names, raise InvalidTypeNameError.
    """
    disallowed_types = frozenset({  # types not supported in renaming or merging
        'InputObjectTypeDefinition',
        'TypeExtensionDefinition',
    })
    unexpected_types = frozenset({  # types not expected to be found in schema definition
        'Field',
        'FragmentDefinition',
        'FragmentSpread',
        'InlineFragment',
        'ObjectField',
        'ObjectValue',
        'OperationDefinition',
        'SelectionSet',
        'Variable',
        'VariableDefinition',
    })
    check_name_validity_types = frozenset({  # nodes whose name need to be checked
        'EnumTypeDefinition',
        'InterfaceTypeDefinition',
        'ObjectTypeDefinition',
        'ScalarTypeDefinition',
        'UnionTypeDefinition',
    })

    def enter(self, node, key, parent, path, ancestors):
        """Raise error if node is of a invalid type or has an invalid name.

        Raises:
            - SchemaStructureError if the node is an InputObjectTypeDefinition,
              TypeExtensionDefinition, or a type that shouldn't exist in a schema definition
            - InvalidTypeNameError if a node has an invalid name
        """
        node_type = type(node).__name__
        if node_type in self.disallowed_types:
            raise SchemaStructureError(
                u'Node type "{}" not allowed.'.format(node_type)
            )
        elif node_type in self.unexpected_types:
            raise SchemaStructureError(
                u'Node type "{}" unexpected in schema AST'.format(node_type)
            )
        elif node_type in self.check_name_validity_types:
            check_type_name_is_valid(node.name.value)


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
            - SchemaStructureError if the field name is not identical to the name of the type
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


def check_ast_schema_is_valid(ast):
    """Check the schema satisfies structural requirements for rename and merge.

    In particular, check that the schema contains no mutations, no subscriptions, no
    InputObjectTypeDefinitions, no TypeExtensionDefinitions, all type names are valid and not
    reserved (not starting with double underscores), and all query type field names match the
    types they query.

    Args:
        ast: Document, representing a schema

    Raises:
        - SchemaStructureError if the AST cannot be built into a valid schema, if the schema
          contains mutations, subscriptions, InputObjectTypeDefinitions, TypeExtensionsDefinitions,
          or if any query type field does not match the queried type.
        - InvalidTypeNameError if a type has a type name that is invalid or reserved
    """
    try:
        schema = build_ast_schema(ast)
    except Exception as e:  # Can't be more specific -- see graphql/utils/build_ast_schema.py
        raise SchemaStructureError(u'Input is not a valid schema. Message: {}'.format(e))

    if schema.get_mutation_type() is not None:
        raise SchemaStructureError(
            u'Renaming schemas that contain mutations is currently not supported.'
        )
    if schema.get_subscription_type() is not None:
        raise SchemaStructureError(
            u'Renaming schemas that contain subscriptions is currently not supported.'
        )

    visit(ast, CheckValidTypesAndNamesVisitor())

    query_type = get_query_type_name(schema)
    visit(ast, CheckQueryTypeFieldsNameMatchVisitor(query_type))
