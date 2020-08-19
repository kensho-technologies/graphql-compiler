# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy
import string
from typing import Dict, Set

from graphql import build_ast_schema, specified_scalar_types
from graphql.language.ast import FieldNode, InlineFragmentNode, NameNode
from graphql.language.visitor import Visitor, visit
from graphql.type.definition import GraphQLScalarType
from graphql.utilities.assert_valid_name import re_name
from graphql.validation import validate
import six

from ..ast_manipulation import get_ast_with_non_null_and_list_stripped
from ..exceptions import GraphQLError, GraphQLValidationError
from ..schema import FilterDirective, OptionalDirective, OutputDirective


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


class SchemaMergeNameConflictError(SchemaTransformError):
    """Raised when merging types or fields cause name conflicts.

    This may be raised if two merged schemas share an identically named field or type, or if a
    CrossSchemaEdgeDescriptor provided when merging schemas has an edge name that causes a
    name conflict with an existing field.
    """


class SchemaRenameNameConflictError(SchemaTransformError):
    """Raised when renaming causes name conflicts."""

    name_conflicts: Dict[str, Set[str]]
    renamed_to_builtin_scalar_conflicts: Dict[str, str]

    def __init__(
        self,
        name_conflicts: Dict[str, Set[str]],
        renamed_to_builtin_scalar_conflicts: Dict[str, str],
    ) -> None:
        """Record all renaming conflicts."""
        if not name_conflicts and not renamed_to_builtin_scalar_conflicts:
            raise ValueError(
                "Cannot raise SchemaRenameNameConflictError without at least one conflict, but "
                "name_conflicts and renamed_to_builtin_scalar_conflicts arguments were both empty "
                "dictionaries."
            )
        super().__init__()
        self.name_conflicts = name_conflicts
        self.renamed_to_builtin_scalar_conflicts = renamed_to_builtin_scalar_conflicts

    def __str__(self) -> str:
        """Explain renaming conflict and the fix."""
        name_conflicts_message = ""
        if self.name_conflicts:
            name_conflicts_message = (
                f"Applying the renaming would produce a schema in which multiple types have the "
                f"same name, which is an illegal schema state. The name_conflicts dict describes "
                f"these problems. For each key k in name_conflicts, name_conflicts[k] is the set "
                f"of types in the original schema that get mapped to k in the new schema. To fix "
                f"this, modify the renamings argument of rename_schema to ensure that no two types "
                f"in the renamed schema have the same name. name_conflicts: {self.name_conflicts}"
            )
        renamed_to_builtin_scalar_conflicts_message = ""
        if self.renamed_to_builtin_scalar_conflicts:
            renamed_to_builtin_scalar_conflicts_message = (
                f"Applying the renaming would rename type(s) to a name already used by a built-in "
                f"GraphQL scalar type. To fix this, ensure that no type name is mapped to a "
                f"scalar's name. The following dict maps each to-be-renamed type to the scalar "
                f"name it was mapped to: {self.renamed_to_builtin_scalar_conflicts}"
            )
        return "\n".join(
            filter(None, [name_conflicts_message, renamed_to_builtin_scalar_conflicts_message])
        )


class InvalidCrossSchemaEdgeError(SchemaTransformError):
    """Raised when a CrossSchemaEdge provided when merging schemas is invalid.

    This may be raised if the provided CrossSchemaEdge refers to nonexistent schemas,
    types not found in the specified schema, or fields not found in the specified type.
    """


class CascadingSuppressionError(SchemaTransformError):
    """Raised if existing suppressions would require further suppressions.

    This may be raised during schema renaming if it:
    * suppresses all the fields of a type but not the type itself
    * suppresses all the members of a union but not the union itself
    * suppresses a type X but there still exists a different type Y that has fields of type X.
    The error message will suggest fixing this illegal state by describing further suppressions, but
    adding these suppressions may lead to other types, unions, fields, etc. needing suppressions of
    their own. Most real-world schemas wouldn't have these cascading situations, and if they do,
    they are unlikely to have many of them, so the error messages are not meant to describe the full
    sequence of steps required to fix all suppression errors in one pass.
    """


_alphanumeric_and_underscore = frozenset(six.text_type(string.ascii_letters + string.digits + "_"))


# String representations for the GraphQL built-in scalar types
# pylint produces a false positive-- see issue here: https://github.com/PyCQA/pylint/issues/3743
builtin_scalar_type_names = frozenset(specified_scalar_types.keys())  # pylint: disable=no-member


def check_schema_identifier_is_valid(identifier):
    """Check if input is a valid identifier, made of alphanumeric and underscore characters.

    Args:
        identifier: str, used for identifying input schemas when merging multiple schemas

    Raises:
        - ValueError if the name is the empty string, or if it consists of characters other
          than alphanumeric characters and underscores
    """
    if not isinstance(identifier, str):
        raise ValueError('Schema identifier "{}" is not a string.'.format(identifier))
    if identifier == "":
        raise ValueError("Schema identifier must be a nonempty string.")
    illegal_characters = frozenset(identifier) - _alphanumeric_and_underscore
    if illegal_characters:
        raise ValueError(
            'Schema identifier "{}" contains illegal characters: {}'.format(
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
        raise InvalidTypeNameError('Name "{}" is not a string.'.format(name))
    if not re_name.match(name):
        raise InvalidTypeNameError('"{}" is not a valid GraphQL name.'.format(name))
    if name.startswith("__"):
        raise InvalidTypeNameError(
            '"{}" starts with two underscores, which is reserved for '
            "GraphQL internal use and is not allowed.".format(name)
        )


def get_query_type_name(schema):
    """Get the name of the query type of the input schema.

    Args:
        schema: GraphQLSchema

    Returns:
        str, name of the query type (e.g. RootSchemaQuery)
    """
    return schema.query_type.name


def get_custom_scalar_names(schema):
    """Get names of all custom scalars used in the input schema.

    Includes all user defined scalars; excludes builtin scalars.

    Note: If the user defined a scalar that shares its name with a builtin introspection type
    (such as __Schema, __Directive, etc), it will not be listed in type_map and thus will not
    be included in the output.

    Returns:
        Set[str], set of names of scalars used in the schema
    """
    type_map = schema.type_map
    custom_scalar_names = {
        type_name
        for type_name, type_object in six.iteritems(type_map)
        if isinstance(type_object, GraphQLScalarType) and type_name not in builtin_scalar_type_names
    }
    return custom_scalar_names


def try_get_ast_by_name_and_type(asts, target_name, target_type):
    """Return the ast in the list with the desired name and type, if found.

    Args:
        asts: List[Node] or None
        target_name: str, name of the AST we're looking for
        target_type: Node, the type of the AST we're looking for. Must be a type with a .name
                     attribute, e.g. Field, Directive

    Returns:
        Node, an element in the input list with the correct name and type, or None if not found
    """
    if asts is None:
        return None
    for ast in asts:
        if isinstance(ast, target_type) and ast.name.value == target_name:
            return ast
    return None


def try_get_inline_fragment(selections):
    """Return the unique inline fragment contained in selections, or None.

    Args:
        selections: List[Union[Field, InlineFragment]] or None

    Returns:
        InlineFragment if one is found in selections, None otherwise

    Raises:
        GraphQLValidationError if selections contains a InlineFragment along with a nonzero
        number of fields, or contains multiple InlineFragments
    """
    if selections is None:
        return None
    inline_fragments_in_selection = [
        selection for selection in selections if isinstance(selection, InlineFragmentNode)
    ]
    if len(inline_fragments_in_selection) == 0:
        return None
    elif len(inline_fragments_in_selection) == 1:
        if len(selections) == 1:
            return inline_fragments_in_selection[0]
        else:
            raise GraphQLValidationError(
                'Input selections "{}" contains both InlineFragments and Fields, which may not '
                "coexist in one selection.".format(selections)
            )
    else:
        raise GraphQLValidationError(
            'Input selections "{}" contains multiple InlineFragments, which is not allowed.'
            "".format(selections)
        )


def get_copy_of_node_with_new_name(node, new_name):
    """Return a node with new_name as its name and otherwise identical to the input node.

    Args:
        node: type Node, with a .name attribute. Not modified by this function
        new_name: str, name to give to the output node

    Returns:
        Node, with new_name as its name and otherwise identical to the input node
    """
    node_type = type(node).__name__
    allowed_types = frozenset(
        (
            "EnumTypeDefinitionNode",
            "FieldNode",
            "FieldDefinitionNode",
            "InterfaceTypeDefinitionNode",
            "NamedTypeNode",
            "ObjectTypeDefinitionNode",
            "UnionTypeDefinitionNode",
        )
    )
    if node_type not in allowed_types:
        raise AssertionError(
            "Input node {} of type {} is not allowed, only {} are allowed.".format(
                node, node_type, allowed_types
            )
        )
    node_with_new_name = copy(node)  # shallow copy is enough
    node_with_new_name.name = NameNode(value=new_name)
    return node_with_new_name


class CheckValidTypesAndNamesVisitor(Visitor):
    """Check that the AST does not contain invalid types or types with invalid names.

    If AST contains invalid types, raise SchemaStructureError; if AST contains types with
    invalid names, raise InvalidTypeNameError.
    """

    disallowed_types = frozenset(
        {  # types not supported in renaming or merging
            "InputObjectTypeDefinitionNode",
            "ObjectTypeExtensionNode",
        }
    )
    unexpected_types = frozenset(
        {  # types not expected to be found in schema definition
            "FieldNode",
            "FragmentDefinitionNode",
            "FragmentSpreadNode",
            "InlineFragmentNode",
            "ObjectFieldNode",
            "ObjectValueNode",
            "OperationDefinitionNode",
            "SelectionSetNode",
            "VariableNode",
            "VariableDefinitionNode",
        }
    )
    check_name_validity_types = frozenset(
        {  # nodes whose name need to be checked
            "EnumTypeDefinitionNode",
            "InterfaceTypeDefinitionNode",
            "ObjectTypeDefinitionNode",
            "ScalarTypeDefinitionNode",
            "UnionTypeDefinitionNode",
        }
    )

    def enter(self, node, key, parent, path, ancestors):
        """Raise error if node is of a invalid type or has an invalid name.

        Raises:
            - SchemaStructureError if the node is an InputObjectTypeDefinition,
              TypeExtensionDefinition, or a type that shouldn't exist in a schema definition
            - InvalidTypeNameError if a node has an invalid name
        """
        node_type = type(node).__name__
        if node_type in self.disallowed_types:
            raise SchemaStructureError('Node type "{}" not allowed.'.format(node_type))
        elif node_type in self.unexpected_types:
            raise SchemaStructureError('Node type "{}" unexpected in schema AST'.format(node_type))
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

    def enter_object_type_definition(self, node, *args):
        """If the node's name matches the query type, record that we entered the query type."""
        if node.name.value == self.query_type:
            self.in_query_type = True

    def leave_object_type_definition(self, node, *args):
        """If the node's name matches the query type, record that we left the query type."""
        if node.name.value == self.query_type:
            self.in_query_type = False

    def enter_field_definition(self, node, *args):
        """If inside the query type, check that the field and queried type names match.

        Raises:
            - SchemaStructureError if the field name is not identical to the name of the type
              that it queries
        """
        if self.in_query_type:
            field_name = node.name.value
            type_node = get_ast_with_non_null_and_list_stripped(node.type)
            queried_type_name = type_node.name.value
            if field_name != queried_type_name:
                raise SchemaStructureError(
                    'Query type\'s field name "{}" does not match corresponding queried type '
                    'name "{}"'.format(field_name, queried_type_name)
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
    schema = build_ast_schema(ast)

    if schema.mutation_type is not None:
        raise SchemaStructureError(
            "Renaming schemas that contain mutations is currently not supported."
        )
    if schema.subscription_type is not None:
        raise SchemaStructureError(
            "Renaming schemas that contain subscriptions is currently not supported."
        )

    visit(ast, CheckValidTypesAndNamesVisitor())

    query_type = get_query_type_name(schema)
    visit(ast, CheckQueryTypeFieldsNameMatchVisitor(query_type))


def is_property_field_ast(field):
    """Return True if selection is a property field, False if a vertex field.

    Args:
        field: Field object. It is considered to be a property field if it has no further
               selections

    Returns:
        True if the selection is a property field, False if it's a vertex field.
    """
    if isinstance(field, FieldNode):
        if (
            field.selection_set is None
            or field.selection_set.selections is None
            or field.selection_set.selections == []
        ):
            return True
        else:
            return False
    else:
        raise AssertionError('Input selection "{}" is not a Field.'.format(field))


class CheckQueryIsValidToSplitVisitor(Visitor):
    """Check the query is valid.

    In particular, check that it only contains supported directives, its property fields come
    before vertex fields in every scope, and that any scope containing a InlineFragment has
    nothing else in scope.
    """

    # This is very restrictive for now. Other cases (e.g. tags not crossing boundaries) are
    # also ok, but temporarily not allowed
    supported_directives = frozenset(
        (FilterDirective.name, OutputDirective.name, OptionalDirective.name,)
    )

    def enter_directive(self, node, *args):
        """Check that the directive is supported."""
        if node.name.value not in self.supported_directives:
            raise GraphQLValidationError(
                'Directive "{}" is not yet supported, only "{}" are currently '
                "supported.".format(node.name.value, self.supported_directives)
            )

    def enter_selection_set(self, node, *args):
        """Check selections are valid.

        If selections contains an InlineFragment, check that it is the only inline fragment in
        scope. Otherwise, check that property fields occur before vertex fields.

        Args:
            node: SelectionSet
        """
        selections = node.selections
        if len(selections) == 1 and isinstance(selections[0], InlineFragmentNode):
            return
        else:
            seen_vertex_field = False  # Whether we're seen a vertex field
            for field in selections:
                if isinstance(field, InlineFragmentNode):
                    raise GraphQLValidationError(
                        "Inline fragments must be the only selection in scope. However, in "
                        "selections {}, an InlineFragment coexists with other selections.".format(
                            selections
                        )
                    )
                if is_property_field_ast(field):
                    if seen_vertex_field:
                        raise GraphQLValidationError(
                            "In the selections {}, the property field {} occurs after a vertex "
                            "field or a type coercion statement, which is not allowed, as all "
                            "property fields must appear before all vertex fields.".format(
                                node.selections, field
                            )
                        )
                else:
                    seen_vertex_field = True


def check_query_is_valid_to_split(schema, query_ast):
    """Check the query is valid for splitting.

    In particular, ensure that the query validates against the schema, does not contain
    unsupported directives, and that in each selection, all property fields occur before all
    vertex fields.

    Args:
        schema: GraphQLSchema object
        query_ast: Document

    Raises:
        GraphQLValidationError if the query doesn't validate against the schema, contains
        unsupported directives, or some property field occurs after a vertex field in some
        selection
    """
    # Check builtin errors
    built_in_validation_errors = validate(schema, query_ast)
    if len(built_in_validation_errors) > 0:
        raise GraphQLValidationError("AST does not validate: {}".format(built_in_validation_errors))
    # Check no bad directives and fields are in order
    visitor = CheckQueryIsValidToSplitVisitor()
    visit(query_ast, visitor)
