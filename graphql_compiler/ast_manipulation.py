# Copyright 2019-present Kensho Technologies, LLC.
from graphql.error import GraphQLSyntaxError
from graphql.language.ast import (
    Document, InlineFragment, ListType, NonNullType, OperationDefinition
)
from graphql.language.parser import parse

from .exceptions import GraphQLParsingError


def get_ast_field_name(ast):
    """Return the field name for the given AST node."""
    return ast.name.value


def get_ast_field_name_or_none(ast):
    """Return the field name for the AST node, or None if the AST is an InlineFragment."""
    if isinstance(ast, InlineFragment):
        return None
    return get_ast_field_name(ast)


def get_human_friendly_ast_field_name(ast):
    """Return a human-friendly name for the AST node, suitable for error messages."""
    if isinstance(ast, InlineFragment):
        return 'type coercion to {}'.format(ast.type_condition)
    elif isinstance(ast, OperationDefinition):
        return '{} operation definition'.format(ast.operation)

    return get_ast_field_name(ast)


def _preprocess_graphql_string(graphql_string):
    """Apply any necessary preprocessing to the input GraphQL string, returning the new version."""
    # HACK(predrag): Workaround for graphql-core issue, to avoid needless errors:
    #                https://github.com/graphql-python/graphql-core/issues/98
    return graphql_string + '\n'


def safe_parse_graphql(graphql_string):
    """Return an AST representation of the given GraphQL input, avoiding known land mines."""
    graphql_string = _preprocess_graphql_string(graphql_string)
    try:
        ast = parse(graphql_string)
    except GraphQLSyntaxError as e:
        raise GraphQLParsingError(e)

    return ast


def get_only_query_definition(document_ast, desired_error_type):
    """Assert that the Document AST contains only a single definition for a query, and return it."""
    if not isinstance(document_ast, Document) or not document_ast.definitions:
        raise AssertionError(u'Received an unexpected value for "document_ast": {}'
                             .format(document_ast))

    if len(document_ast.definitions) != 1:
        raise desired_error_type(
            u'Encountered multiple definitions within GraphQL input. This is not supported.'
            u'{}'.format(document_ast.definitions))

    definition_ast = document_ast.definitions[0]
    if definition_ast.operation != 'query':
        raise desired_error_type(
            u'Expected a GraphQL document with a single query definition, but instead found a '
            u'but instead found a "{}" operation. This is not supported.'
            .format(definition_ast.operation))

    return definition_ast


def get_only_selection_from_ast(ast, desired_error_type):
    """Return the selected sub-ast, ensuring that there is precisely one."""
    selections = [] if ast.selection_set is None else ast.selection_set.selections

    if len(selections) != 1:
        ast_name = get_human_friendly_ast_field_name(ast)
        if selections:
            selection_names = [
                get_human_friendly_ast_field_name(selection_ast)
                for selection_ast in selections
            ]
            raise desired_error_type(u'Expected an AST with exactly one selection, but found '
                                     u'{} selections at AST node named {}: {}'
                                     .format(len(selection_names), selection_names, ast_name))
        else:
            ast_name = get_human_friendly_ast_field_name(ast)
            raise desired_error_type(u'Expected an AST with exactly one selection, but got '
                                     u'one with no selections. Error near AST node named: {}'
                                     .format(ast_name))

    return selections[0]


def get_ast_with_non_null_stripped(ast):
    """Strip a NonNullType layer around the AST if there is one, return the underlying AST."""
    if isinstance(ast, NonNullType):
        stripped_ast = ast.type
        if isinstance(stripped_ast, NonNullType):
            raise AssertionError(
                u'NonNullType is unexpectedly found to wrap around another NonNullType in AST '
                u'{}, which is not allowed.'.format(ast)
            )
        return stripped_ast
    else:
        return ast


def get_ast_with_non_null_and_list_stripped(ast):
    """Strip any NonNullType or List layers around the AST, return the underlying AST."""
    while isinstance(ast, (NonNullType, ListType)):
        ast = ast.type
    return ast
