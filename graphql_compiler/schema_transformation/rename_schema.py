# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from typing import AbstractSet, Any, Dict, List, Mapping, Tuple, TypeVar, Union, cast, Optional, Set

from graphql import (
    DocumentNode,
    EnumTypeDefinitionNode,
    FieldDefinitionNode,
    InterfaceTypeDefinitionNode,
    NamedTypeNode,
    Node,
    ObjectTypeDefinitionNode,
    UnionTypeDefinitionNode,
    build_ast_schema,
)
from graphql.language.visitor import IDLE, Visitor, visit, REMOVE
import six

from .utils import (
    SchemaNameConflictError,
    check_ast_schema_is_valid,
    check_type_name_is_valid,
    get_copy_of_node_with_new_name,
    get_query_type_name,
    get_scalar_names, CascadingSuppressionError, SchemaTransformError,
)
from ..ast_manipulation import get_ast_with_non_null_and_list_stripped

RenamedSchemaDescriptor = namedtuple(
    "RenamedSchemaDescriptor",
    (
        "schema_ast",  # Document, AST representing the renamed schema
        "schema",  # GraphQLSchema, representing the same schema as schema_ast
        "reverse_name_map",  # Dict[str, str], renamed type/query type field name to original name
        # reverse_name_map only contains names that were changed
    ),
)


# Union of classes of nodes to be renamed by an instance of RenameSchemaTypesVisitor. Note that
# RenameSchemaTypesVisitor also has a class attribute rename_types which parallels the classes here.
# This duplication is necessary due to language and linter constraints-- see the comment in the
# RenameSchemaTypesVisitor class for more information.
# Unfortunately, RenameTypes itself has to be a module attribute instead of a class attribute
# because a bug in flake8 produces a linting error if RenameTypes is a class attribute and we type
# hint the return value of the RenameSchemaTypesVisitor's _rename_name_and_add_to_record() method as
# RenameTypes. More on this here: https://github.com/PyCQA/pyflakes/issues/441
RenameTypes = Union[
    EnumTypeDefinitionNode,
    InterfaceTypeDefinitionNode,
    NamedTypeNode,
    ObjectTypeDefinitionNode,
    UnionTypeDefinitionNode,
]
RenameTypesT = TypeVar("RenameTypesT", bound=RenameTypes)
# AST visitor functions can return a number of different things, such as returning a Node (to update
# that node) or returning a special value defined in graphql.visitor such as REMOVE (to remove the
# node) and IDLE (to do nothing with the node). In the current GraphQL-core version (>=3,<3.1),
# REMOVE is set to the singleton object Ellipsis and IDLE is set to None. However, because these
# special values' underlying definitions can change, we can't type-hint functions returning a
# special value with anything more specific than Any. For more information, see:
# https://github.com/kensho-technologies/graphql-compiler/pull/834#discussion_r434622400
# We can update this type hint when a future GraphQL-core release organizes these special return
# values into an enum.
# https://github.com/graphql-python/graphql-core/issues/96
VisitorReturnType = Union[Node, Any]


def rename_schema(
    schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]]
) -> RenamedSchemaDescriptor:
    """Create a RenamedSchemaDescriptor; types and query type fields are renamed using renamings.

    Any type, interface, enum, or fields of the root type/query type whose name
    appears in renamings will be renamed to the corresponding value if the value is not None. If the
    value is None, it will be suppressed in the renamed schema and queries will not be able to
    access it.

    Any such names that do not appear in renamings will be unchanged.

    Scalars, directives, enum values, and fields not belonging to the root/query type will never be

    Args:
        schema_ast: represents a valid schema that does not contain extensions, input object
                    definitions, mutations, or subscriptions, whose fields of the query type share
                    the same name as the types they query. Not modified by this function
        renamings: maps original type/field names to renamed type/field names or None.
                   Type or query type field names that do not appear in the dict will be unchanged.
                   Any dict-like object that implements get(key, [default]) may also be used

    Returns:
        RenamedSchemaDescriptor, a namedtuple that contains the AST of the renamed schema, and the
        map of renamed type/field names to original names. Only renamed names will be included
        in the map.

    Raises:
        - InvalidTypeNameError if the schema contains an invalid type name, or if the user attempts
          to rename a type to an invalid name. A name is considered invalid if it does not consist
          of alphanumeric characters and underscores, if it starts with a numeric character, or
          if it starts with double underscores
        - SchemaStructureError if the schema does not have the expected form; in particular, if
          the AST does not represent a valid schema, if any query type field does not have the
          same name as the type that it queries, if the schema contains type extensions or
          input object definitions, or if the schema contains mutations or subscriptions
        - SchemaNameConflictError if there are conflicts between the renamed types or fields
    """
    # Check input schema satisfies various structural requirements
    check_ast_schema_is_valid(schema_ast)

    schema = build_ast_schema(schema_ast)
    query_type = get_query_type_name(schema)
    scalars = get_scalar_names(schema)

    _validate_renamings(schema_ast, renamings, query_type)

    # Rename types, interfaces, enums
    schema_ast, reverse_name_map = _rename_types(schema_ast, renamings, query_type, scalars)
    reverse_name_map_changed_names_only = {
        renamed_name: original_name
        for renamed_name, original_name in six.iteritems(reverse_name_map)
        if renamed_name != original_name
    }

    # Rename query type fields
    schema_ast = _rename_query_type_fields(schema_ast, renamings, query_type)
    return RenamedSchemaDescriptor(
        schema_ast=schema_ast,
        schema=build_ast_schema(schema_ast),
        reverse_name_map=reverse_name_map_changed_names_only,
    )


def _rename_types(
    schema_ast: DocumentNode,
    renamings: Mapping[str, Optional[str]],
    query_type: str,
    scalars: AbstractSet[str],
) -> Tuple[DocumentNode, Dict[str, str]]:
    """Rename types, enums, interfaces using renamings.

    The query type will not be renamed. Scalar types, field names, enum values will not be renamed.

    The input schema AST will not be modified.

    Args:
        schema_ast: schema that we're returning a modified version of
        renamings: maps original type/interface/enum name to renamed name. Any name not in the dict
                   will be unchanged
        query_type: name of the query type, e.g. 'RootSchemaQuery'
        scalars: set of all scalars used in the schema, including user defined scalars and used
                 builtin scalars, excluding unused builtins

    Returns:
        Tuple containing the modified version of the schema AST, and the renamed type name to
        original type name map. Map contains all non-suppressed types, including those that were not
        renamed.

    Raises:
        - InvalidTypeNameError if the schema contains an invalid type name, or if the user attempts
          to rename a type to an invalid name
        - SchemaNameConflictError if the rename causes name conflicts
    """
    visitor = RenameSchemaTypesVisitor(renamings, query_type, scalars)
    renamed_schema_ast = visit(schema_ast, visitor)
    return renamed_schema_ast, visitor.reverse_name_map


def _rename_query_type_fields(
    schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]], query_type: str
) -> DocumentNode:
    """Rename all fields of the query type.

    The input schema AST will not be modified.

    Args:
        schema_ast: schema that we're returning a modified version of
        renamings: maps original query type field name to renamed name. Any name not in the dict
                   will be unchanged
        query_type: name of the query type, e.g. 'RootSchemaQuery'

    Returns:
        modified version of the input schema AST

    Raises:
        - SchemaTransformError if renamings suppressed every type
    """
    visitor = RenameQueryTypeFieldsVisitor(renamings, query_type)
    renamed_schema_ast = visit(schema_ast, visitor)
    return renamed_schema_ast


def _validate_renamings(
    schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]], query_type: str
) -> None:
    """Validates the renamings argument before attempting to rename the schema.

    Check for fields with suppressed types or unions whose members were all suppressed. Also,
    confirm renamings contains no enums, interfaces, or interface implementation suppressions
    because that hasn't been implemented yet.

    The input AST will not be modified.

    Args:
        schema_ast: schema that we're returning a modified version of
        renamings: maps original field name to renamed name. If a name
                   does not appear in the dict, it will be unchanged
        query_type: name of the query type, e.g. 'RootSchemaQuery'

    Raises:
        - CascadingSuppressionError if a type suppression would require further suppressions
        - NotImplementedError if renamings attempts to suppress an enum or an interface
    """
    _check_for_cascading_type_suppression(schema_ast, renamings, query_type)
    _ensure_no_unsupported_suppression(schema_ast, renamings, query_type)


def _ensure_no_unsupported_suppression(schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]], query_type: str) -> None:
    """Confirm renamings contains no enums, interfaces, or interface implementation suppressions."""
    visitor = SuppressionNotImplementedVisitor(renamings, query_type)
    visit(schema_ast, visitor)
    if not visitor.attempted_enum_suppressions and not visitor.attempted_interface_suppressions and not visitor.unsupported_interface_implementation_suppressions:
        return
    # Otherwise, attempted to suppress something we shouldn't suppress.
    error_message_components = [
        f"Type renamings {renamings} attempted to suppress parts of the schema for which "
        f"suppression is not implemented yet, but is intended to be renamed."
    ]
    if visitor.attempted_enum_suppressions:
        error_message_components.append(f"Type renamings mapped these schema enums to None: {visitor.attempted_enum_suppressions}, attempting to suppress them. However, schema renaming has not implemented enum suppression yet.")
    if visitor.attempted_interface_suppressions:
        error_message_components.append(f"Type renamings mapped these schema interfaces to None: {visitor.attempted_interface_suppressions}, attempting to suppress them. However, schema renaming has not implemented enum suppression yet.")
    if visitor.unsupported_interface_implementation_suppressions:
        error_message_components.append(f"Type renamings mapped these object types to None: {visitor.unsupported_interface_implementation_suppressions}, attempting to suppress them. Normally, this would be fine. However, these types each implement at least one interface and schema renaming has not implemented this particular suppression yet.")
    error_message_components.append(f"To avoid these suppressions, remove the mappings from the renamings argument.")
    raise NotImplementedError("\n".join(error_message_components))


def _check_for_cascading_type_suppression(schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]], query_type: str) -> None:
    """Check for fields with suppressed types or unions whose members were all suppressed."""
    visitor = CascadingSuppressionCheckVisitor(renamings, query_type)
    visit(schema_ast, visitor)
    if visitor.fields_to_suppress or visitor.union_types_to_suppress:
        error_message_components = [
            f"Type renamings {renamings} suppressed types that require "
            f"further suppressions to produce a valid renamed schema.\n\n"
        ]
        if visitor.fields_to_suppress:
            error_message_components.append(
                f"There exists at least one field that depend on types that would be suppressed:\n"
            )
            for object_type in visitor.fields_to_suppress:
                error_message_components.append(f"Object type {object_type} contains ")
                error_message_components += [
                    f"field {field} of suppressed type {visitor.fields_to_suppress[object_type][field]}, "
                    for field in visitor.fields_to_suppress[object_type]
                ]
                error_message_components.append("\n")
            error_message_components.append(
                "\nField suppression hasn't been implemented yet, but when it is, you can fix this problem by suppressing the fields described here."
            )
        if visitor.union_types_to_suppress:
            error_message_components.append(
                f"There exists at least one union that would have all of its member types suppressed:\n"
            )
            for union_type in visitor.union_types_to_suppress:
                error_message_components.append(
                    f"Union type {union_type} has no non-suppressed members: "
                )
                error_message_components += [
                    get_ast_with_non_null_and_list_stripped(union_member).name.value
                    for union_member in union_type.types
                ]
                error_message_components.append("\n")
            error_message_components.append(
                f"\nTo fix this, you can suppress the union as well by adding `union_type: None` to the `renamings` argument of `rename_schema`, for each value of union_type described here. Note that "
                f"adding suppressions may lead to other types, fields, unions, etc. requiring "
                f"suppression so you may need to iterate on this before getting a legal schema."
            )
        raise CascadingSuppressionError("".join(error_message_components))


class RenameSchemaTypesVisitor(Visitor):
    """Traverse a Document AST, editing the names of nodes."""

    noop_types = frozenset(
        {
            "ArgumentNode",
            "BooleanValueNode",
            "DirectiveNode",
            "DirectiveDefinitionNode",
            "DocumentNode",
            "EnumValueNode",
            "EnumValueDefinitionNode",
            "FieldNode",
            "FieldDefinitionNode",
            "FloatValueNode",
            "FragmentDefinitionNode",
            "FragmentSpreadNode",
            "InlineFragmentNode",
            "InputObjectTypeDefinitionNode",
            "InputValueDefinitionNode",
            "IntValueNode",
            "ListTypeNode",
            "ListValueNode",
            "NameNode",
            "NonNullTypeNode",
            "ObjectFieldNode",
            "ObjectValueNode",
            "OperationDefinitionNode",
            "OperationTypeDefinitionNode",
            "ScalarTypeDefinitionNode",
            "SchemaDefinitionNode",
            "SelectionSetNode",
            "StringValueNode",
            "VariableNode",
            "VariableDefinitionNode",
            "SchemaExtensionNode",
            "InterfaceTypeExtensionNode",
            "UnionTypeExtensionNode",
            "EnumTypeExtensionNode",
            "ObjectTypeExtensionNode",
            "InputObjectTypeExtensionNode",
            "ScalarTypeExtensionNode",
        }
    )
    # rename_types must be a set of strings corresponding to the names of the classes in
    # RenameTypes. The duplication exists because introspection for Unions via typing.get_args()
    # doesn't exist until Python 3.8. In Python 3.8, this would be a valid way to define
    # rename_types:
    # rename_types = frozenset(cls.__name__ for cls in get_args(RenameTypes))  # type: ignore
    # Note: even with Python 3.8, the mypy version at the time of writing (version 0.770) doesn't
    # allow for introspection for Unions. mypy's maintainers recently merged a PR
    # (https://github.com/python/mypy/pull/8779) that permits this line of code, but did so after
    # the mypy 0.770 release. If we do end up removing the duplication at a later point but not
    # update the mypy version, we'd need to ignore it (as shown in the in-line comment).
    rename_types = frozenset(
        {
            "EnumTypeDefinitionNode",
            "InterfaceTypeDefinitionNode",
            "NamedTypeNode",
            "ObjectTypeDefinitionNode",
            "UnionTypeDefinitionNode",
        }
    )

    def __init__(
        self, renamings: Mapping[str, Optional[str]], query_type: str, scalar_types: AbstractSet[str]
    ) -> None:
        """Create a visitor for renaming types in a schema AST.

        Args:
            renamings: maps original type name to renamed name or None (for type suppression). Any
                       name not in the dict will be unchanged
            query_type: name of the query type (e.g. RootSchemaQuery), which will not be renamed
            scalar_types: set of all scalars used in the schema, including all user defined scalars
                          and any builtin scalars that were used
        """
        self.renamings = renamings
        self.reverse_name_map: Dict[str, str] = {}  # From renamed type name to original type name
        # reverse_name_map contains all non-suppressed types, including those that were unchanged
        self.query_type = query_type
        self.scalar_types = frozenset(scalar_types)
        self.builtin_types = frozenset({"String", "Int", "Float", "Boolean", "ID"})

    def _rename_name_and_add_to_record(self, node: RenameTypesT) -> RenameTypesT:
        """Change the name of the input node if necessary, add the name pair to reverse_name_map.

        Don't rename if the type is the query type, a scalar type, or a builtin type.

        The input node will not be modified. reverse_name_map may be modified.

        Args:
            node: object representing an AST component, containing a .name attribute
                  corresponding to an AST node of type NameNode.

        Returns:
            Node object or REMOVE. REMOVE is a special return value defined by the GraphQL library. A visitor function returns REMOVE to delete the node it's currently at. This function returns REMOVE to suppress types. If the current node is not to be suppressed, it returns a Node object identical to the input node, except with possibly a new name. If the name was not changed, the returned object is the exact same object as the input

        Raises:
            - InvalidTypeNameError if either the node's current name or renamed name is invalid
            - SchemaNameConflictError if the newly renamed node causes name conflicts with
              existing types, scalars, or builtin types
        """
        name_string = node.name.value

        if name_string == self.query_type or name_string in self.scalar_types:
            return node

        new_name_string = self.renamings.get(name_string, name_string)  # Default use original
        if new_name_string is None:
            # Suppress the type
            return REMOVE
        check_type_name_is_valid(new_name_string)

        if (
            new_name_string in self.reverse_name_map
            and self.reverse_name_map[new_name_string] != name_string
        ):
            raise SchemaNameConflictError(
                '"{}" and "{}" are both renamed to "{}"'.format(
                    name_string, self.reverse_name_map[new_name_string], new_name_string
                )
            )
        if new_name_string in self.scalar_types or new_name_string in self.builtin_types:
            raise SchemaNameConflictError(
                '"{}" was renamed to "{}", clashing with scalar "{}"'.format(
                    name_string, new_name_string, new_name_string
                )
            )

        self.reverse_name_map[new_name_string] = name_string
        if new_name_string == name_string:
            return node
        else:  # Make copy of node with the changed name, return the copy
            node_with_new_name = get_copy_of_node_with_new_name(node, new_name_string)
            return node_with_new_name

    def enter(
        self, node: Node, key: Any, parent: Any, path: List[Any], ancestors: List[Any],
    ) -> VisitorReturnType:
        """Upon entering a node, operate depending on node type."""
        node_type = type(node).__name__
        if node_type in self.noop_types:
            # Do nothing, continue traversal
            return IDLE
        elif node_type in self.rename_types:
            # Rename node, put name pair into record
            renamed_node = self._rename_name_and_add_to_record(cast(RenameTypes, node))
            if renamed_node is node:  # Name unchanged, continue traversal
                return IDLE
            else:
                # Name changed or suppressed, return new node, `visit` will make shallow copies
                # along path
                return renamed_node
        else:
            # All Node types should've been taken care of, this line should never be reached
            raise AssertionError('Unreachable code reached. Missed type: "{}"'.format(node_type))


class RenameQueryTypeFieldsVisitor(Visitor):
    def __init__(self, renamings: Mapping[str, Optional[str]], query_type: str) -> None:
        """Create a visitor for renaming fields of the query type in a schema AST.

        Args:
            renamings: maps original field name to renamed field name or (for type suppression). Any
                       name not in the dict will be unchanged
            query_type: name of the query type (e.g. RootSchemaQuery)
        """
        # Note that as field names and type names have been confirmed to match up, any renamed
        # query type field already has a corresponding renamed type. If no errors, due to either
        # invalid names or name conflicts, were raised when renaming type, no errors will occur when
        # renaming query type fields.
        self.in_query_type = False
        self.renamings = renamings
        self.query_type = query_type

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
        if not node.fields:
            raise SchemaTransformError(
                f"Type renamings {self.renamings} suppressed every type in the schema so it will "
                f"be impossible to query for anything. To fix this, check why the `renamings` "
                f"argument of `rename_schema` mapped every type to None."
            )
        if node.name.value == self.query_type:
            self.in_query_type = False

    def enter_field_definition(
        self,
        node: FieldDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> VisitorReturnType:
        """If inside the query type, rename field and add the name pair to reverse_field_map."""
        if self.in_query_type:
            field_name = node.name.value
            new_field_name = self.renamings.get(field_name, field_name)  # Default use original
            if new_field_name == field_name:
                return IDLE
            if new_field_name is None:
                # Suppress the type
                return REMOVE
            else:  # Make copy of node with the changed name, return the copy
                field_node_with_new_name = get_copy_of_node_with_new_name(node, new_field_name)
                return field_node_with_new_name

        return IDLE


class CascadingSuppressionCheckVisitor(Visitor):
    def __init__(self, renamings: Mapping[str, Optional[str]], query_type: str) -> None:
        """Create a visitor to check that suppression does not cause an illegal state.
        Args:
            renamings: Dict[str, Optional[str]], from original field name to renamed field name or
                       None (for type suppression). Any name not in the dict will be unchanged
            query_type: str, name of the query type (e.g. RootSchemaQuery)
        """
        self.renamings = renamings
        self.query_type = query_type
        self.current_type = None
        # Maps a type T to a dict which maps a field F belonging to T to the field's type T'
        self.fields_to_suppress: Dict[str, Dict[str, str]] = {}
        # Record any unions to suppress because all their types were suppressed
        self.union_types_to_suppress: List[UnionTypeDefinitionNode] = []

    def enter_object_type_definition(
        self,
        node: ObjectTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If the node's name matches the query type, record that we entered the query type."""
        self.current_type = node.name.value

    def leave_object_type_definition(
        self,
        node: ObjectTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If the node's name matches the query type, record that we left the query type."""
        self.current_type = None

    def enter_field_definition(
        self,
        node: FieldDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If not at query type, check that no field depends on a type that was suppressed."""
        if self.current_type == self.query_type:
            return None
        # At a field of a type that is not the query type
        field_name = node.name.value
        field_type = get_ast_with_non_null_and_list_stripped(node.type).name.value
        if self.renamings.get(field_type, field_type):
            return None
        # Reaching this point means this field is of a type to be suppressed.
        if self.current_type is None:
            raise AssertionError(
                f"Entered a field not in any ObjectTypeDefinition scope because "
                f"self.current_type is None"
            )
        if self.current_type == field_type:
            # Then node corresponds to a field belonging to type T that is also of type T.
            # Therefore, we don't need to explicitly suppress the field as well and this should not
            # raise errors.
            return None
        if self.current_type not in self.fields_to_suppress:
            self.fields_to_suppress[self.current_type] = {}
        self.fields_to_suppress[self.current_type][field_name] = field_type
        return None

    def enter_union_type_definition(
        self,
        node: UnionTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """Check that each union still has at least one member."""
        union_name = node.name.value
        # Check if al the union members are suppressed.
        for union_member in node.types:
            union_member_type = get_ast_with_non_null_and_list_stripped(union_member).name.value
            if self.renamings.get(union_member_type, union_member_type):
                # Then at least one member of the union is not suppressed, so there is no cascading
                # suppression error concern.
                return None
        if self.renamings.get(union_name):
            # If the union is also suppressed, then nothing needs to happen here
            return None
        self.union_types_to_suppress.append(node)


class SuppressionNotImplementedVisitor(Visitor):
    def __init__(self, renamings: Mapping[str, Optional[str]], query_type: str) -> None:
        """Create a visitor to check that renamings does not attempt to suppress enums/interfaces

        Args:
            renamings: from original field name to renamed field name or None (for type
                       suppression). Any name not in the dict will be unchanged
            query_type: name of the query type (e.g. RootSchemaQuery)
        """
        self.renamings = renamings
        self.query_type = query_type
        self.attempted_enum_suppressions: Set = set()
        self.attempted_interface_suppressions: Set = set()
        self.unsupported_interface_implementation_suppressions: Set[str] = set()

    def enter_enum_type_definition(
        self,
        node: EnumTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        enum_name = node.name.value
        if self.renamings.get(enum_name, enum_name) is None:
            self.attempted_enum_suppressions.add(enum_name)

    def enter_interface_type_definition(
        self,
        node: InterfaceTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        interface_name = node.name.value
        if self.renamings.get(interface_name, interface_name) is None:
            self.attempted_interface_suppressions.add(interface_name)

    def enter_object_type_definition(
        self,
        node: ObjectTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        if not node.interfaces:
            return
        if self.renamings.get(node.name.value, node.name.value) is None:
            # suppressing interface implementations isn't supported yet.
            self.unsupported_interface_implementation_suppressions.add(node.name.value)
