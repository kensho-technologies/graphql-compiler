# Copyright 2019-present Kensho Technologies, LLC.
from typing import Optional, Type, Union

from graphql.error import GraphQLSyntaxError
from graphql.language.ast import (
    DocumentNode,
    FieldNode,
    InlineFragmentNode,
    ListTypeNode,
    NamedTypeNode,
    Node,
    NonNullTypeNode,
    OperationDefinitionNode,
    OperationType,
    SelectionNode,
    TypeNode,
)
from graphql.language.parser import parse
from graphql.pyutils import FrozenList

from .exceptions import GraphQLParsingError


def get_ast_field_name(ast: FieldNode) -> str:
    """Return the field name for the given AST node."""
    return ast.name.value


def get_ast_field_name_or_none(ast: Union[FieldNode, InlineFragmentNode]) -> Optional[str]:
    """Return the field name for the AST node, or None if the AST is an InlineFragment."""
    if isinstance(ast, InlineFragmentNode):
        return None
    return get_ast_field_name(ast)


def get_human_friendly_ast_field_name(ast: Node) -> str:
    """Return a human-friendly name for the AST node, suitable for error messages."""
    if isinstance(ast, InlineFragmentNode):
        return "type coercion to {}".format(ast.type_condition)
    elif isinstance(ast, OperationDefinitionNode):
        return "{} operation definition".format(ast.operation)
    elif isinstance(ast, FieldNode):
        return get_ast_field_name(ast)
    else:
        # Fall back to Node's __repr__() method.
        # If we need more information for a specific type, we can add another branch in the if-elif.
        return repr(ast)


def safe_parse_graphql(graphql_string: str) -> DocumentNode:
    """Return an AST representation of the given GraphQL input, reraising GraphQL library errors."""
    try:
        ast = parse(graphql_string)
    except GraphQLSyntaxError as e:
        raise GraphQLParsingError(e) from e

    return ast


def get_only_query_definition(
    document_ast: DocumentNode, desired_error_type: Type[Exception]
) -> OperationDefinitionNode:
    """Assert that the Document AST contains only a single definition for a query, and return it."""
    if not isinstance(document_ast, DocumentNode) or not document_ast.definitions:
        raise AssertionError(
            'Received an unexpected value for "document_ast": {}'.format(document_ast)
        )

    if len(document_ast.definitions) != 1:
        raise desired_error_type(
            "Encountered multiple definitions within GraphQL input. This is not supported."
            "{}".format(document_ast.definitions)
        )

    definition_ast = document_ast.definitions[0]
    if not isinstance(definition_ast, OperationDefinitionNode):
        raise desired_error_type(
            f"Expected a query definition at the start of the GraphQL input, but found an "
            f"unsupported and unrecognized definition instead: {definition_ast}"
        )

    if definition_ast.operation != OperationType.QUERY:
        raise desired_error_type(
            "Expected a GraphQL document with a single query definition, but instead found a "
            'but instead found a "{}" operation. This is not supported.'.format(
                definition_ast.operation
            )
        )

    return definition_ast


def get_only_selection_from_ast(
    ast: Union[FieldNode, InlineFragmentNode, OperationDefinitionNode],
    desired_error_type: Type[Exception],
) -> SelectionNode:
    """Return the selected sub-ast, ensuring that there is precisely one."""
    selections = FrozenList([]) if ast.selection_set is None else ast.selection_set.selections

    if len(selections) != 1:
        ast_name = get_human_friendly_ast_field_name(ast)
        if selections:
            selection_names = [
                get_human_friendly_ast_field_name(selection_ast) for selection_ast in selections
            ]
            raise desired_error_type(
                "Expected an AST with exactly one selection, but found "
                "{} selections at AST node named {}: {}".format(
                    len(selection_names), selection_names, ast_name
                )
            )
        else:
            ast_name = get_human_friendly_ast_field_name(ast)
            raise desired_error_type(
                "Expected an AST with exactly one selection, but got "
                "one with no selections. Error near AST node named: {}".format(ast_name)
            )

    return selections[0]


def get_ast_with_non_null_stripped(ast: TypeNode) -> Union[ListTypeNode, NamedTypeNode]:
    """Strip a NonNullType layer around the AST if there is one, return the underlying AST."""
    result: TypeNode

    if isinstance(ast, NonNullTypeNode):
        stripped_ast = ast.type
        if isinstance(stripped_ast, NonNullTypeNode):
            raise AssertionError(
                "NonNullType is unexpectedly found to wrap around another NonNullType in AST "
                "{}, which is not allowed.".format(ast)
            )
        result = stripped_ast
    else:
        result = ast

    if not isinstance(result, (ListTypeNode, NamedTypeNode)):
        raise AssertionError(
            f"Expected the result to be either a ListTypeNode or a NamedTypeNode, but instead "
            f"found: {result}"
        )

    return result


def get_ast_with_non_null_and_list_stripped(ast: TypeNode) -> NamedTypeNode:
    """Strip any NonNullType or List layers around the AST, return the underlying AST."""
    while isinstance(ast, (NonNullTypeNode, ListTypeNode)):
        ast = ast.type

    if not isinstance(ast, NamedTypeNode):
        raise AssertionError(
            f"Expected the AST value to be a NamedTypeNode, but unexpectedly instead found: {ast}"
        )

    return ast
