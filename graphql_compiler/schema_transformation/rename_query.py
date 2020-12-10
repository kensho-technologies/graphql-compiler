# Copyright 2019-present Kensho Technologies, LLC.
from typing import Any, Dict, List, Union

from graphql.language.ast import (
    DocumentNode,
    FieldNode,
    NamedTypeNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
)
from graphql.language.visitor import Visitor, VisitorAction, visit
from graphql.validation import validate

from ..exceptions import GraphQLValidationError
from .rename_schema import RenamedSchemaDescriptor
from .utils import RenameQueryNodeTypesT, get_copy_of_node_with_new_name


def rename_query(
    ast: DocumentNode, renamed_schema_descriptor: RenamedSchemaDescriptor
) -> DocumentNode:
    """Translate names of types using reverse_name_map of the input RenamedSchemaDescriptor.

    The direction in which types and fields are renamed is opposite of the process that
    produced the renamed schema descriptor. If a type X was renamed to Y in the schema, then
    any occurrences of type Y in the input query ast will be renamed to X.

    All type names (including ones in type coercions), as well as root vertex fields (fields
    of the query type) will be renamed. No other field names will be renamed.

    Args:
        ast: represents a query
        renamed_schema_descriptor: namedtuple including the attribute reverse_name_map, which maps
                                   the new, renamed names of types to their original names. This
                                   function will revert these renamed types in the query ast back to
                                   their original names

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

    visitor = RenameQueryVisitor(renamed_schema_descriptor.reverse_name_map)
    renamed_ast = visit(ast, visitor)

    return renamed_ast


class RenameQueryVisitor(Visitor):
    def __init__(self, type_renamings: Dict[str, str]) -> None:
        """Create a visitor for renaming types and root vertex fields in a query AST.

        Args:
            type_renamings: Maps type or root field names to the new value in the dict.
                            Any name not in the dict will be unchanged
        """
        self.type_renamings = type_renamings
        self.selection_set_level = 0

    def _rename_name(self, node: RenameQueryNodeTypesT) -> RenameQueryNodeTypesT:
        """Change the name of the input node if necessary, according to type_renamings.

        Args:
            node: represents a field in an AST, containing a .name attribute. It is not modified

        Returns:
            Node that is almost identical to the input node except for a possibly different name. If
            the name was not changed, the returned object is the exact same object as the input
        """
        name_string = node.name.value
        new_name_string = self.type_renamings.get(name_string, name_string)  # Default use original
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
        """Rename root vertex fields."""
        # For a Field to be a root vertex field, it needs to be the first level of
        # selections (fields in more nested selections are normal fields that should not be
        # modified)
        # As FragmentDefinition is not allowed, the parent of the selection must be a query
        # As a query may not start with an inline fragment, all first level selections are
        # fields
        if self.selection_set_level == 1:
            renamed_node = self._rename_name(node)
            if renamed_node is node:  # Name unchanged, continue traversal
                return None
            else:  # Name changed, return new node, `visit` will make shallow copies along path
                return renamed_node

        return None
