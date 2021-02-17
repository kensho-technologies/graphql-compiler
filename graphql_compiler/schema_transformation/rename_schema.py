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

For both 1-1 or 1-many renaming, renamings only apply to types, fields, and enum values that exist
in the original schema. For example, if a schema contains a type named "Foo" and a type named "Bar"
but not a type named "Baz" and type_renamings maps "Foo" to "Bar" and "Bar" to "Baz", then the
renamed schema will contain a type named "Bar" (corresponding to the original schema's type "Foo")
and a type named "Baz" (corresponding to the original schema's type "Bar"), instead of containing
two types both named "Baz".

Field renamings may produce "illegal" schema states in the process of renaming, but they are legal
as long as the end result is a legal schema. For example, if a schema contains a type named
type_name that contains just two fields named "foo" and "bar", and
    field_renamings == {"type_name": {"foo": {"foo", "bar"}, "bar": {"baz", "quux"}}}
this would be a legal renaming. Even though applying the renaming for "foo" first would produce an
intermediate state with two fields named "bar", the end result has no naming collisions.

Field renaming operations take place before type renamings, so all field renamings should be
specified in terms of the name of the type in the original schema. For example, if a schema
contains a single type named "Foo" that contains a field named "bar", then to produce a schema
with a single type named "Baz" containing a field named "quux", the renamings could be as
follows:
    type_renamings == {"Foo": "Baz"}
    field_renamings == {"Foo": {"bar": "quux"}}
Note that field_renamings == {"Baz": {"bar": "quux"}} would not produce the desired
result because "Baz" is not a type in the original schema.

Operations that are already supported:
- 1-1 renaming of object types, unions, enums, and interfaces.
- Suppressing types that don't implement an interface.
- Suppressing unions.
- 1-1 and 1-many renamings for fields belonging to object types.
- Suppressions for fields belonging to object types.
- Renamings and suppressions for scalar types.

Operations that are not yet supported but will be implemented:
- Suppressions for enums, interfaces, and object types that implement interfaces.
- Renamings and suppressions for fields that belong to either interface types or object types that
  implement interfaces.
- Renamings and suppressions for enum values.

Renaming constraints:
- If you suppress all member types in a union, you must also suppress the union.
- If you suppress a type Foo, no other type Bar may keep fields of type Foo (those fields must be
  suppressed). However, if type Foo has a field of that type Foo, it is legal to suppress type Foo
  without explicitly suppressing that particular field.
- If you suppress all the fields of a type Foo, then the type Foo must also be suppressed in
  type_renamings.
- You may not suppress all types in the schema's root type.
- All names must be valid GraphQL names.
- Names may not conflict with each other. For instance, you may not rename both "Foo" and "Bar" to
  "Baz". You also may not rename anything to "Baz" if a type "Baz" already exists and is not also
  being renamed or suppressed. The same rules apply for fields that belong to the same type, since
  they share a namespace as well.
- No-op renamings are not allowed meaning that:
  - A string type_name may be in type_renamings only if there exists a type in the original schema
    named type_name (since otherwise that entry would not affect any type in the schema).
  - If string type_name is in type_renamings, then type_renamings[type_name] != type_name (since
    if they were the same, then applying the renaming would not change the type named type_name).
  - A string type_name may be in field_renamings only if there exists a type in the original
    schema named type_name and that type wouldn't get suppressed by type_renamings (since
    otherwise that entry would not affect any type in the schema).
  - If type_name is in field_renamings, a string field_name may be in field_renamings[type_name]
    only if the type named type_name in the original schema contains a field named field_name in the
    original schema (since otherwise that entry would not affect any field in the schema).
  - If type_name is in field_renamings and field_name is in field_renamings[type_name], then
    field_renamings[type_name][field_name] != {field_name} (since if this were the case, then
    applying the renaming would not change the field named field_name).

"""
from collections import namedtuple
from copy import copy
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple, Union, cast

from graphql import (
    DocumentNode,
    EnumTypeDefinitionNode,
    FieldDefinitionNode,
    InterfaceTypeDefinitionNode,
    Node,
    ObjectTypeDefinitionNode,
    UnionTypeDefinitionNode,
    build_ast_schema,
)
from graphql.language.visitor import IDLE, REMOVE, Visitor, VisitorAction, visit
from graphql.pyutils import FrozenList
import six

from ..ast_manipulation import get_ast_with_non_null_and_list_stripped
from .utils import (
    CascadingSuppressionError,
    InvalidNameError,
    NoOpRenamingError,
    RenameTypes,
    RenameTypesT,
    SchemaRenameNameConflictError,
    SchemaTransformError,
    builtin_scalar_type_names,
    check_ast_schema_is_valid,
    get_copy_of_node_with_new_name,
    get_query_type_name,
    is_valid_nonreserved_name,
)


RenamedSchemaDescriptor = namedtuple(
    "RenamedSchemaDescriptor",
    (
        "schema_ast",  # Document, AST representing the renamed schema
        "schema",  # GraphQLSchema, representing the same schema as schema_ast
        "reverse_name_map",  # Dict[str, str], renamed type/query type field name to original name
        # reverse_name_map only contains names that were changed
        "reverse_field_name_map",  # Dict[str, Dict[str, str]], mappings type names in the original
        # schema to dicts mapping renamed field names to their original names. It contains entries
        # solely for fields whose names were renamed.
    ),
)


# AST visitor functions can return a number of different things, such as returning a Node (to update
# that node) or returning a special value specified in graphql.visitor's VisitorAction.
VisitorReturnType = Union[Node, VisitorAction]


def rename_schema(
    schema_ast: DocumentNode,
    type_renamings: Mapping[str, Optional[str]],
    field_renamings: Mapping[str, Mapping[str, Set[str]]],
) -> RenamedSchemaDescriptor:
    """Create a RenamedSchemaDescriptor; rename/suppress types and fields.

    Any object type, interface type, enum type, or field of the root type/query type has a name. Let
    the name be called type_name. If type_renamings.get(type_name, type_name) is not None, the type
    or field of the root type/query type will be renamed to the returned value. If the value is
    None, it will be suppressed in the renamed schema and queries will not be able to access it.

    Fields may also be renamed or suppressed if they belong to object types that don't implement an
    interface. For an object type named type_name, field_renamings.get(type_name, {}) contains
    the renamings for the fields belonging to that type.

    If a type or field doesn't appear in the renamings arguments, it will be unchanged. Directives
    will never be renamed.

    In addition, some operations have not been implemented yet (see module-level docstring for more
    details).

    Args:
        schema_ast: represents a valid schema that does not contain extensions, input object
                    definitions, mutations, or subscriptions, whose fields of the query type share
                    the same name as the types they query. Not modified by this function
        type_renamings: maps original type name to renamed name or None (for type suppression). A
                        type named "Foo" will be unchanged iff type_renamings does not map "Foo" to
                        anything, i.e. "Foo" not in type_renamings
        field_renamings: maps type names to the field renamings for that type. The renamings map
                         field names belonging to the type to a set of field names for the
                         renamed schema

    Returns:
        RenamedSchemaDescriptor containing the AST of the renamed schema, and the maps of renamed
        type/field names to original names. Only renamed names will be included in the maps.

    Raises:
        - CascadingSuppressionError if type/field suppression would require further suppressions
        - SchemaTransformError if type_renamings suppressed every type. Note that this is a
          superclass of CascadingSuppressionError, InvalidNameError, SchemaStructureError, and
          SchemaRenameNameConflictError, so handling exceptions of type SchemaTransformError will
          also catch all of its subclasses. This will change after the error classes are modified so
          that errors can be fixed programmatically, at which point it will make sense for the user
          to attempt to treat different errors differently
        - NotImplementedError if type_renamings attempts to suppress an enum, an interface, or a
          type implementing an interface
        - InvalidNameError if the schema contains an invalid type name, or if the user attempts
          to rename a type to an invalid name. A name is considered invalid if it does not consist
          of alphanumeric characters and underscores, if it starts with a numeric character, or
          if it starts with double underscores
        - SchemaStructureError if the schema does not have the expected form; in particular, if
          the AST does not represent a valid schema, if any query type field does not have the
          same name as the type that it queries, if the schema contains type extensions or
          input object definitions, or if the schema contains mutations or subscriptions
        - SchemaRenameNameConflictError if there are name conflicts between the renamed types or
          fields
        - NoOpRenamingError if the renamings contain no-op renamings
    """
    # Check input schema satisfies various structural requirements
    check_ast_schema_is_valid(schema_ast)

    schema = build_ast_schema(schema_ast)
    query_type = get_query_type_name(schema)

    _validate_renamings(schema_ast, type_renamings, field_renamings, query_type)

    # Rename types, interfaces, enums, unions and suppress types, unions
    schema_ast, reverse_name_map, reverse_field_name_map = _rename_and_suppress_types_and_fields(
        schema_ast, type_renamings, field_renamings, query_type
    )

    schema_ast = _rename_and_suppress_query_type_fields(schema_ast, type_renamings, query_type)
    return RenamedSchemaDescriptor(
        schema_ast=schema_ast,
        schema=build_ast_schema(schema_ast),
        reverse_name_map=reverse_name_map,
        reverse_field_name_map=reverse_field_name_map,
    )


def _validate_renamings(
    schema_ast: DocumentNode,
    type_renamings: Mapping[str, Optional[str]],
    field_renamings: Mapping[str, Mapping[str, Set[str]]],
    query_type: str,
) -> None:
    """Validate the type_renamings argument before attempting to rename the schema.

    Check for fields with suppressed types or unions whose members were all suppressed. Also,
    confirm type_renamings contains no enums, interfaces, or interface implementation suppressions
    because that hasn't been implemented yet.

    The input AST will not be modified.

    Args:
        schema_ast: represents a valid schema that does not contain extensions, input object
                    definitions, mutations, or subscriptions, whose fields of the query type share
                    the same name as the types they query. Not modified by this function
        type_renamings: maps original type name to renamed name or None (for type suppression). A
                        type named "Foo" will be unchanged iff type_renamings does not map "Foo" to
                        anything, i.e. "Foo" not in type_renamings
        field_renamings: maps type names to the field renamings for that type. The renamings map
                         field names belonging to the type to a set of field names for the
                         renamed schema
        query_type: name of the query type, e.g. 'RootSchemaQuery'

    Raises:
        - CascadingSuppressionError if a type/field suppression would require further suppressions
        - NotImplementedError if type_renamings attempts to suppress an enum, an interface, or a
          type implementing an interface
    """
    _ensure_no_cascading_type_suppressions(schema_ast, type_renamings, field_renamings, query_type)
    _ensure_no_unsupported_suppressions(schema_ast, type_renamings)


def _ensure_no_cascading_type_suppressions(
    schema_ast: DocumentNode,
    type_renamings: Mapping[str, Optional[str]],
    field_renamings: Mapping[str, Mapping[str, Set[str]]],
    query_type: str,
) -> None:
    """Check for situations that would require further suppressions to produce a valid schema."""
    visitor = CascadingSuppressionCheckVisitor(type_renamings, field_renamings, query_type)
    visit(schema_ast, visitor)
    if visitor.fields_to_suppress or visitor.union_types_to_suppress or visitor.types_to_suppress:
        error_message_components = [
            "Renamings would require further suppressions to produce a valid renamed schema."
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
                "A schema containing a field that is of a nonexistent type is invalid. To fix "
                "this, suppress the previously-mentioned fields using the field_renamings argument "
                "of rename_schema."
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
                "A schema containing a union with no members is invalid. To fix this, suppress the "
                "previously-mentioned unions using the type_renamings argument of rename_schema."
            )
        if visitor.types_to_suppress:
            error_message_components.append(
                f"The following types have no non-suppressed fields, which is invalid: "
                f"{sorted(visitor.types_to_suppress)}. To fix this, suppress the "
                f"previously-mentioned types using the type_renamings argument of rename_schema."
            )
        error_message_components.append(
            "Note that adding suppressions may lead to other types, fields, etc. requiring "
            "suppression so you may need to iterate on this before getting a legal schema."
        )
        raise CascadingSuppressionError("\n".join(error_message_components))


def _ensure_no_unsupported_suppressions(
    schema_ast: DocumentNode, type_renamings: Mapping[str, Optional[str]]
) -> None:
    """Confirm type_renamings has no enums, interfaces, or interface implementation suppressions."""
    visitor = SuppressionNotImplementedVisitor(type_renamings)
    visit(schema_ast, visitor)
    if (
        not visitor.unsupported_enum_suppressions
        and not visitor.unsupported_interface_suppressions
        and not visitor.unsupported_interface_implementation_suppressions
    ):
        return
    # Otherwise, attempted to suppress something we shouldn't suppress.
    error_message_components = [
        f"Type renamings {type_renamings} attempted to suppress parts of the schema for which "
        f"suppression is not implemented yet."
    ]
    if visitor.unsupported_enum_suppressions:
        error_message_components.append(
            f"Type renamings mapped these schema enums to None: "
            f"{visitor.unsupported_enum_suppressions}, attempting to suppress them. However, "
            f"type renaming has not implemented enum suppression yet."
        )
    if visitor.unsupported_interface_suppressions:
        error_message_components.append(
            f"Type renamings mapped these schema interfaces to None: "
            f"{visitor.unsupported_interface_suppressions}, attempting to suppress them. However, "
            f"type renaming has not implemented interface suppression yet."
        )
    if visitor.unsupported_interface_implementation_suppressions:
        error_message_components.append(
            f"Type renamings mapped these object types to None: "
            f"{visitor.unsupported_interface_implementation_suppressions}, attempting to suppress "
            f"them. Normally, this would be fine. However, these types each implement at least one "
            f"interface and type renaming has not implemented this particular suppression yet."
        )
    error_message_components.append(
        "To avoid these suppressions, remove the mappings from the type_renamings argument."
    )
    raise NotImplementedError("\n".join(error_message_components))


def _rename_and_suppress_types_and_fields(
    schema_ast: DocumentNode,
    type_renamings: Mapping[str, Optional[str]],
    field_renamings: Mapping[str, Mapping[str, Set[str]]],
    query_type: str,
) -> Tuple[DocumentNode, Dict[str, str], Dict[str, Dict[str, str]]]:
    """Rename and suppress types, enums, interfaces, fields using renamings.

    The query type will not be renamed.

    The input schema AST will not be modified.

    Args:
        schema_ast: schema that we're returning a modified version of
        type_renamings: maps original type name to renamed name or None (for type suppression). A
                        type named "Foo" will be unchanged iff type_renamings does not map "Foo" to
                        anything, i.e. "Foo" not in type_renamings
        field_renamings: maps type names to the field renamings for that type. The renamings map
                         field names belonging to the type to a set of field names for the
                         renamed schema
        query_type: name of the query type, e.g. 'RootSchemaQuery'

    Returns:
        Tuple containing the modified version of the schema AST, the renamed type name to original
        type name map, and the renamed field name to original field name map. The maps contain
        entries for all non-suppressed types/ fields that were changed.

    Raises:
        - InvalidNameError if the user attempts to rename a type or field to an invalid name
        - SchemaRenameNameConflictError if the rename causes name conflicts
        - NoOpRenamingError if renamings contains no-op renamings
    """
    visitor = RenameSchemaTypesVisitor(type_renamings, field_renamings, query_type)
    renamed_schema_ast = visit(schema_ast, visitor)
    if visitor.invalid_type_names or visitor.invalid_field_names:
        explanation = (
            "Applying the renaming would involve names that are not valid, non-reserved "
            "GraphQL names. Valid, non-reserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores."
        )
        invalid_type_names_message = None
        if visitor.invalid_type_names:
            sorted_invalid_type_names = sorted(visitor.invalid_type_names.items())
            invalid_type_names_message = (
                f"The following is a list of tuples that describes what needs to be fixed for type "
                f"renamings. Each tuple is of the form (original_name, invalid_new_name) where "
                f"original_name is the name in the original schema and invalid_new_name is what "
                f"original_name would be renamed to: {sorted_invalid_type_names}"
            )
        invalid_field_names_message = None
        if visitor.invalid_field_names:
            sorted_invalid_field_names = [
                (type_name, sorted(field_renamings.items()))
                for type_name, field_renamings in sorted(visitor.invalid_field_names.items())
            ]
            invalid_field_names_message = (
                f"The following is a list of tuples that describes what needs to be fixed for "
                f"field renamings. Each tuple is of the form (type_name, field_renamings) "
                f"where type_name is the name of the type in the original schema and "
                f"field_renamings is a list of tuples mapping the original field name to the "
                f"invalid GraphQL name it would be renamed to: {sorted_invalid_field_names}"
            )
        error_message_components = [
            explanation,
            invalid_type_names_message,
            invalid_field_names_message,
        ]
        raise InvalidNameError("\n".join([i for i in error_message_components if i is not None]))
    if (
        visitor.type_name_conflicts
        or visitor.type_renamed_to_builtin_scalar_conflicts
        or visitor.field_name_conflicts
    ):
        raise SchemaRenameNameConflictError(
            visitor.type_name_conflicts,
            visitor.type_renamed_to_builtin_scalar_conflicts,
            visitor.field_name_conflicts,
        )
    if visitor.types_involving_interfaces_with_field_renamings:
        raise NotImplementedError(
            f"Field renaming for interfaces or types implementing interfaces is not supported, but "
            f"they exist for the following types and should be removed: "
            f"{visitor.types_involving_interfaces_with_field_renamings}"
        )
    if visitor.illegal_builtin_scalar_renamings:
        raise NotImplementedError(
            f"Type_renamings contained renamings for the following built-in scalar types: "
            f"{visitor.illegal_builtin_scalar_renamings}. To fix this, remove them from "
            f"type_renamings."
        )
    for type_name in visitor.suppressed_type_names:
        if type_name not in type_renamings:
            raise AssertionError(
                f"suppressed_type_names should be a subset of the set of keys in "
                f"type_renamings, but found {type_name} in suppressed_type_names that is not a "
                f"key in type_renamings. This is a bug."
            )
    renamed_types = {
        visitor.reverse_name_map[type_name]
        for type_name in visitor.reverse_name_map
        if type_name != visitor.reverse_name_map[type_name]
    }
    no_op_type_renames = set(type_renamings) - renamed_types - set(visitor.suppressed_type_names)
    # nonexistent_types_with_field_renamings is the set of all object type names that aren't in the
    # original schema but appeared in field_renamings anyways.
    nonexistent_types_with_field_renamings = (
        set(field_renamings) - visitor.types_with_field_renamings_processed
    )
    if (
        no_op_type_renames
        or visitor.no_op_field_renamings
        or nonexistent_types_with_field_renamings
    ):
        raise NoOpRenamingError(
            no_op_type_renames,
            visitor.no_op_field_renamings,
            nonexistent_types_with_field_renamings,
        )

    reverse_name_map_changed_names_only = {
        renamed_name: original_name
        for renamed_name, original_name in six.iteritems(visitor.reverse_name_map)
        if renamed_name != original_name
    }
    reverse_field_name_map_changed_names_only = {}
    for type_name, reverse_field_name_mapping in visitor.reverse_field_name_map.items():
        current_type_reverse_field_name_map_changed_names_only = {
            renamed_field_name: original_field_name
            for renamed_field_name, original_field_name in reverse_field_name_mapping.items()
            if renamed_field_name != original_field_name
        }
        if current_type_reverse_field_name_map_changed_names_only:
            reverse_field_name_map_changed_names_only[
                type_name
            ] = current_type_reverse_field_name_map_changed_names_only

    return (
        renamed_schema_ast,
        reverse_name_map_changed_names_only,
        reverse_field_name_map_changed_names_only,
    )


def _rename_and_suppress_query_type_fields(
    schema_ast: DocumentNode, type_renamings: Mapping[str, Optional[str]], query_type: str
) -> DocumentNode:
    """Rename or suppress all fields of the query type.

    The input schema AST will not be modified.

    Args:
        schema_ast: schema that we're returning a modified version of
        type_renamings: maps original type name to renamed name or None (for type suppression). A
                        type named "Foo" will be unchanged iff type_renamings does not map "Foo" to
                        anything, i.e. "Foo" not in type_renamings
        query_type: name of the query type, e.g. 'RootSchemaQuery'

    Returns:
        modified version of the input schema AST

    Raises:
        - SchemaTransformError if type_renamings suppressed every type
    """
    visitor = RenameQueryTypeFieldsVisitor(type_renamings, query_type)
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
            "ScalarTypeDefinitionNode",
            "UnionTypeDefinitionNode",
        }
    )

    # Collects naming conflict errors involving types that are not built-in scalar types. If
    # type_renamings would result in multiple types being named "Foo", type_name_conflicts will map
    # "Foo" to a set containing the name of each such type
    type_name_conflicts: Dict[str, Set[str]]

    # Collects naming conflict errors involving built-in scalar types. If
    # type_renamings["Foo"] == "String", type_renamed_to_builtin_scalar_conflicts will map
    # "Foo" to "String"
    type_renamed_to_builtin_scalar_conflicts: Dict[str, str]

    # Collects naming errors that arise from attempting to rename a builtin scalar. If
    # type_renamings["String"] == "Foo" schema, illegal_builtin_scalar_renamings will contain
    # "String"
    illegal_builtin_scalar_renamings: Set[str]

    # reverse_name_map maps renamed type name to original type name, containing all non-suppressed
    # types, including those that were unchanged. Must contain unchanged names to prevent type
    # renaming conflicts and raise SchemaRenameNameConflictError when they arise
    reverse_name_map: Dict[str, str]

    # Collects invalid type names in type_renamings. If type_renamings["Foo"] is a string that is
    # not a valid, non-reserved GraphQL type name (valid, non-reserved names consist only of
    # alphanumeric characters and underscores, do not start with a number, and do not start with two
    # underscores), invalid_type_names will map "Foo" to the invalid type name.
    invalid_type_names: Dict[str, str]

    # Collects the type names for types that get suppressed. If type_renamings["Foo"] == None,
    # suppressed_type_names will contain "Foo".
    suppressed_type_names: Set[str]

    # reverse_field_name_map maps type name to a dict, which in turn maps the name of a field in the
    # renamed schema to the name of the field in the original schema, if the field has different
    # names in the original schema and the new schema. If field_renamings would rename a field named
    # "foo" (in a type named "Baz") to "bar", then reverse_field_name_map["Baz"] will map "bar" to
    # "foo".
    reverse_field_name_map: Dict[str, Dict[str, str]]

    # Collects no-op renamings for fields, mapping the type name that contains the field to the set
    # of field names for which field_renamings contained no-op renamings. For a type named "Bar", if
    # field_renaming
    #    - renames a field named "foo" to "foo", or
    #    - attempts to rename a field named "foo" when such a field does not exist
    # no_op_field_renamings will map "Bar" to a set containing "foo".
    no_op_field_renamings: Dict[str, Set[str]]

    # Collects type names for each object type that has field renamings that have been applied.
    # After every renaming is done, this is used to ensure that field_renamings contains no unused
    # field renamings for a particular type.
    types_with_field_renamings_processed: Set[str]

    # Collects invalid field names in field_renamings. If field_renamings would rename a field named
    # "foo" (in a type named "Bar") to a string that is not a valid, non-reserved GraphQL type name
    # (valid, non-reserved names consist only of alphanumeric characters and underscores, do not
    # start with a number, and do not start with two underscores), invalid_field_names will map
    # "Bar" to a dict that maps "foo" to the invalid field name.
    invalid_field_names: Dict[str, Dict[str, str]]

    # Collects naming conflict errors involving fields. If field_renamings would rename multiple
    # fields (in a type named "Bar" in the original schema) to "foo", field_name_conflicts will map
    # "Bar" to a dict that maps "foo" to a set containing the names of the fields in the original
    # schema that would be renamed to "foo".
    field_name_conflicts: Dict[str, Dict[str, Set[str]]]

    # Collects names of types who have entries in field_renamings if the type is an interface
    # or if the type is an object type implementing an interface because field renamings involving
    # interfaces haven't been implemented yet. If field renamings has field renamings for such a
    # type named "Foo", types_involving_interfaces_with_field_renamings will contain "Foo".
    types_involving_interfaces_with_field_renamings: Set[str]

    def __init__(
        self,
        type_renamings: Mapping[str, Optional[str]],
        field_renamings: Mapping[str, Mapping[str, Set[str]]],
        query_type: str,
    ) -> None:
        """Create a visitor for renaming types in a schema AST.

        Args:
            type_renamings: maps original type name to renamed name or None (for type suppression).
                            A type named "Foo" will be unchanged iff type_renamings does not map
                            "Foo" to anything, i.e. "Foo" not in type_renamings
            field_renamings: maps type names to the field renamings for that type. The renamings map
                             field names belonging to the type to a set of field names for the
                             renamed schema
            query_type: name of the query type (e.g. RootSchemaQuery), which will not be renamed
        """
        self.type_renamings = type_renamings
        self.reverse_name_map = {}
        self.type_name_conflicts = {}
        self.type_renamed_to_builtin_scalar_conflicts = {}
        self.illegal_builtin_scalar_renamings = {
            scalar_name
            for scalar_name in builtin_scalar_type_names
            if scalar_name in type_renamings
        }
        self.invalid_type_names = {}
        self.query_type = query_type
        self.suppressed_type_names = set()
        self.field_renamings = field_renamings
        self.reverse_field_name_map = {}
        self.no_op_field_renamings = {}
        self.types_with_field_renamings_processed = set()
        self.invalid_field_names = {}
        self.field_name_conflicts = {}
        self.types_involving_interfaces_with_field_renamings = set()

    def _rename_or_suppress_or_ignore_name_and_add_to_record(
        self, node: RenameTypesT
    ) -> Union[RenameTypesT, VisitorAction]:
        """Change node based on renamings and update reverse mapping data structures.

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
        """
        type_name = node.name.value

        if type_name == self.query_type or type_name in builtin_scalar_type_names:
            return IDLE

        desired_type_name = self.type_renamings.get(type_name, type_name)  # Default use original

        if desired_type_name is None:
            # Suppress the type
            self.suppressed_type_names.add(type_name)
            return REMOVE
        if not is_valid_nonreserved_name(desired_type_name):
            self.invalid_type_names[type_name] = desired_type_name

        # Renaming conflict arises when two types with different names in the original schema have
        # the same name in the new schema.
        if self.reverse_name_map.get(desired_type_name, type_name) != type_name:
            conflictingly_renamed_type_name = self.reverse_name_map[desired_type_name]

            # Collect all types in the original schema that would be named desired_type_name in the
            # new schema
            if desired_type_name not in self.type_name_conflicts:
                self.type_name_conflicts[desired_type_name] = {conflictingly_renamed_type_name}
            self.type_name_conflicts[desired_type_name].add(type_name)

        if desired_type_name in builtin_scalar_type_names:
            self.type_renamed_to_builtin_scalar_conflicts[type_name] = desired_type_name

        # Any potential type suppressions will have taken place by this point, so this current node
        # will appear in the renamed schema, so it's safe to apply field renamings to this type.
        fields_renamed_node = node  # If no field renaming happens, fields_renamed_node will just be
        # the current node, unchanged.
        if isinstance(fields_renamed_node, ObjectTypeDefinitionNode):
            # mypy is unable to detect that fields_renamed_node is an ObjectTypeDefinitionNode if
            # the code enters this block, so disabling it for this line.
            # https://github.com/python/mypy/issues/2885#issuecomment-287928126
            fields_renamed_node = self._rename_fields(fields_renamed_node)  # type: ignore
        elif (
            isinstance(fields_renamed_node, InterfaceTypeDefinitionNode)
            and fields_renamed_node.name.value in self.field_renamings
        ):
            self.types_involving_interfaces_with_field_renamings.add(fields_renamed_node.name.value)
        self.reverse_name_map[desired_type_name] = type_name
        if desired_type_name == type_name:
            return fields_renamed_node
        else:  # Make copy of node with the changed name, return the copy
            node_with_new_name = get_copy_of_node_with_new_name(
                fields_renamed_node, desired_type_name
            )
            return node_with_new_name

    def _rename_fields(self, node: ObjectTypeDefinitionNode) -> ObjectTypeDefinitionNode:
        """Rename node's fields, if applicable and return new node with updated fields."""
        type_name = node.name.value
        if type_name not in self.field_renamings:
            return node
        if node.interfaces:
            self.types_involving_interfaces_with_field_renamings.add(type_name)
        current_type_field_renamings = self.field_renamings[type_name]
        self.types_with_field_renamings_processed.add(type_name)
        # Need to create a set of field nodes that the type will have after the field renamings,
        # instead of just modifying them in place. This is to support 1-many renaming.
        new_field_nodes: Set[FieldDefinitionNode] = set()
        for field_node in node.fields:
            original_field_name = field_node.name.value
            if original_field_name in current_type_field_renamings and current_type_field_renamings[
                original_field_name
            ] == {original_field_name}:
                # Check for no-op 1-1 renamings when the renamings would rename a field to itself.
                self.no_op_field_renamings.setdefault(type_name, set()).add(original_field_name)
            new_field_names = current_type_field_renamings.get(
                original_field_name, {original_field_name}
            )
            for new_field_name in new_field_names:
                # Validate the new field name before adding it to the schema.
                if new_field_name in self.reverse_field_name_map.setdefault(type_name, {}):
                    if new_field_name not in self.field_name_conflicts.setdefault(type_name, {}):
                        conflictingly_renamed_field_name = self.reverse_field_name_map[type_name][
                            new_field_name
                        ]
                        self.field_name_conflicts[type_name][new_field_name] = {
                            conflictingly_renamed_field_name
                        }
                    self.field_name_conflicts[type_name][new_field_name].add(original_field_name)
                if not is_valid_nonreserved_name(new_field_name):
                    self.invalid_field_names.setdefault(type_name, {})[
                        original_field_name
                    ] = new_field_name
                self.reverse_field_name_map[type_name][new_field_name] = original_field_name
            new_field_nodes.update(
                get_copy_of_node_with_new_name(field_node, new_field_name)
                for new_field_name in new_field_names
            )
        # Check that, having applied field renamings for every single field in node.fields, that
        # there are no leftover field_renamings that would be illegal noops.
        unused_field_renamings = set(current_type_field_renamings) - {
            field.name.value for field in node.fields
        }
        if unused_field_renamings:
            # Need this condition because if all the renamings are used, calling update() will
            # materialize an empty set, making it seem like there are no-op field renamings even
            # when there aren't.
            self.no_op_field_renamings.setdefault(type_name, set()).update(unused_field_renamings)
        new_type_node = copy(node)
        new_type_node.fields = FrozenList(new_field_nodes)
        return new_type_node

    def enter(
        self,
        node: Node,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> VisitorReturnType:
        """Upon entering a node, operate depending on node type."""
        node_type = type(node).__name__
        if node_type in self.noop_types:
            # Do nothing, continue traversal
            return IDLE
        elif node_type in self.rename_types:
            # Process the node by either renaming, suppressing, or not doing anything with it
            # (depending on what type_renamings specifies)
            return self._rename_or_suppress_or_ignore_name_and_add_to_record(
                cast(RenameTypes, node)
            )
        else:
            # All Node types should've been taken care of, this line should never be reached
            raise AssertionError('Unreachable code reached. Missed type: "{}"'.format(node_type))


class RenameQueryTypeFieldsVisitor(Visitor):
    def __init__(self, type_renamings: Mapping[str, Optional[str]], query_type: str) -> None:
        """Create a visitor for renaming or suppressing fields of the query type in a schema AST.

        Args:
            type_renamings: maps original type name to renamed name or None (for type suppression).
                            A type named "Foo" will be unchanged iff type_renamings does not map
                            "Foo" to anything, i.e. "Foo" not in type_renamings
            query_type: name of the query type (e.g. RootSchemaQuery)

        Raises:
            - SchemaTransformError if every field in the query type was suppressed
        """
        # Note that as field names and type names have been confirmed to match up, any renamed
        # query type field already has a corresponding renamed type.
        self.in_query_type = False
        self.type_renamings = type_renamings
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
                f"Type renamings {self.type_renamings} suppressed every type in the schema so it "
                f"will be impossible to query for anything. To fix this, check why the "
                f"type_renamings argument of rename_schema mapped every type to None."
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
        """If inside query type, rename or remove field as specified by type_renamings."""
        if self.in_query_type:
            field_name = node.name.value
            new_field_name = self.type_renamings.get(field_name, field_name)  # Default use original
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
    The types_to_suppress attribute records types for which all fields were suppressed.

    After calling visit() on the schema using this visitor, if any of these attributes are non-empty
    then there are further suppressions required to produce a legal schema so the code should then
    raise a CascadingSuppressionError.

    """

    # For a type named T, and its field named F whose type has name V, this dict would be
    # {"T": {"F": "V"}}
    fields_to_suppress: Dict[str, Dict[str, str]]
    union_types_to_suppress: List[UnionTypeDefinitionNode]
    types_to_suppress: Set[str]

    def __init__(
        self,
        type_renamings: Mapping[str, Optional[str]],
        field_renamings: Mapping[str, Mapping[str, Set[str]]],
        query_type: str,
    ) -> None:
        """Create a visitor to check that suppression does not cause an illegal state.

        Args:
            type_renamings: maps original type name to renamed name or None (for type suppression).
                            A type named "Foo" will be unchanged iff type_renamings does not map
                            "Foo" to anything, i.e. "Foo" not in type_renamings
            field_renamings: maps type names to the field renamings for that type. The renamings map
                             field names belonging to the type to a set of field names for the
                             renamed schema
            query_type: name of the query type (e.g. RootSchemaQuery)
        """
        self.type_renamings = type_renamings
        self.field_renamings = field_renamings
        self.query_type = query_type
        self.current_type: Optional[str] = None
        self.fields_to_suppress = {}
        self.union_types_to_suppress = []
        self.types_to_suppress = set()

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
        if self.current_type not in self.field_renamings:
            # No field renamings for current type, so it's impossible for all its fields to have
            # been suppressed.
            return
        current_type_field_renamings = self.field_renamings[self.current_type]
        for field in node.fields:
            field_name = field.name.value
            if (
                field_name not in current_type_field_renamings
                or current_type_field_renamings[field_name]
            ):
                # Do nothing if there's at least one field for the current type that hasn't been
                # suppressed, either because field renamings didn't contain an entry for field_name
                # or if it didn't suppress the field
                return
        self.types_to_suppress.add(self.current_type)

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
        """Check that no type Bar contains a field of type Foo, where Foo is suppressed."""
        if self.current_type == self.query_type:
            return IDLE
        # At a field of a type that is not the query type
        field_name = node.name.value
        field_type = get_ast_with_non_null_and_list_stripped(node.type).name.value
        if self.type_renamings.get(field_type, field_type):
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
        if self.field_renamings.get(self.current_type, {}).get(field_name, {field_name}) == set():
            # Field was also suppressed so this should not raise errors.
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
            if self.type_renamings.get(union_member_type, union_member_type):
                # Then at least one member of the union is not suppressed, so there is no cascading
                # suppression error concern.
                return IDLE
        if self.type_renamings.get(union_name, union_name) is None:
            # If the union is also suppressed, then nothing needs to happen here
            return IDLE
        self.union_types_to_suppress.append(node)

        return IDLE


class SuppressionNotImplementedVisitor(Visitor):
    """Traverse the schema to check for suppressions that are not yet implemented.

    Each attribute that mentions an unsupported suppression records the types that type_renamings
    attempts to suppress.

    After calling visit() on the schema using this visitor, if any of these attributes are non-empty
    then some suppressions specified by type_renamings are unsupported, so the code should then
    raise a NotImplementedError.

    """

    unsupported_enum_suppressions: Set[str]
    unsupported_interface_suppressions: Set[str]
    unsupported_interface_implementation_suppressions: Set[str]

    def __init__(self, type_renamings: Mapping[str, Optional[str]]) -> None:
        """Confirm type_renamings doesn't try to suppress enum/interface/interface implementation.

        Args:
            type_renamings: maps original type name to renamed name or None (for type suppression).
                            A type named "Foo" will be unchanged iff type_renamings does not map
                            "Foo" to anything, i.e. "Foo" not in type_renamings
        """
        self.type_renamings = type_renamings
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
        """If type_renamings suppresses enums, record it for error message."""
        enum_name = node.name.value
        if self.type_renamings.get(enum_name, enum_name) is None:
            self.unsupported_enum_suppressions.add(enum_name)

    def enter_interface_type_definition(
        self,
        node: InterfaceTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If type_renamings suppresses interfaces, record it for error message."""
        interface_name = node.name.value
        if self.type_renamings.get(interface_name, interface_name) is None:
            self.unsupported_interface_suppressions.add(interface_name)

    def enter_object_type_definition(
        self,
        node: ObjectTypeDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> None:
        """If type_renamings suppresses interface implementations, record it for error message."""
        if not node.interfaces:
            return
        object_name = node.name.value
        if self.type_renamings.get(object_name, object_name) is None:
            # Suppressing interface implementations isn't supported yet.
            self.unsupported_interface_implementation_suppressions.add(object_name)
