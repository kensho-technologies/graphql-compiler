# Copyright 2019-present Kensho Technologies, LLC.
"""Implement renaming and suppressing parts of a GraphQL schema.

There are two ways to rename a part of a schema: 1-1 renaming and 1-many renaming.

1-1 renaming replaces the name of a type, field, or enum value in the schema. For instance, given
the following part of a schema:
    type Dog {
        name: String
    }
    type Human {
        pet: Dog
    }
1-1 renaming "Dog" to "NewDog" on a schema containing this object type (but not containing a
type named "NewDog") would produce a schema almost identical to the original schema except
with the NewDog object type replacing Dog everywhere it appears.
    type NewDog {
        name: String
    }
    type Human {
        pet: NewDog
    }
If "Dog" also appeared as a field in the schema's root type, it would be renamed to "NewDog" there
as well.

1-many renaming is an operation intended specifically for any of the following:
- fields in object types
- fields in interface types
- enum values
In 1-many renaming, the same field or enum value is mapped to multiple names. For instance, given
the following type in a schema:
    type Dog {
        name: String
    }
1-many renaming the "Dog" type's "name" field to "name" and "secondname" would produce a schema
almost identical to the original schema except with both fields representing the same underlying
data.
    type Dog {
        name: String
        secondname: String
    }

Suppressing part of the schema removes it altogether. For instance, given the following part of a
schema:
    type Dog {
        name: String
    }
suppressing "Dog" would produce an otherwise-identical schema but with that type (and therefore all
its fields) removed. If "Dog" also appeared as a field in the schema's root type, it would be
removed there as well.

Operations that are already supported:
- 1-1 renaming of object types, unions, enums, and interfaces.
- Suppressing types that don't implement an interface.
- Suppressing unions.

Operations that are not yet supported but will be implemented:
- Suppressions for fields, enums, enum values, interfaces, and types that implement interfaces.
- Renamings and suppressions for scalar types
- 1-1 and 1-many renamings for fields and enum values.

Renaming constraints:
- If you suppress all member types in a union, you must also suppress the union.
- If you suppress a type X, no other type Y may keep fields of type X (those fields must be
  suppressed, which requires field suppression which hasn't been implemented yet). However, if type
  X has a field of that type X, it is legal to suppress type X without explicitly suppressing that
  particular field.
- You may not suppress all types in the schema's root type.
- All names must be valid GraphQL names.
- Names may not conflict with each other. For instance, you may not rename both "Foo" and "Bar" to
  "Baz". You also may not rename anything to "Baz" if a type "Baz" already exists and is not also
  being renamed or suppressed.
"""
from collections import namedtuple
from typing import AbstractSet, Any, Dict, List, Mapping, Optional, Set, Tuple, TypeVar, Union, cast

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
    specified_scalar_types,
)
from graphql.language.visitor import IDLE, REMOVE, Visitor, VisitorAction, visit
import six

from ..ast_manipulation import get_ast_with_non_null_and_list_stripped
from .utils import (
    CascadingSuppressionError,
    SchemaNameConflictError,
    SchemaTransformError,
    check_ast_schema_is_valid,
    check_type_name_is_valid,
    get_copy_of_node_with_new_name,
    get_query_type_name,
    get_scalar_names,
)


RenamedSchemaDescriptor = namedtuple(
    "RenamedSchemaDescriptor",
    (
        "schema_ast",  # Document, AST representing the renamed schema
        "schema",  # GraphQLSchema, representing the same schema as schema_ast
        "reverse_name_map",  # Dict[str, str], renamed type/query type field name to original name
        # reverse_name_map only contains names that were changed
    ),
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
    UnionTypeDefinitionNode,
]
RenameTypesT = TypeVar("RenameTypesT", bound=RenameTypes)
# AST visitor functions can return a number of different things, such as returning a Node (to update
# that node) or returning a special value specified in graphql.visitor's VisitorAction.
VisitorReturnType = Union[Node, VisitorAction]


def rename_schema(
    schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]]
) -> RenamedSchemaDescriptor:
    """Create a RenamedSchemaDescriptor; rename/suppress types and root type fields using renamings.

    Any type, interface, enum, or fields of the root type/query type whose name
    appears in renamings will be renamed to the corresponding value if the value is not None. If the
    value is None, it will be suppressed in the renamed schema and queries will not be able to
    access it.

    Any such names that do not appear in renamings will be unchanged. Directives will never be
    renamed.

    In addition, some operations have not been implemented yet (see module-level docstring for more
    details).

    Args:
        schema_ast: represents a valid schema that does not contain extensions, input object
                    definitions, mutations, or subscriptions, whose fields of the query type share
                    the same name as the types they query. Not modified by this function
        renamings: maps original type name to renamed name or None (for type suppression). Any
                   name not in the dict will be unchanged

    Returns:
        RenamedSchemaDescriptor containing the AST of the renamed schema, and the map of renamed
        type/field names to original names. Only renamed names will be included in the map.

    Raises:
        - CascadingSuppressionError if a type suppression would require further suppressions
        - SchemaTransformError if renamings suppressed every type. Note that this is a superclass of
          CascadingSuppressionError, InvalidTypeNameError, SchemaStructureError, and
          SchemaNameConflictError, so handling exceptions of type SchemaTransformError will also
          catch all of its subclasses. This will change after the error classes are modified so that
          errors can be fixed programmatically, at which point it will make sense for the user to
          attempt to treat different errors differently
        - NotImplementedError if renamings attempts to suppress an enum, an interface, or a type
          implementing an interface
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

    _validate_renamings(schema_ast, renamings, query_type, scalars)

    # Rename types, interfaces, enums, unions and suppress types, unions
    schema_ast, reverse_name_map = _rename_and_suppress_types(
        schema_ast, renamings, query_type, scalars
    )
    reverse_name_map_changed_names_only = {
        renamed_name: original_name
        for renamed_name, original_name in six.iteritems(reverse_name_map)
        if renamed_name != original_name
    }

    schema_ast = _rename_and_suppress_query_type_fields(schema_ast, renamings, query_type)
    return RenamedSchemaDescriptor(
        schema_ast=schema_ast,
        schema=build_ast_schema(schema_ast),
        reverse_name_map=reverse_name_map_changed_names_only,
    )


def _validate_renamings(
    schema_ast: DocumentNode,
    renamings: Mapping[str, Optional[str]],
    query_type: str,
    scalars: AbstractSet[str],
) -> None:
    """Validate the renamings argument before attempting to rename the schema.

    Check for fields with suppressed types or unions whose members were all suppressed. Also,
    confirm renamings contains no enums, interfaces, or interface implementation suppressions
    because that hasn't been implemented yet. Confirm that no scalars would be suppressed or
    renamed.

    The input AST will not be modified.

    Args:
        schema_ast: represents a valid schema that does not contain extensions, input object
                    definitions, mutations, or subscriptions, whose fields of the query type share
                    the same name as the types they query. Not modified by this function
        renamings: maps original type name to renamed name or None (for type suppression). Any name
                   not in the dict will be unchanged
        query_type: name of the query type, e.g. 'RootSchemaQuery'
        scalars: set of all scalars used in the schema, including user defined scalars and used
                 builtin scalars, excluding unused builtins

    Raises:
        - CascadingSuppressionError if a type suppression would require further suppressions
        - NotImplementedError if renamings attempts to suppress an enum, an interface, or a type
          implementing an interface
    """
    _ensure_no_cascading_type_suppressions(schema_ast, renamings, query_type)
    _ensure_no_unsupported_operations(schema_ast, renamings, scalars)


def _ensure_no_cascading_type_suppressions(
    schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]], query_type: str
) -> None:
    """Check for fields with suppressed types or unions whose members were all suppressed."""
    visitor = CascadingSuppressionCheckVisitor(renamings, query_type)
    visit(schema_ast, visitor)
    if visitor.fields_to_suppress or visitor.union_types_to_suppress:
        error_message_components = [
            f"Type renamings {renamings} would require further suppressions to produce a valid "
            f"renamed schema."
        ]
        if visitor.fields_to_suppress:
            for object_type in visitor.fields_to_suppress:
                error_message_components.append(f"Object type {object_type} contains: ")
                error_message_components.extend(
                    (
                        f"field {field} of suppressed type "
                        f"{visitor.fields_to_suppress[object_type][field]}, "
                        for field in visitor.fields_to_suppress[object_type]
                    )
                )
            error_message_components.append(
                "A schema containing a field that is of a nonexistent type is invalid. When field "
                "suppression is supported, you can fix this problem by suppressing the fields "
                "shown above."
            )
        if visitor.union_types_to_suppress:
            for union_type in visitor.union_types_to_suppress:
                error_message_components.append(
                    f"Union type {union_type} has no non-suppressed members: "
                )
                error_message_components.extend(
                    (union_member.name.value for union_member in union_type.types)
                )
            error_message_components.append(
                "To fix this, you can suppress the union as well by adding union_type: None to the "
                "renamings argument when renaming types, for each value of union_type described "
                "here. Note that adding suppressions may lead to other types, fields, etc. "
                "requiring suppression so you may need to iterate on this before getting a legal "
                "schema."
            )
        raise CascadingSuppressionError("\n".join(error_message_components))


def _ensure_no_unsupported_operations(
    schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]], scalars: AbstractSet[str],
) -> None:
    """Check for unsupported renaming or suppression operations."""
    _ensure_no_unsupported_scalar_operations(renamings, scalars)
    _ensure_no_unsupported_suppressions(schema_ast, renamings)


def _ensure_no_unsupported_scalar_operations(
    renamings: Mapping[str, Optional[str]], scalars: AbstractSet[str],
) -> None:
    """Check for unsupported scalar operations."""
    unsupported_scalar_operations = {}  # Map scalars to value to be renamed.
    for scalar in scalars:
        if renamings.get(scalar, scalar) != scalar:
            # Then it either attempts to rename or suppress the scalar.
            unsupported_scalar_operations[scalar] = renamings.get(scalar)
    if unsupported_scalar_operations != {}:
        raise NotImplementedError(
            f"Scalar renaming and suppression is not implemented yet, but renamings attempted to "
            f"modify the following scalars: {unsupported_scalar_operations}. To fix this, remove "
            f"them from renamings."
        )


def _ensure_no_unsupported_suppressions(
    schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]]
) -> None:
    """Confirm renamings contains no enums, interfaces, or interface implementation suppressions."""
    visitor = SuppressionNotImplementedVisitor(renamings)
    visit(schema_ast, visitor)
    if (
        not visitor.unsupported_enum_suppressions
        and not visitor.unsupported_interface_suppressions
        and not visitor.unsupported_interface_implementation_suppressions
    ):
        return
    # Otherwise, attempted to suppress something we shouldn't suppress.
    error_message_components = [
        f"Type renamings {renamings} attempted to suppress parts of the schema for which "
        f"suppression is not implemented yet."
    ]
    if visitor.unsupported_enum_suppressions:
        error_message_components.append(
            f"Type renamings mapped these schema enums to None: "
            f"{visitor.unsupported_enum_suppressions}, attempting to suppress them. However, "
            f"schema renaming has not implemented enum suppression yet."
        )
    if visitor.unsupported_interface_suppressions:
        error_message_components.append(
            f"Type renamings mapped these schema interfaces to None: "
            f"{visitor.unsupported_interface_suppressions}, attempting to suppress them. However, "
            f"schema renaming has not implemented interface suppression yet."
        )
    if visitor.unsupported_interface_implementation_suppressions:
        error_message_components.append(
            f"Type renamings mapped these object types to None: "
            f"{visitor.unsupported_interface_implementation_suppressions}, attempting to suppress "
            f"them. Normally, this would be fine. However, these types each implement at least one "
            f"interface and schema renaming has not implemented this particular suppression yet."
        )
    error_message_components.append(
        "To avoid these suppressions, remove the mappings from the renamings argument."
    )
    raise NotImplementedError("\n".join(error_message_components))


def _rename_and_suppress_types(
    schema_ast: DocumentNode,
    renamings: Mapping[str, Optional[str]],
    query_type: str,
    scalars: AbstractSet[str],
) -> Tuple[DocumentNode, Dict[str, str]]:
    """Rename and suppress types, enums, interfaces using renamings.

    The query type will not be renamed.

    The input schema AST will not be modified.

    Args:
        schema_ast: schema that we're returning a modified version of
        renamings: maps original type name to renamed name or None (for type suppression). Any
                   name not in the dict will be unchanged
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


def _rename_and_suppress_query_type_fields(
    schema_ast: DocumentNode, renamings: Mapping[str, Optional[str]], query_type: str
) -> DocumentNode:
    """Rename or suppress all fields of the query type.

    The input schema AST will not be modified.

    Args:
        schema_ast: schema that we're returning a modified version of
        renamings: maps original type name to renamed name or None (for type suppression). Any name
                   not in the dict will be unchanged
        query_type: name of the query type, e.g. 'RootSchemaQuery'

    Returns:
        modified version of the input schema AST

    Raises:
        - SchemaTransformError if renamings suppressed every type
    """
    visitor = RenameQueryTypeFieldsVisitor(renamings, query_type)
    renamed_schema_ast = visit(schema_ast, visitor)
    return renamed_schema_ast


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
        self,
        renamings: Mapping[str, Optional[str]],
        query_type: str,
        scalar_types: AbstractSet[str],
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
        
        # pylint produces a false positive-- see issue here:
        # https://github.com/PyCQA/pylint/issues/3743
        self.builtin_types = frozenset(specified_scalar_types.keys())  # pylint: disable=no-member

    def _rename_or_suppress_or_ignore_name_and_add_to_record(
        self, node: RenameTypesT
    ) -> Union[RenameTypesT, VisitorAction]:
        """Specify input node change based on renamings. If node renamed, update reverse_name_map.

        Don't rename if the type is the query type or a builtin type.

        The input node will not be modified. reverse_name_map may be modified.

        Args:
            node: object representing an AST component, containing a .name attribute
                  corresponding to an AST node of type NameNode.

        Returns:
            Node object, REMOVE, or IDLE. The GraphQL library defines special return values REMOVE
            and IDLE to delete or do nothing with the node a visitor is currently at, respectively.
            If the current node is to be renamed, this function returns a Node object identical to
            the input node except with a new name. If it is to be suppressed, this function returns
            REMOVE. If neither of these are the case, this function returns IDLE.

        Raises:
            - InvalidTypeNameError if either the node's current name or renamed name is invalid
            - SchemaNameConflictError if the newly renamed node causes name conflicts with
              existing types, scalars, or builtin types
        """
        name_string = node.name.value

        if name_string == self.query_type or name_string in self.scalar_types:
            return IDLE

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
            return IDLE
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
            # Process the node by either renaming, suppressing, or not doing anything with it
            # (depending on what renamings specifies)
            return self._rename_or_suppress_or_ignore_name_and_add_to_record(
                cast(RenameTypes, node)
            )
        else:
            # All Node types should've been taken care of, this line should never be reached
            raise AssertionError('Unreachable code reached. Missed type: "{}"'.format(node_type))


class RenameQueryTypeFieldsVisitor(Visitor):
    def __init__(self, renamings: Mapping[str, Optional[str]], query_type: str) -> None:
        """Create a visitor for renaming or suppressing fields of the query type in a schema AST.

        Args:
            renamings: maps original type name to renamed name or None (for type suppression). Any
                       name not in the dict will be unchanged
            query_type: name of the query type (e.g. RootSchemaQuery)

        Raises:
            - SchemaTransformError if every field in the query type was suppressed
        """
        # Note that as field names and type names have been confirmed to match up, any renamed
        # query type field already has a corresponding renamed type.
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
        """If inside query type, rename or remove field as specified by renamings."""
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
    """Traverse the schema to check for cascading suppression issues.

    The fields_to_suppress attribute records non-suppressed fields that depend on suppressed types.
    The union_types_to_suppress attribute records unions that had all its members suppressed.

    After calling visit() on the schema using this visitor, if any of these attributes are non-empty
    then there are further suppressions required to produce a legal schema so the code should then
    raise a CascadingSuppressionError.

    """

    # For a type named T, and its field named F whose type has name V, this dict would be
    # {"T": {"F": "V"}}
    fields_to_suppress: Dict[str, Dict[str, str]]
    union_types_to_suppress: List[UnionTypeDefinitionNode]

    def __init__(self, renamings: Mapping[str, Optional[str]], query_type: str) -> None:
        """Create a visitor to check that suppression does not cause an illegal state.

        Args:
            renamings: maps original type name to renamed name or None (for type suppression). Any
                       name not in the dict will be unchanged
            query_type: name of the query type (e.g. RootSchemaQuery)
        """
        self.renamings = renamings
        self.query_type = query_type
        self.current_type: Optional[str] = None
        self.fields_to_suppress = {}
        self.union_types_to_suppress = []

    def enter_object_type_definition(
        self,
        node: ObjectTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """Record the current type that the visitor is traversing."""
        self.current_type = node.name.value

    def leave_object_type_definition(
        self,
        node: ObjectTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """Finish traversing the current type node."""
        self.current_type = None

    def enter_field_definition(
        self,
        node: FieldDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """Check that no type Y contains a field of type X, where X is suppressed."""
        if self.current_type == self.query_type:
            return IDLE
        # At a field of a type that is not the query type
        field_name = node.name.value
        field_type = get_ast_with_non_null_and_list_stripped(node.type).name.value
        if self.renamings.get(field_type, field_type):
            return IDLE
        # Reaching this point means this field is of a type to be suppressed.
        if self.current_type is None:
            raise AssertionError(
                "Entered a field not in any ObjectTypeDefinition scope because "
                "self.current_type is None"
            )
        if self.current_type == field_type:
            # Then node corresponds to a field belonging to type T that is also of type T.
            # Therefore, we don't need to explicitly suppress the field as well and this should not
            # raise errors.
            return IDLE
        if self.current_type not in self.fields_to_suppress:
            self.fields_to_suppress[self.current_type] = {}
        self.fields_to_suppress[self.current_type][field_name] = field_type
        return IDLE

    def enter_union_type_definition(
        self,
        node: UnionTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """Check that each union still has at least one non-suppressed member."""
        union_name = node.name.value
        # Check if all the union members are suppressed.
        for union_member in node.types:
            union_member_type = get_ast_with_non_null_and_list_stripped(union_member).name.value
            if self.renamings.get(union_member_type, union_member_type):
                # Then at least one member of the union is not suppressed, so there is no cascading
                # suppression error concern.
                return IDLE
        if self.renamings.get(union_name, union_name) is None:
            # If the union is also suppressed, then nothing needs to happen here
            return IDLE
        self.union_types_to_suppress.append(node)


class SuppressionNotImplementedVisitor(Visitor):
    """Traverse the schema to check for suppressions that are not yet implemented.

    Each attribute that mentions an unsupported suppression records the types that renamings
    attempts to suppress.

    After calling visit() on the schema using this visitor, if any of these attributes are non-empty
    then some suppressions specified by renamings are unsupported, so the code should then raise a
    NotImplementedError.

    """

    unsupported_enum_suppressions: Set[str]
    unsupported_interface_suppressions: Set[str]
    unsupported_interface_implementation_suppressions: Set[str]

    def __init__(self, renamings: Mapping[str, Optional[str]]) -> None:
        """Confirm renamings does not attempt to suppress enum/interface/interface implementation.

        Args:
            renamings: from original field name to renamed field name or None (for type
                       suppression). Any name not in the dict will be unchanged
        """
        self.renamings = renamings
        self.unsupported_enum_suppressions = set()
        self.unsupported_interface_suppressions = set()
        self.unsupported_interface_implementation_suppressions = set()

    def enter_enum_type_definition(
        self,
        node: EnumTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If renamings has enum suppression, record it for error message."""
        enum_name = node.name.value
        if self.renamings.get(enum_name, enum_name) is None:
            self.unsupported_enum_suppressions.add(enum_name)

    def enter_interface_type_definition(
        self,
        node: InterfaceTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If renamings has interface suppression, record it for error message."""
        interface_name = node.name.value
        if self.renamings.get(interface_name, interface_name) is None:
            self.unsupported_interface_suppressions.add(interface_name)

    def enter_object_type_definition(
        self,
        node: ObjectTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If renamings has interface implementation suppression, record it for error message."""
        if not node.interfaces:
            return
        object_name = node.name.value
        if self.renamings.get(object_name, object_name) is None:
            # Suppressing interface implementations isn't supported yet.
            self.unsupported_interface_implementation_suppressions.add(object_name)
