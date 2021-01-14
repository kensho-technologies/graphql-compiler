# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy
import string
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Type, TypeVar, Union

from graphql import GraphQLSchema, build_ast_schema, specified_scalar_types
from graphql.language.ast import (
    DirectiveNode,
    DocumentNode,
    EnumTypeDefinitionNode,
    FieldDefinitionNode,
    FieldNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    InterfaceTypeDefinitionNode,
    NamedTypeNode,
    NameNode,
    Node,
    ObjectTypeDefinitionNode,
    ScalarTypeDefinitionNode,
    SelectionNode,
    SelectionSetNode,
    UnionTypeDefinitionNode,
)
from graphql.language.visitor import Visitor, visit
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


class InvalidNameError(SchemaTransformError):
    """Raised if a type/field name is not valid.

    This may be raised if the input schema contains invalid names, or if the user attempts to
    rename a type/field to an invalid name. A name is considered valid if it consists of
    alphanumeric characters and underscores and doesn't start with a numeric character (as required
    by GraphQL), and doesn't start with double underscores as such type names are reserved for
    GraphQL internal use.
    """


class SchemaMergeNameConflictError(SchemaTransformError):
    """Raised when merging types or fields cause name conflicts.

    This may be raised if two merged schemas share an identically named field or type, or if a
    CrossSchemaEdgeDescriptor provided when merging schemas has an edge name that causes a
    name conflict with an existing field.
    """


class SchemaRenameNameConflictError(SchemaTransformError):
    """Raised when renaming causes name conflicts."""

    type_name_conflicts: Dict[str, Set[str]]
    renamed_to_builtin_scalar_conflicts: Dict[str, str]
    field_name_conflicts: Dict[str, Dict[str, Set[str]]]

    def __init__(
        self,
        type_name_conflicts: Dict[str, Set[str]],
        renamed_to_builtin_scalar_conflicts: Dict[str, str],
        field_name_conflicts: Dict[str, Dict[str, Set[str]]],
    ) -> None:
        """Record all renaming conflicts."""
        if not any(
            [type_name_conflicts, renamed_to_builtin_scalar_conflicts, field_name_conflicts]
        ):
            raise ValueError(
                "Cannot raise SchemaRenameNameConflictError without at least one conflict, but "
                "all arguments were empty dictionaries."
            )
        super().__init__()
        self.type_name_conflicts = type_name_conflicts
        self.renamed_to_builtin_scalar_conflicts = renamed_to_builtin_scalar_conflicts
        self.field_name_conflicts = field_name_conflicts

    def __str__(self) -> str:
        """Explain renaming conflict and the fix."""
        type_name_conflicts_message = ""
        if self.type_name_conflicts:
            sorted_type_name_conflicts = [
                (new_type_name, sorted(original_schema_type_names))
                for new_type_name, original_schema_type_names in sorted(
                    self.type_name_conflicts.items()
                )
            ]
            type_name_conflicts_message = (
                f"Applying the renaming would produce a schema in which multiple types have the "
                f"same name, which is an illegal schema state. To fix this, modify the "
                f"type_renamings argument of rename_schema to ensure that no two types in the "
                f"renamed schema have the same name. The following is a list of tuples that "
                f"describes what needs to be fixed. Each tuple is of the form "
                f"(new_type_name, original_schema_type_names) where new_type_name is the type name "
                f"that would appear in the new schema and original_schema_type_names is a list of "
                f"types in the original schema that get mapped to new_type_name: "
                f"{sorted_type_name_conflicts}"
            )
        renamed_to_builtin_scalar_conflicts_message = ""
        if self.renamed_to_builtin_scalar_conflicts:
            sorted_renamed_to_builtin_scalar_conflicts = sorted(
                self.renamed_to_builtin_scalar_conflicts.items()
            )
            renamed_to_builtin_scalar_conflicts_message = (
                f"Applying the renaming would rename type(s) to a name already used by a built-in "
                f"GraphQL scalar type. To fix this, ensure that no type name is mapped to a "
                f"scalar's name. The following is a list of tuples that describes what needs to be "
                f"fixed. Each tuple is of the form (type_name, scalar_name) where type_name is the "
                f"original name of the type and scalar_name is the name of the scalar that the "
                f"type would be renamed to: {sorted_renamed_to_builtin_scalar_conflicts}"
            )
        field_name_conflicts_message = ""
        if self.field_name_conflicts:
            sorted_field_name_conflicts = [
                (
                    type_name,
                    [
                        (desired_field_name, sorted(original_field_names))
                        for desired_field_name, original_field_names in sorted(
                            field_renaming_conflicts_dict.items()
                        )
                    ],
                )
                for type_name, field_renaming_conflicts_dict in sorted(
                    self.field_name_conflicts.items()
                )
            ]
            field_name_conflicts_message = (
                f"Applying the renaming would produce a schema in which multiple fields belonging "
                f"to the same type have the same name, which is an illegal schema state. To fix "
                f"this, modify the field_renamings argument of rename_schema to ensure that within "
                f"each type in the renamed schema, no two fields have the same name. The following "
                f"is a list of tuples that describes what needs to be fixed. "
                f"Each tuple is of the form "
                f"(type_name, [(desired_field_name, original_field_names),...]) where type_name is "
                f"the type name that would appear in the original schema, desired_field_name is "
                f"the name of a field in the new schema, and original_field_names is a list of the "
                f"names of all the fields in the original schema that would be renamed to "
                f"desired_field_name: {sorted_field_name_conflicts}"
            )
        return "\n".join(
            filter(
                None,
                [
                    type_name_conflicts_message,
                    renamed_to_builtin_scalar_conflicts_message,
                    field_name_conflicts_message,
                ],
            )
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


class NoOpRenamingError(SchemaTransformError):
    """Raised if renamings contain no-op renames.

    No-op renames can occur in these ways:
    * type_renamings contains a string type_name but there doesn't exist a type in the schema named
      type_name
    * type_renamings maps a string type_name to itself, i.e. type_renamings[type_name] == type_name
    * There exists an object type T named type_name in the schema such that
      field_renamings[type_name] contains a string field_name but there doesn't exist a field named
      field_name belonging to T in the schema.
    * field_renamings contains a string type_name but there doesn't exist an object type in the
      schema named type_name
    * There exists an object type T named type_name in the schema such that
      field_renamings[type_name] 1:1 maps a string field_name to itself within a particular type,
      i.e. field_renamings[type_name][field_name] == [field_name]
    """

    no_op_type_renames: Set[str]
    no_op_nonexistent_type_field_renames: Set[str]
    no_op_field_renames: Dict[str, Set[str]]

    def __init__(
        self,
        no_op_type_renames: Set[str],
        no_op_field_renames: Dict[str, Set[str]],
        no_op_nonexistent_type_field_renames: Set[str],
    ) -> None:
        """Record all no-op renamings."""
        if not any([no_op_type_renames, no_op_field_renames, no_op_nonexistent_type_field_renames]):
            raise ValueError(
                "Cannot raise NoOpRenamingError without at least one invalid name, but "
                "all arguments were empty."
            )
        super().__init__()
        self.no_op_nonexistent_type_field_renames = no_op_nonexistent_type_field_renames
        self.no_op_type_renames = no_op_type_renames
        self.no_op_field_renames = no_op_field_renames

    def __str__(self) -> str:
        """Explain no-op renamings and the fix."""
        no_op_type_renames_message = ""
        if self.no_op_type_renames:
            no_op_type_renames_message = (
                f"type_renamings cannot have no-op renamings. However, the following entries exist "
                f"in the type_renamings argument, which either rename a type to itself or would "
                f"rename a type that doesn't exist in the schema, both of which are invalid: "
                f"{sorted(self.no_op_type_renames)}"
            )
        no_op_field_renames_message = ""
        if self.no_op_field_renames:
            sorted_no_op_field_renames = [
                (type_name, sorted(field_names))
                for type_name, field_names in sorted(self.no_op_field_renames.items())
            ]
            no_op_field_renames_message = (
                f"The field renamings for the following types would "
                f"either rename a field to itself or would rename a field that doesn't exist in "
                f"the schema, both of which are invalid. The following is a list of tuples that "
                f"describes what needs to be fixed for field renamings. Each tuple is of the form "
                f"(type_name, field_renamings) where type_name is the name of the type in the "
                f"original schema and field_renamings is a list of the fields that would be no-op "
                f"renamed: {sorted_no_op_field_renames}"
            )
        no_op_nonexistent_type_field_renames_message = ""
        if self.no_op_nonexistent_type_field_renames:
            no_op_nonexistent_type_field_renames_message = (
                f"The following entries exist in the field_renamings argument that correspond to "
                f"names of object types that either don't exist in the original schema or would "
                f"get suppressed. In other words, the field renamings for each of these types "
                f"would be no-ops: {sorted(self.no_op_nonexistent_type_field_renames)}"
            )
        return "\n".join(
            filter(
                None,
                [
                    no_op_type_renames_message,
                    no_op_field_renames_message,
                    no_op_nonexistent_type_field_renames_message,
                ],
            )
        )


_alphanumeric_and_underscore: FrozenSet[str] = frozenset(
    six.text_type(string.ascii_letters + string.digits + "_")
)


# String representations for the GraphQL built-in scalar types
# pylint produces a false positive-- see issue here: https://github.com/PyCQA/pylint/issues/3743
builtin_scalar_type_names: FrozenSet[str] = frozenset(
    specified_scalar_types.keys()  # pylint: disable=no-member
)


# Union of classes of nodes to be renamed or suppressed by an instance of RenameSchemaTypesVisitor.
# Note that RenameSchemaTypesVisitor also has a class attribute rename_types which parallels the
# classes here. This duplication is necessary due to language and linter constraints-- see the
# comment in the RenameSchemaTypesVisitor class for more information.
# Unfortunately, RenameTypes itself has to be a module attribute instead of a class attribute
# because a bug in flake8 produces a linting error if RenameTypes is a class attribute and we type
# hint the return value of the RenameSchemaTypesVisitor's
# _rename_or_suppress_or_ignore_name_and_add_to_record() method as RenameTypes. More on this here:
# https://github.com/PyCQA/pyflakes/issues/441
RenameTypes = Union[
    EnumTypeDefinitionNode,
    InterfaceTypeDefinitionNode,
    NamedTypeNode,
    ObjectTypeDefinitionNode,
    ScalarTypeDefinitionNode,
    UnionTypeDefinitionNode,
]
RenameTypesT = TypeVar("RenameTypesT", bound=RenameTypes)

# For the same reason as with RenameTypes, these types have to be written out explicitly instead of
# relying on allowed_types in get_copy_of_node_with_new_name.
# Unlike RenameTypes, RenameNodes also includes fields because it's used in the function
# get_copy_of_node_with_new_name which rename_query depends on to rename the root field in a query.
# Meanwhile, RenameTypes applies only for rename_schema and field renaming in the schema is not
# implemented yet.
RenameNodes = Union[
    RenameTypes,
    FieldNode,
    FieldDefinitionNode,
]
RenameNodesT = TypeVar("RenameNodesT", bound=RenameNodes)

# Contains the node types that may be renamed in rename_query. NamedTypeNode is here for type
# renaming and FieldNode is here for renaming field nodes in the root vertex (as described in
# RenameQueryVisitor).
RenameQueryNodeTypes = Union[NamedTypeNode, FieldNode]
RenameQueryNodeTypesT = TypeVar("RenameQueryNodeTypesT", bound=RenameQueryNodeTypes)


def check_schema_identifier_is_valid(identifier: str) -> None:
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


def is_valid_nonreserved_name(name: str) -> bool:
    """Check if input is a valid, non-reserved GraphQL name.

    A GraphQL name is valid iff it consists of only alphanumeric characters and underscores and
    does not start with a numeric character. It is non-reserved (i.e. not reserved for GraphQL
    internal use) if it does not start with double underscores.

    Args:
        name: to be checked

    Returns:
        True iff name is a valid, non-reserved GraphQL type name.
    """
    return bool(re_name.match(name)) and not name.startswith("__")


def get_query_type_name(schema: GraphQLSchema) -> str:
    """Get the name of the query type of the input schema (e.g. RootSchemaQuery)."""
    if schema.query_type is None:
        raise AssertionError(
            "Schema's query_type field is None, even though the compiler is read-only."
        )
    return schema.query_type.name


def try_get_ast_by_name_and_type(
    asts: Optional[Sequence[Node]], target_name: str, target_type: Type[Node]
) -> Optional[Node]:
    """Return the ast in the list with the desired name and type, if found.

    Args:
        asts: optional list of asts to search through
        target_name: name of the AST we're looking for
        target_type: type of the AST we're looking for. Instances of this type must have a .name
                     attribute, (e.g. FieldNode, DirectiveNode) and its .name attribute must have a
                     .value attribute.

    Returns:
        element in the input list with the correct name and type, or None if not found
    """
    if asts is None:
        return None
    for ast in asts:
        if isinstance(ast, target_type):
            if not (hasattr(ast, "name") and hasattr(ast.name, "value")):  # type: ignore
                # Can't type hint "has .name attribute"
                raise AssertionError(
                    f"AST {ast} is either missing a .name attribute or its .name attribute is "
                    f"missing a .value attribute. This should be impossible because target_type "
                    f"{target_type} must have a .name attribute, {target_type}'s .name attribute "
                    f"must have a .value attribute, and the ast must be of type {target_type}."
                )
            if ast.name.value == target_name:  # type: ignore
                # Can't type hint "has .name attribute"
                return ast
    return None


def try_get_inline_fragment(
    selections: Optional[List[SelectionNode]],
) -> Optional[InlineFragmentNode]:
    """Return the unique inline fragment contained in selections, or None.

    Args:
        selections: optional list of selections to search through

    Returns:
        inline fragment if one is found in selections, None otherwise

    Raises:
        GraphQLValidationError if selections contains an InlineFragmentNode along with a nonzero
        number of FieldNodes, contains multiple InlineFragmentNodes, or unexpectedly contains a
        SelectionNode that is neither an InlineFragmentNode nor a FieldNode.
    """
    if selections is None:
        return None
    for selection in selections:
        if not isinstance(selection, InlineFragmentNode) and not isinstance(selection, FieldNode):
            raise GraphQLValidationError(
                f"Unexpectedly received a selection of type {type(selection)}. "
                f"Only expected to receive FieldNode or InlineFragmentNode."
            )
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
                f'Input selections "{selections}" contains both InlineFragments and Fields, '
                f"which may not coexist in one selection."
            )
    else:
        raise GraphQLValidationError(
            f'Input selections "{selections}" contains multiple InlineFragments, which is '
            f"not allowed."
        )


def get_copy_of_node_with_new_name(node: RenameNodesT, new_name: str) -> RenameNodesT:
    """Return a node with new_name as its name and otherwise identical to the input node.

    Args:
        node: node to make a copy of
        new_name: name to give to the output node

    Returns:
        node with new_name as its name and otherwise identical to the input node
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
            "ScalarTypeDefinitionNode",
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
    invalid names, raise InvalidNameError.
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
    check_name_validity_types = (
        EnumTypeDefinitionNode,
        InterfaceTypeDefinitionNode,
        ObjectTypeDefinitionNode,
        ScalarTypeDefinitionNode,
        UnionTypeDefinitionNode,
    )

    def enter(
        self, node: Node, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> None:
        """Raise error if node is of a invalid type or has an invalid name.

        Raises:
            - SchemaStructureError if the node is an InputObjectTypeDefinition,
              TypeExtensionDefinition, or a type that shouldn't exist in a schema definition
            - InvalidNameError if a node has an invalid name
        """
        node_type = type(node).__name__
        if node_type in self.disallowed_types:
            raise SchemaStructureError('Node type "{}" not allowed.'.format(node_type))
        elif node_type in self.unexpected_types:
            raise SchemaStructureError('Node type "{}" unexpected in schema AST'.format(node_type))
        elif isinstance(node, self.check_name_validity_types):
            if not is_valid_nonreserved_name(node.name.value):
                raise InvalidNameError(
                    f"Node name {node.name.value} is not a valid, non-reserved GraphQL name. "
                    f"Valid, non-reserved GraphQL names must consist of only alphanumeric "
                    f"characters and underscores, must not start with a numeric character, and "
                    f"must not start with double underscores."
                )


class CheckQueryTypeFieldsNameMatchVisitor(Visitor):
    """Check that every query type field's name is identical to the type it queries.

    If not, raise SchemaStructureError.
    """

    def __init__(self, query_type: str) -> None:
        """Create a visitor for checking query type field names.

        Args:
            query_type: name of the query type (e.g. RootSchemaQuery)
        """
        self.query_type = query_type
        self.in_query_type = False

    def enter_object_type_definition(
        self,
        node: ObjectTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If the node's name matches the query type, record that we entered the query type."""
        if node.name.value == self.query_type:
            self.in_query_type = True

    def leave_object_type_definition(
        self,
        node: ObjectTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If the node's name matches the query type, record that we left the query type."""
        if node.name.value == self.query_type:
            self.in_query_type = False

    def enter_field_definition(
        self,
        node: FieldDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
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


def check_ast_schema_is_valid(ast: DocumentNode) -> None:
    """Check the schema satisfies structural requirements for rename and merge.

    In particular, check that the schema contains no mutations, no subscriptions, no
    InputObjectTypeDefinitions, no TypeExtensionDefinitions, all type names are valid and not
    reserved (not starting with double underscores), and all query type field names match the
    types they query.

    Args:
        ast: represents schema

    Raises:
        - SchemaStructureError if the AST cannot be built into a valid schema, if the schema
          contains mutations, subscriptions, InputObjectTypeDefinitions, TypeExtensionsDefinitions,
          or if any query type field does not match the queried type.
        - InvalidNameError if a type has a type name that is invalid or reserved
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


def is_property_field_ast(field: FieldNode) -> bool:
    """Return True iff selection is a property field (i.e. no further selections)."""
    if isinstance(field, FieldNode):
        # Unfortunately, since split_query.py hasn't been type-hinted yet, we can't rely on the
        # type-hint in this function to ensure field is a FieldNode yet.
        return (
            field.selection_set is None
            or field.selection_set.selections is None
            or field.selection_set.selections == []
        )
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
        (
            FilterDirective.name,
            OutputDirective.name,
            OptionalDirective.name,
        )
    )

    def enter_directive(
        self, node: DirectiveNode, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> None:
        """Check that the directive is supported."""
        if node.name.value not in self.supported_directives:
            raise GraphQLValidationError(
                'Directive "{}" is not yet supported, only "{}" are currently '
                "supported.".format(node.name.value, self.supported_directives)
            )

    def enter_selection_set(
        self, node: SelectionSetNode, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> None:
        """Check selections are valid.

        If selections contains an InlineFragment, check that it is the only inline fragment in
        scope. Otherwise, check that property fields occur before vertex fields.

        Args:
            node: selection set
            key: The index or key to this node from the parent node or Array.
            parent: the parent immediately above this node, which may be an Array.
            path: The key path to get to this node from the root node.
            ancestors: All nodes and Arrays visited before reaching parent of this node. These
                       correspond to array indices in ``path``. Note: ancestors includes arrays
                       which contain the parent of visited node.
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
                if isinstance(field, FragmentSpreadNode):
                    raise GraphQLValidationError(
                        f"Fragments (not to be confused with inline fragments) are not supported "
                        f"by the compiler. However, in SelectionSetNode {node}'s selections "
                        f"attribute {selections}, the field {field} is a FragmentSpreadNode named "
                        f"{field.name.value}."
                    )
                if not isinstance(field, FieldNode):
                    raise AssertionError(
                        f"The SelectionNode {field} in SelectionSetNode {node}'s selections "
                        f"attribute is not a FieldNode but instead has type {type(field)}."
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


def check_query_is_valid_to_split(schema: GraphQLSchema, query_ast: DocumentNode) -> None:
    """Check the query is valid for splitting.

    In particular, ensure that the query validates against the schema, does not contain
    unsupported directives, and that in each selection, all property fields occur before all
    vertex fields.

    Args:
        schema: schema the query is written against.
        query_ast: query to split.

    Raises:
        GraphQLValidationError if the query doesn't validate against the schema, contains
        unsupported directives, or some property field occurs after a vertex field in some
        selection.
    """
    # Check builtin errors
    built_in_validation_errors = validate(schema, query_ast)
    if len(built_in_validation_errors) > 0:
        raise GraphQLValidationError("AST does not validate: {}".format(built_in_validation_errors))
    # Check no bad directives and fields are in order
    visitor = CheckQueryIsValidToSplitVisitor()
    visit(query_ast, visitor)
