# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy

from graphql.language.ast import Field, InlineFragment, OperationDefinition, SelectionSet

from ...ast_manipulation import get_ast_field_name
from ...compiler.helpers import get_field_type_from_schema, get_vertex_field_type
from ..macro_edge.directives import MacroEdgeTargetDirective


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


def find_target_and_copy_path_to_it(ast):
    """Copy the AST objects on the path to the target, returning it and the target AST.

    This function makes it easy to change the AST at the @target directive without mutating the
    original object or doing a deepcopy.

    Args:
        ast: GraphQL library AST object

    Returns:
        pair containing:
        - GraphQL library AST object equal to the input. Objects on the path to the @target
          directive are shallow copied.
        - GraphQL library AST object at the @target directive of the resulting AST, or None
          if there was no @target directive in the AST.
    """
    # Base case
    for directive in ast.directives:
        if directive.name.value == MacroEdgeTargetDirective.name:
            target_ast = copy(ast)
            return target_ast, target_ast

    # Recurse
    new_selections = []
    target_ast = None
    if isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        if ast.selection_set is not None:
            for selection in ast.selection_set.selections:
                new_selection, possible_target_ast = find_target_and_copy_path_to_it(selection)
                new_selections.append(new_selection)
                if possible_target_ast is not None:
                    target_ast = possible_target_ast
    else:
        raise AssertionError(u'Unexpected AST type received: {} {}'.format(type(ast), ast))

    if target_ast is None:
        return ast, None
    else:
        new_ast = copy(ast)
        new_ast.selection_set = SelectionSet(new_selections)
        return new_ast, target_ast


def _get_type_at_macro_edge_target_using_current_type(schema, ast, current_type):
    """Return type at the @macro_edge_target or None if there is no target."""
    # Base case
    for directive in ast.directives:
        if directive.name.value == MacroEdgeTargetDirective.name:
            return current_type

    if not isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        raise AssertionError(u'Unexpected AST type received: {} {}'.format(type(ast), ast))

    # Recurse
    if ast.selection_set is not None:
        for selection in ast.selection_set.selections:
            type_in_selection = None
            if isinstance(selection, Field):
                if selection.selection_set is not None:
                    type_in_selection = get_vertex_field_type(
                        current_type, selection.name.value)
            elif isinstance(selection, InlineFragment):
                type_in_selection = schema.get_type(selection.type_condition.name.value)
            else:
                raise AssertionError(u'Unexpected selection type received: {} {}'
                                     .format(type(selection), selection))

            if type_in_selection is not None:
                type_at_target = _get_type_at_macro_edge_target_using_current_type(
                    schema, selection, type_in_selection)
                if type_at_target is not None:
                    return type_at_target

    return None  # Didn't find target


def get_type_at_macro_edge_target(schema, ast):
    """Return the GraphQL type at the @macro_edge_target or None if there is no target."""
    root_type = get_ast_field_name(ast)
    root_schema_type = get_field_type_from_schema(schema.get_query_type(), root_type)
    return _get_type_at_macro_edge_target_using_current_type(schema, ast, root_schema_type)


def omit_ast_from_ast_selections(ast, ast_to_omit):
    """Return an equivalent AST to the input, but with the specified AST omitted if it appears.

    Args:
        ast: GraphQL library AST object, such as a Field, InlineFragment, or OperationDefinition
        ast_to_omit: GraphQL library AST object, the *exact same* object that should be omitted.
                     This function uses reference equality, since deep equality can get expensive.

    Returns:
        GraphQL library AST object, equivalent to the input one, with all instances of
        the specified AST omitted. If the specified AST does not appear in the input AST,
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
