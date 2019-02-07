# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy

from graphql.language.ast import Field, InlineFragment, OperationDefinition, SelectionSet

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
    selections = [] if ast.selection_set is None else ast.selection_set.selections

    if len(selections) != 1:
        ast_name = get_human_friendly_ast_field_name(ast)
        if selections:
            selection_names = [
                get_human_friendly_ast_field_name(selection_ast)
                for selection_ast in selections
            ]
            raise GraphQLInvalidMacroError(u'Expected an AST with exactly one selection, but found '
                                           u'{} selections at AST node named {}: {}'
                                           .format(len(selection_names), selection_names, ast_name))
        else:
            ast_name = get_human_friendly_ast_field_name(ast)
            raise GraphQLInvalidMacroError(u'Expected an AST with exactly one selection, but got '
                                           u'one with no selections. Error near AST node named: {}'
                                           .format(ast_name))

    return selections[0]


def remove_directives_from_ast(ast, directive_names_to_omit):
    """Return an equivalent AST to the input, but with instances of the named directives omitted.

    Args:
        ast: GraphQL library AST object, such as a Field, InlineFragment, or OperationDefinition
        directive_names_to_omit: set of strings describing the names of the directives to omit

    Returns:
        GraphQL library AST object, equivalent to the input one, with all instances of
        the named directives omitted. If the specified directives do not appear in the input AST,
        the returned object is the exact same object as the input.
    """
    if not isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        return ast

    made_changes = False

    new_selections = None
    if ast.selection_set is not None:
        new_selections = []
        for selection_ast in ast.selection_set.selections:
            new_selection_ast = remove_directives_from_ast(selection_ast, directive_names_to_omit)

            if selection_ast is not new_selection_ast:
                # Since we did not get the exact same object as the input, changes were made.
                # That means this call will also need to make changes and return a new object.
                made_changes = True

            new_selections.append(new_selection_ast)

    directives_to_keep = [
        directive
        for directive in ast.directives
        if directive.name.value not in directive_names_to_omit
    ]
    if len(directives_to_keep) != len(ast.directives):
        made_changes = True

    if not made_changes:
        # We didn't change anything, return the original input object.
        return ast

    new_ast = copy(ast)
    new_ast.selection_set = SelectionSet(new_selections)
    new_ast.directives = directives_to_keep
    return new_ast


def omit_ast_from_ast_selections(ast, ast_to_omit):
    """Return an equivalent AST to the input, but with the specified AST omitted if it appears.

    Args:
        ast: GraphQL library AST object, such as a Field, InlineFragment, or OperationDefinition
        ast_to_omit: GraphQL library AST object, the *exact same* object that should be omitted.
                     This function uses reference equality, since deep equality can get expensive.

    Returns:
        GraphQL library AST object, equivalent to the input one, with all instances of
        the named directives omitted. If the specified AST does not appear in the input AST,
        the returned object is the exact same object as the input.
    """
    if not isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        return ast

    if ast.selection_set is None:
        return ast

    made_changes = False

    selections_to_keep = []
    for selection_ast in ast.selection_set.selections:
        if selection_ast is ast_to_omit:
            # Drop the current selection.
            made_changes = True
        else:
            new_selection_ast = omit_ast_from_ast_selections(selection_ast, ast_to_omit)
            if new_selection_ast is not selection_ast:
                # The current selection contained the AST to omit, and was altered as a result.
                made_changes = True
            selections_to_keep.append(new_selection_ast)

    if not made_changes:
        return ast

    new_ast = copy(ast)
    if not selections_to_keep:
        new_ast.selection_set = None
    else:
        new_ast.selection_set = SelectionSet(selections_to_keep)

    return new_ast
