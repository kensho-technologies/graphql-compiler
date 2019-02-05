# Copyright 2019-present Kensho Technologies, LLC.
from graphql.language.ast import Field, InlineFragment, OperationDefinition

from ...ast_manipulation import get_human_friendly_ast_field_name
from ...exceptions import GraphQLInvalidMacroError


def _yield_ast_nodes_with_directives(ast):
    """Get the AST objects where directives appear, anywhere in the given AST.

    Args:
        ast: GraphQL library AST object, such as a Field, InlineFragment, or OperationDefinition

    Returns:
        Iterable[Tuple[AST object, Directive]], where each tuple describes an AST node together with
        the directive it contains. If an AST node contains multiple directives, the AST node will be
        returned as part of multiple tuples, in no particular order.
    """
    for directive in ast.directives:
        yield (ast, directive)

    if isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        if ast.selection_set is not None:
            for sub_selection_set in ast.selection_set.selections:
                # TODO(predrag): When we make the compiler py3-only, use a "yield from" here.
                for entry in _yield_ast_nodes_with_directives(sub_selection_set):
                    yield entry
    else:
        raise AssertionError(u'Unexpected AST type received: {} {}'.format(type(ast), ast))


def get_directives_for_ast(ast):
    """Return a dict of directive name -> list of (ast, directive) where that directive is used.

    Args:
        ast: GraphQL library AST object, such as a Field, InlineFragment, or OperationDefinition

    Returns:
        Dict[str, List[Tuple[AST object, Directive]]], allowing the user to find the instances
        in this AST object where a directive with a given name appears; for each of those instances,
        we record and return the AST object where the directive was applied, together with the AST
        Directive object describing it together with any arguments that might have been supplied.
    """
    result = {}

    for ast, directive in _yield_ast_nodes_with_directives(ast):
        directive_name = directive.name.value
        result.setdefault(directive_name, []).append((ast, directive))

    return result


def get_only_selection_from_ast(ast):
    """Return the selected sub-ast, ensuring that there is precisely one."""
    if ast.selection_set is None:
        ast_name = get_human_friendly_ast_field_name(ast)
        raise GraphQLInvalidMacroError(u'Expected an AST with exactly one selection, but got one '
                                       u'with no selections. Error near AST node named: {}'
                                       .format(ast_name))

    selections = ast.selection_set.selections
    if len(selections) != 1:
        ast_name = get_human_friendly_ast_field_name(ast)
        selection_names = [
            get_human_friendly_ast_field_name(selection_ast)
            for selection_ast in selections
        ]
        raise GraphQLInvalidMacroError(u'Expected an AST with exactly one selection, but found '
                                       u'{} selections at AST node named {}: {}'
                                       .format(len(selection_names), selection_names, ast_name))

    return selections[0]
