# Copyright 2019-present Kensho Technologies, LLC.
"""Helpers for rewriting GraphQL AST objects using structural sharing."""
from copy import copy

from graphql.language.ast import (
    Argument, Field, InlineFragment, ListValue, Name, OperationDefinition, SelectionSet,
    StringValue
)

from ...compiler.helpers import get_parameter_name, is_tagged_parameter
from ...schema import FilterDirective, TagDirective
from ..macro_edge.directives import MacroEdgeTargetDirective


def _replace_tag_names_in_tag_directive(name_change_map, tag_directive):
    """Apply tag parameter renaming to the given tag directive.

    Args:
        name_change_map: Dict[str, str] mapping tag names to new names
        tag_directive: GraphQL library tag directive whose name is in the name_change_map.
                       This ast is not mutated.

    Returns:
        GraphQL library directive object, equivalent to the input one, with its name changed
        according to the name_change_map. If no changes were made, this is the same object
        as the input tag directive.
    """
    # Schema validation has ensured this exists
    current_name = tag_directive.arguments[0].value.value
    new_name = name_change_map[current_name]

    if new_name == current_name:
        # No changes are necessary, return the original input object.
        return tag_directive

    renamed_tag_directive = copy(tag_directive)
    renamed_tag_directive.arguments = [Argument(Name('tag_name'), StringValue(new_name))]
    return renamed_tag_directive


def _replace_tag_names_in_filter_directive(name_change_map, filter_directive):
    """Apply tag parameter renaming to the given filter directive.

    Args:
        name_change_map: Dict[str, str] mapping tag names to new names
        filter_directive: GraphQL library filter directive object that potentially uses
                          tagged parameters. All such tagged parameters should be in
                          the name_change_map. This directive object is not mutated,
                          and if no changes are necessary then it will be returned

    Returns:
        GraphQL library directive object, equivalent to the input one, with any tagged parameters it
        uses replaced according to the name_change_map. If no changes were made, this is the
        same object as the input filter directive.
    """
    made_changes = False

    new_arguments = []
    for argument in filter_directive.arguments:
        if argument.name.value == 'op_name':
            new_arguments.append(argument)
        elif argument.name.value == 'value':
            new_value_list = []
            for value in argument.value.values:
                parameter = value.value
                new_value = value

                # Rewrite tagged parameter names if necessary.
                if is_tagged_parameter(parameter):
                    current_name = get_parameter_name(parameter)
                    new_name = name_change_map[current_name]
                    if new_name != current_name:
                        made_changes = True
                        new_value = StringValue('%' + new_name)

                new_value_list.append(new_value)

            if made_changes:
                new_argument = Argument(Name('value'), value=ListValue(new_value_list))
            else:
                new_argument = argument
            new_arguments.append(new_argument)
        else:
            raise AssertionError(u'Unknown argument name {} in filter directive {}, this should '
                                 u'have been caught in an earlier validation step.'
                                 .format(argument.name.value, filter_directive))

    if not made_changes:
        # No changes were made, return the original input object.
        return filter_directive

    filter_with_renamed_args = copy(filter_directive)
    filter_with_renamed_args.arguments = new_arguments
    return filter_with_renamed_args


def _replace_tag_names_in_directives(name_change_map, directives):
    """Return directives with tag names replaced according to the name_change_map.

    Args:
        name_change_map: Dict[str, str] mapping all tag names in the ast to new names
        directives: list of GraphQL library directive objects in which we want to replace tag names.

    Returns:
        list of GraphQL library directive objects, equivalent to the input ones, with tag names
        renamed according to the name_change_map. If no changes were made, this is the
        same object as the input directives list.
    """
    # Rename tag names in @tag and @filter directives, and record if we made changes
    made_changes = False
    new_directives = []
    for directive in directives:
        if directive.name.value == TagDirective.name:
            renamed_tag_directive = _replace_tag_names_in_tag_directive(name_change_map, directive)
            made_changes_to_tag = directive is not renamed_tag_directive

            made_changes = made_changes or made_changes_to_tag
            new_directives.append(renamed_tag_directive)
        elif directive.name.value == FilterDirective.name:
            filter_with_renamed_args = _replace_tag_names_in_filter_directive(
                name_change_map, directive)
            made_changes_to_filter = directive is not filter_with_renamed_args

            made_changes = made_changes or made_changes_to_filter
            new_directives.append(filter_with_renamed_args)
        else:
            new_directives.append(directive)

    if made_changes:
        return new_directives
    else:
        return directives


# ############
# Public API #
# ############

def replace_tag_names(name_change_map, ast):
    """Return a new ast with tag names replaced according to the name_change_map.

    Args:
        name_change_map: Dict[str, str] mapping all tag names in the ast to new names
        ast: GraphQL library AST object, such as a Field, InlineFragment, or OperationDefinition
             This ast is not mutated.

    Returns:
        GraphQL library AST object, equivalent to the input one, with all tag names replaced
        according to the name_change_map. If no changes were made, this is the same object
        as the input.
    """
    if not isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        return ast

    made_changes = False

    # Recurse into selections.
    new_selection_set = None
    if ast.selection_set is not None:
        new_selections = []
        for selection_ast in ast.selection_set.selections:
            new_selection_ast = replace_tag_names(name_change_map, selection_ast)

            if selection_ast is not new_selection_ast:
                # Since we did not get the exact same object as the input, changes were made.
                # That means this call will also need to make changes and return a new object.
                made_changes = True

            new_selections.append(new_selection_ast)
        new_selection_set = SelectionSet(new_selections)

    # Process the current node's directives.
    directives = ast.directives
    new_directives = _replace_tag_names_in_directives(name_change_map, directives)
    made_changes = made_changes or (directives is not new_directives)

    if not made_changes:
        # We didn't change anything, return the original input object.
        return ast

    new_ast = copy(ast)
    new_ast.selection_set = new_selection_set
    new_ast.directives = new_directives
    return new_ast


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

    new_selection_set = None
    if ast.selection_set is not None:
        new_selections = []
        for selection_ast in ast.selection_set.selections:
            new_selection_ast = remove_directives_from_ast(selection_ast, directive_names_to_omit)

            if selection_ast is not new_selection_ast:
                # Since we did not get the exact same object as the input, changes were made.
                # That means this call will also need to make changes and return a new object.
                made_changes = True

            new_selections.append(new_selection_ast)
        new_selection_set = SelectionSet(new_selections)

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
    new_ast.selection_set = new_selection_set
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


def find_target_and_copy_path_to_it(ast):
    """Copy the AST objects on the path to the target, returning the copied AST and the target AST.

    This function makes it easy to make changes to the AST at the macro edge target directive while
    using structural sharing, i.e. without mutating the original object while doing the minimum
    amount of copying necessary:
    - If called with an AST that does not contain a macro edge target directive, it is guaranteed to
      produce the original AST input object as part of the result, instead of making a copy.
    - If called with an AST that does contain that directive, it will return a new AST object that
      has copies for all AST objects on the traversal path toward the AST containing the directive,
      together with a shallow copy of the AST object that contains the directive itself.

    Args:
        ast: GraphQL library AST object

    Returns:
        tuple containing:
        - GraphQL library AST object equivalent to the input AST. Objects on the path to the
          macro edge target directive are shallow-copied.
        - GraphQL library AST object at the macro edge target directive of the resulting AST,
          or None if there was no such directive in the AST.
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
