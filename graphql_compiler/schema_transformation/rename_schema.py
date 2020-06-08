# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from graphql import (
    DocumentNode,
    FieldDefinitionNode,
    Node,
    ObjectTypeDefinitionNode,
    UnionTypeDefinitionNode,
    build_ast_schema,
)
from graphql.language.visitor import REMOVE, Visitor, visit
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

# AST visitor functions can return a number of different things, such as returning a Node (to update
# that node) or returning REMOVE (to remove the node). In the current GraphQL-core version
# (>=3,<3.1), REMOVE is set to the singleton object Ellipsis. However, returning Ellipsis prevents
# us from type-hinting functions with anything more specific than Any. For more information, see:
# https://github.com/kensho-technologies/graphql-compiler/pull/834#discussion_r434622400
# and the issue opened with GraphQL-core here:
# https://github.com/graphql-python/graphql-core/issues/96
VisitorReturnType = Union[Node, Any]


def rename_schema(
    ast: DocumentNode, renamings: Dict[str, Optional[str]]
) -> RenamedSchemaDescriptor:
    """Create a RenamedSchemaDescriptor; types and query type fields are renamed using renamings.

    Any type, interface, enum, or fields of the root type/query type whose name
    appears in renamings will be renamed to the corresponding value if the value is not None. If the
    value is None, it will be suppressed in the renamed schema and queries will not be able to
    access it.

    Any such names that do not appear in renamings will be unchanged.

    Scalars, directives, enum values, and fields not belonging to the root/query type will never be
    renamed.

    Args:
        ast: Document, representing a valid schema that does not contain extensions, input
             object definitions, mutations, or subscriptions, whose fields of the query type share
             the same name as the types they query. Not modified by this function
        renamings: Dict[str, Optional[str]], mapping original type/root type field names to renamed
                   type/root type field names or None.
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
    check_ast_schema_is_valid(ast)

    schema = build_ast_schema(ast)
    query_type = get_query_type_name(schema)
    scalars = get_scalar_names(schema)

    # Rename types, interfaces, enums
    ast, reverse_name_map = _rename_types(ast, renamings, query_type, scalars)
    reverse_name_map_changed_names_only = {
        renamed_name: original_name
        for renamed_name, original_name in six.iteritems(reverse_name_map)
        if renamed_name != original_name
    }

    # Rename query type fields
    ast = _rename_query_type_fields(ast, renamings, query_type)

    # Check for fields or unions that depend on types that were suppressed
    ast = _check_for_cascading_type_suppression(ast, renamings, query_type)
    return RenamedSchemaDescriptor(
        schema_ast=ast,
        schema=build_ast_schema(ast),
        reverse_name_map=reverse_name_map_changed_names_only,
    )


def _rename_types(
    ast: DocumentNode, renamings: Dict[str, Optional[str]], query_type: str, scalars: Set[str]
) -> Tuple[DocumentNode, Dict[str, str]]:
    """Rename types, enums, interfaces or suppress types using renamings.

    The query type will not be renamed. Scalar types, field names, enum values will not be renamed.

    The input AST will not be modified.

    Args:
        ast: Document, the schema that we're returning a modified version of
        renamings: Dict[str, Optional[str]], mapping original type/interface/enum name to renamed
                   name. If a name does not appear in the dict, it will be unchanged
        query_type: str, name of the query type, e.g. 'RootSchemaQuery'
        scalars: Set[str], the set of all scalars used in the schema, including user defined
                 scalars and and used builtin scalars, excluding unused builtins

    Returns:
        Tuple[Document, Dict[str, str]], containing the modified version of the AST, and
        the renamed type name to original type name map. Map contains all non-suppressed types,
        including those that were not renamed.

    Raises:
        - InvalidTypeNameError if the schema contains an invalid type name, or if the user attempts
          to rename a type to an invalid name
        - SchemaNameConflictError if the rename causes name conflicts
    """
    visitor = RenameSchemaTypesVisitor(renamings, query_type, scalars)
    renamed_ast = visit(ast, visitor)

    return renamed_ast, visitor.reverse_name_map


def _rename_query_type_fields(
    ast: DocumentNode, renamings: Dict[str, Optional[str]], query_type: str
) -> DocumentNode:
    """Rename or suppress fields of the query type.

    The input AST will not be modified.

    Args:
        ast: DocumentNode, the schema that we're returning a modified version of
        renamings: Dict[str, Optional[str]], mapping original field name to renamed name. If a name
                   does not appear in the dict, it will be unchanged
        query_type: str, name of the query type, e.g. 'RootSchemaQuery'

    Returns:
        DocumentNode, representing the modified version of the input schema AST

    Raises:
        - InvalidTypeNameError if renamings suppressed every type
    """
    visitor = RenameQueryTypeFieldsVisitor(renamings, query_type)
    renamed_ast = visit(ast, visitor)
    return renamed_ast


def _check_for_cascading_type_suppression(
    ast: DocumentNode, renamings: Dict[str, Optional[str]], query_type: str
) -> DocumentNode:
    """Check for fields with suppressed types or unions whose members were all suppressed.

    The input AST will not be modified.

    Args:
        ast: DocumentNode, the schema that we're returning a modified version of
        renamings: Dict[str, Optional[str]], mapping original field name to renamed name. If a name
                   does not appear in the dict, it will be unchanged
        query_type: str, name of the query type, e.g. 'RootSchemaQuery'

    Returns:
        DocumentNode, representing the modified version of the input schema AST

    Raises:
        - CascadingSuppressionError if a type suppression would require further suppressions
    """
    visitor = CascadingSuppressionCheckVisitor(renamings, query_type)
    renamed_ast = visit(ast, visitor)
    return renamed_ast


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
        self, renamings: Dict[str, Optional[str]], query_type: str, scalar_types: Set[str]
    ) -> None:
        """Create a visitor for renaming types in a schema AST.

        Args:
            renamings: Dict[str, Optional[str]], mapping from original type name to renamed type
                       name or None (for type suppression). Any name not in the dict will be
                       unchanged
            query_type: str, name of the query type (e.g. RootSchemaQuery), which will not
                        be renamed
            scalar_types: Set[str], set of names of all scalars used in the schema, including
                          all user defined scalars and any builtin scalars that were used
        """
        self.renamings = renamings
        self.reverse_name_map: Dict[str, str] = {}  # From renamed type name to original type name
        # reverse_name_map contains all non-suppressed types, including those that were unchanged
        self.query_type = query_type
        self.scalar_types = frozenset(scalar_types)
        self.builtin_types = frozenset({"String", "Int", "Float", "Boolean", "ID"})

    def _rename_name_and_add_to_record(self, node: Node) -> VisitorReturnType:
        """Change the name of the input node if necessary, add the name pair to reverse_name_map.

        Don't rename if the type is the query type, a scalar type, or a builtin type.

        The input node will not be modified. reverse_name_map may be modified.

        Args:
            node: EnumTypeDefinitionNode, InterfaceTypeDefinitionNode, NamedTypeNode,
                  ObjectTypeDefinitionNode, or UnionTypeDefinitionNode. An object representing an
                  AST component, containing a .name attribute corresponding to an AST node of type
                  NameNode.

        Returns:
            Node object or REMOVE. REMOVE is a special return value defined by the GraphQL library.
            A visitor function returns REMOVE to delete the node it's currently at. This function
            returns REMOVE to suppress types. If the current node is not to be suppressed, it
            returns a Node object identical to the input node, except with possibly a new name. If
            the name was not changed, the returned object is the exact same object as the input

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
            return None
        elif node_type in self.rename_types:
            # Rename node, put name pair into record
            renamed_node = self._rename_name_and_add_to_record(node)
            if renamed_node is node:  # Name unchanged, continue traversal
                return None
            else:
                # Name changed or suppressed, return new node, `visit` will make shallow copies
                # along path
                return renamed_node
        else:
            # All Node types should've been taken care of, this line should never be reached
            raise AssertionError('Unreachable code reached. Missed type: "{}"'.format(node_type))


class RenameQueryTypeFieldsVisitor(Visitor):
    def __init__(self, renamings: Dict[str, Optional[str]], query_type: str) -> None:
        """Create a visitor for renaming fields of the query type in a schema AST.

        Args:
            renamings: Dict[str, Optional[str]], from original field name to renamed field name or
                       None (for type suppression). Any name not in the dict will be unchanged
            query_type: str, name of the query type (e.g. RootSchemaQuery)
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
                return None
            if new_field_name is None:
                # Suppress the type
                return REMOVE
            else:  # Make copy of node with the changed name, return the copy
                field_node_with_new_name = get_copy_of_node_with_new_name(node, new_field_name)
                return field_node_with_new_name
        return None


class CascadingSuppressionCheckVisitor(Visitor):
    def __init__(self, renamings: Dict[str, Optional[str]], query_type: str) -> None:
        """Create a visitor to check that suppression does not cause an illegal state.

        Args:
            renamings: Dict[str, Optional[str]], from original field name to renamed field name or
                       None (for type suppression). Any name not in the dict will be unchanged
            query_type: str, name of the query type (e.g. RootSchemaQuery)
        """
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
    ) -> None:
        """If not at query type, check that no field depends on a type that was suppressed."""
        if self.in_query_type:
            return None
        # At a field of a type that is not the query type
        field_name = node.name.value
        node_type = get_ast_with_non_null_and_list_stripped(node.type)
        if node_type == REMOVE:
            # Then this field depends on a type that was suppressed, which is illegal
            if not ancestors:
                raise AssertionError(
                    f"Expected ancestors to be non-empty list when entering field definition but"
                    f"ancestors was {ancestors} at node {node}"
                )
            # We use the grandparent node (ObjectTypeDefinitionNode) instead of the parent because
            # the parent of a FieldDefinitionNode is simply a list of FieldDefinitionNodes, which
            # doesn't contain the name of the type containing this node (which we need for the error
            # message).
            node_grandparent = ancestors[-1]
            if not isinstance(node_grandparent, ObjectTypeDefinitionNode):
                raise TypeError(
                    f"Expected field node {node}'s grandparent node to be of type "
                    f"ObjectTypeDefinitionNode but grandparent node was of type "
                    f"{type(node_grandparent).__name__} instead."
                )
            type_name = node_grandparent.name.value
            raise CascadingSuppressionError(
                f"Type renamings {self.renamings} attempted to suppress a type, but type "
                f"{type_name}'s field {field_name} still depends on that type. Suppressing "
                f"individual fields hasn't been implemented yet, but when it is, you can fix "
                f"this error by suppressing the field as well. Note that adding suppressions "
                f"may lead to other types, fields, unions, etc. requiring suppression so you "
                f"may need to iterate on this before getting a legal schema."
            )
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
        if not node.types:
            raise CascadingSuppressionError(
                f"Type renamings {self.renamings} suppressed all types belonging to the union "
                f"{union_name}. To fix this, you can suppress the union as well by adding "
                f"`{union_name}: None` to the `renamings` argument of `rename_schema`. Note that "
                f"adding suppressions may lead to other types, fields, unions, etc. requiring "
                f"suppression so you may need to iterate on this before getting a legal schema."
            )
