# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from typing import AbstractSet, Any, Dict, List, Mapping, Optional, Tuple, TypeVar, Union, cast

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
from graphql.language.visitor import Visitor, visit
import six

from .utils import (
    SchemaNameConflictError,
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


def rename_schema(
    schema_ast: DocumentNode, renamings: Mapping[str, str]
) -> RenamedSchemaDescriptor:
    """Create a RenamedSchemaDescriptor; types and query type fields are renamed using renamings.

    Any type, interface, enum, or fields of the root type/query type whose name
    appears in renamings will be renamed to the corresponding value. Any such names that do not
    appear in renamings will be unchanged. Scalars, directives, enum values, and fields not
    belonging to the root/query type will never be renamed.

    Args:
        schema_ast: represents a valid schema that does not contain extensions, input object
                    definitions, mutations, or subscriptions, whose fields of the query type share
                    the same name as the types they query. Not modified by this function
        renamings: maps original type/field names to renamed type/field names. Type or query type
                   field names that do not appear in the dict will be unchanged. Any dict-like
                   object that implements get(key, [default]) may also be used

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
    renamings: Mapping[str, str],
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
        original type name map. Map contains all types, including those that were not renamed.

    Raises:
        - InvalidTypeNameError if the schema contains an invalid type name, or if the user attempts
          to rename a type to an invalid name
        - SchemaNameConflictError if the rename causes name conflicts
    """
    visitor = RenameSchemaTypesVisitor(renamings, query_type, scalars)
    renamed_schema_ast = visit(schema_ast, visitor)
    return renamed_schema_ast, visitor.reverse_name_map


def _rename_query_type_fields(
    schema_ast: DocumentNode, renamings: Mapping[str, str], query_type: str
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
        self, renamings: Mapping[str, str], query_type: str, scalar_types: AbstractSet[str]
    ) -> None:
        """Create a visitor for renaming types in a schema AST.

        Args:
            renamings: maps original type name to renamed name. Any name not in the dict will be
                       unchanged
            query_type: name of the query type (e.g. RootSchemaQuery), which will not be renamed
            scalar_types: set of all scalars used in the schema, including all user defined scalars
                          and any builtin scalars that were used
        """
        self.renamings = renamings
        self.reverse_name_map: Dict[str, str] = {}  # from renamed type name to original type name
        # reverse_name_map contains all types, including those that were unchanged
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
            Node object, identical to the input node, except with possibly a new name. If the
            name was not changed, the returned object is the exact same object as the input

        Raises:
            - InvalidTypeNameError if either the node's current name or renamed name is invalid
            - SchemaNameConflictError if the newly renamed node causes name conflicts with
              existing types, scalars, or builtin types
        """
        name_string = node.name.value

        if name_string == self.query_type or name_string in self.scalar_types:
            return node

        new_name_string = self.renamings.get(name_string, name_string)  # Default use original
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
    ) -> Optional[Node]:
        """Upon entering a node, operate depending on node type."""
        node_type = type(node).__name__
        if node_type in self.noop_types:
            # Do nothing, continue traversal
            return None
        elif node_type in self.rename_types:
            # Rename node, put name pair into record
            renamed_node = self._rename_name_and_add_to_record(cast(RenameTypes, node))
            if renamed_node is node:  # Name unchanged, continue traversal
                return None
            else:  # Name changed, return new node, `visit` will make shallow copies along path
                return renamed_node
        else:
            # All Node types should've been taken care of, this line should never be reached
            raise AssertionError('Unreachable code reached. Missed type: "{}"'.format(node_type))


class RenameQueryTypeFieldsVisitor(Visitor):
    def __init__(self, renamings: Mapping[str, str], query_type: str) -> None:
        """Create a visitor for renaming fields of the query type in a schema AST.

        Args:
            renamings: maps original field name to renamed field name. Any name not in the dict will
                       be unchanged
            query_type: name of the query type (e.g. RootSchemaQuery)
        """
        # Note that as field names and type names have been confirmed to match up, any renamed
        # field already has a corresponding renamed type. If no errors, due to either invalid
        # names or name conflicts, were raised when renaming type, no errors will occur when
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
        if node.name.value == self.query_type:
            self.in_query_type = False

    def enter_field_definition(
        self,
        node: FieldDefinitionNode,
        key: Any,
        parent: Any,
        path: List[Any],
        ancestors: List[Any],
    ) -> Optional[Node]:
        """If inside the query type, rename field and add the name pair to reverse_field_map."""
        if self.in_query_type:
            field_name = node.name.value
            new_field_name = self.renamings.get(field_name, field_name)  # Default use original
            if new_field_name == field_name:
                return None
            else:  # Make copy of node with the changed name, return the copy
                field_node_with_new_name = get_copy_of_node_with_new_name(node, new_field_name)
                return field_node_with_new_name

        return None
