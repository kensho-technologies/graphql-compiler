# Copyright 2019-present Kensho Technologies, LLC.
from typing import Any, Dict, List, Union

from graphql import GraphQLSchema
from graphql.language.ast import (
    DocumentNode,
    FieldNode,
    InterfaceTypeDefinitionNode,
    NamedTypeNode,
    ObjectTypeDefinitionNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
)
from graphql.language.visitor import Visitor, VisitorAction, visit
from graphql.validation import validate

from ..ast_manipulation import get_ast_with_non_null_and_list_stripped
from ..exceptions import GraphQLValidationError
from .rename_schema import RenamedSchemaDescriptor
from .utils import RenameQueryNodeTypesT, get_copy_of_node_with_new_name


def rename_query(
    ast: DocumentNode, renamed_schema_descriptor: RenamedSchemaDescriptor
) -> DocumentNode:
    """Translate names of types/fields using reverse_name_map of the input RenamedSchemaDescriptor.

    The direction in which types/fields are renamed is opposite of the process that
    produced the renamed schema descriptor. If a type/field X was renamed to Y in the schema, then
    any occurrences of Y in the input query AST will be renamed to X.

    All type names (including ones in type coercions) and field names will be renamed.

    Args:
        ast: represents a query
        renamed_schema_descriptor: namedtuple including the attribute reverse_name_map, which maps
                                   the new, renamed names of types to their original names, and
                                   reverse_field_name_map which has a similar role for fields. This
                                   function will revert these renamed types/fields in the query AST
                                   back to their original names

    Returns:
        New AST representing the renamed query

    Raises:
        - GraphQLValidationError if the AST does not have the expected form; in particular,
          if the AST fails GraphQL's builtin validation against the provided schema, if it
          contains Fragments, or if it contains an InlineFragment at the root level
    """
    built_in_validation_errors = validate(renamed_schema_descriptor.schema, ast)
    if len(built_in_validation_errors) > 0:
        raise GraphQLValidationError("AST does not validate: {}".format(built_in_validation_errors))

    if len(ast.definitions) > 1:  # includes either multiple queries, or fragment definitions
        raise GraphQLValidationError(
            "Only one query may be included, and fragments are not allowed."
        )

    query_definition = ast.definitions[0]
    if not (
        isinstance(query_definition, OperationDefinitionNode)
        and query_definition.operation == OperationType.QUERY
    ):
        raise AssertionError(
            f"AST argument for rename_query is not a query. Instead, query definition was of type "
            f"{type(query_definition)}."
        )

    for selection in query_definition.selection_set.selections:
        if not isinstance(selection, FieldNode):  # possibly an InlineFragment
            raise GraphQLValidationError(
                'Each root selection must be of type "Field", not "{}" as in '
                'selection "{}"'.format(type(selection).__name__, selection)
            )

    visitor = RenameQueryVisitor(
        renamed_schema_descriptor.schema,
        renamed_schema_descriptor.reverse_name_map,
        renamed_schema_descriptor.reverse_field_name_map,
    )
    renamed_ast = visit(ast, visitor)

    return renamed_ast


class RenameQueryVisitor(Visitor):
    def __init__(
        self,
        schema: GraphQLSchema,
        type_renamings: Dict[str, str],
        field_renamings: Dict[str, Dict[str, str]],
    ) -> None:
        """Create a visitor for renaming types and fields in a query AST.

        Args:
            schema: The renamed schema that the original query is written against
            type_renamings: Maps type or root field names to the new value in the dict.
                            Any name not in the dict will be unchanged
            field_renamings: Maps type names to a dict mapping the field names to the new value.
                             Any names not in the dicts will be unchanged
        """
        self.schema = schema
        self.type_renamings = type_renamings
        self.field_renamings = field_renamings
        self.selection_set_level = 0
        # Acts like a stack that records the types of the current scopes. The last item is the top
        # of the stack. Each entry is the name of a type in the new schema, i.e. not the name of
        # the type in the original schema if it was renamed.
        self.current_type_name: List[str] = []

    def _rename_name(self, node: RenameQueryNodeTypesT) -> RenameQueryNodeTypesT:
        """Change the name of the input node if necessary, according to the renamings.

        Args:
            node: represents a field in an AST, containing a .name attribute. It is not modified

        Returns:
            Node that is almost identical to the input node except for a possibly different name. If
            the name was not changed, the returned object is the exact same object as the input
        """
        name_string = node.name.value
        if isinstance(node, FieldNode) and self.selection_set_level > 1:
            field_name = node.name.value
            # The top item in the stack is the type of the field, and the one immediately after that
            # is the type that contains this field in the schema
            current_type_name = self.current_type_name[-2]
            current_type_name_in_original_schema = self.type_renamings.get(
                current_type_name, current_type_name
            )
            new_name_string = self.field_renamings.get(
                current_type_name_in_original_schema, {}
            ).get(field_name, field_name)
        else:
            new_name_string = self.type_renamings.get(
                name_string, name_string
            )  # Default use original
        if new_name_string == name_string:
            return node
        else:
            node_with_new_name = get_copy_of_node_with_new_name(node, new_name_string)
            return node_with_new_name

    def enter_named_type(
        self, node: NamedTypeNode, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> Union[NamedTypeNode, VisitorAction]:
        """Rename name of node."""
        # NamedType nodes describe types in the schema, appearing in InlineFragments
        self.current_type_name.append(node.name.value)
        renamed_node = self._rename_name(node)
        if renamed_node is node:  # Name unchanged, continue traversal
            return None
        else:  # Name changed, return new node, `visit` will make shallow copies along path
            return renamed_node

    def enter_selection_set(
        self, node: SelectionSetNode, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> None:
        """Record that we entered another nested level of selections."""
        self.selection_set_level += 1

    def leave_selection_set(
        self, node: SelectionSetNode, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> None:
        """Record that we left a level of selections."""
        self.selection_set_level -= 1

    def enter_field(
        self, node: FieldNode, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> Union[FieldNode, VisitorAction]:
        """Rename fields."""
        # For a Field to be a root vertex field, it needs to be the first level of
        # selections (fields in more nested selections are normal fields that should not be
        # modified)
        # As FragmentDefinition is not allowed, the parent of the selection must be a query
        # As a query may not start with an inline fragment, all first level selections are
        # fields
        if self.selection_set_level == 1:
            self.current_type_name.append(node.name.value)
        else:
            # Entered a regular field and we want to find its type
            current_type_name = self.current_type_name[-1]
            current_type = self.schema.get_type(current_type_name)
            if current_type is None:
                raise AssertionError(
                    f"Current type is {current_type_name} which doesn't exist in the schema. This "
                    f"is a bug."
                )
            if current_type.ast_node is None:
                raise AssertionError(
                    f"Current type {current_type_name} should have non-null field ast_node, which "
                    f"contains information such as the current type's fields. However, ast_node "
                    f"was None. This is a bug."
                )
            if not isinstance(
                current_type.ast_node, (ObjectTypeDefinitionNode, InterfaceTypeDefinitionNode)
            ):
                raise AssertionError(
                    f"Current type {current_type_name}'s ast_node field should be an "
                    f"ObjectTypeDefinitionNode. However, the actual type was "
                    f"{type(current_type.ast_node)}. This is a bug."
                )
            current_type_fields = current_type.ast_node.fields
            for field_node in current_type_fields:
                # Unfortunately, fields is a list instead of some other datastructure so we actually
                # have to loop through them all.
                if field_node.name.value == node.name.value:
                    field_type_name = get_ast_with_non_null_and_list_stripped(
                        field_node.type
                    ).name.value
                    self.current_type_name.append(field_type_name)
                    break
        renamed_node = self._rename_name(node)
        if renamed_node is node:  # Name unchanged, continue traversal
            return None
        else:  # Name changed, return new node, `visit` will make shallow copies along path
            return renamed_node

    def leave_field(
        self, node: FieldNode, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> None:
        """Record that we left a field."""
        self.current_type_name.pop()
