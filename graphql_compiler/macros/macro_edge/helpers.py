# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy

from graphql.language.ast import (
    Argument, Field, InlineFragment, ListValue, Name, OperationDefinition, SelectionSet,
    StringValue
)

from ...ast_manipulation import get_ast_field_name
from ...compiler.helpers import get_field_type_from_schema, get_vertex_field_type
from ...schema import FilterDirective, TagDirective
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


def get_all_tag_names(ast):
    """Return a set of strings containing tag names that appear in the query."""
    return {
        # Schema validation has ensured this exists
        directive.arguments[0].value.value
        for ast, directive in _yield_ast_nodes_with_directives(ast)
        if directive.name.value == TagDirective.name
    }


def _remove_colocated_tags(non_macro_names, ast):
    """Return an AST with at most one tag per field by removing tags.

    Args:
        non_macro_names: set of tag names that the user wrote. We prefer keeping these names.
        ast: GraphQL query AST object that potentially has multiple colocated tags. This AST
             should not contain any duplicate tags (different tags with the same name).

    Returns:
        tuple (new_ast, name_change_map). new_ast is the ast with at most one tag per field.
        name_change_map is a dict (string -> string) that contains the new name for each
        tag name. Names of removed tags are mapped to the name of the colocated tag that was
        not removed.
    """
    if not isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        return ast

    made_changes = False
    name_change_map = dict()

    new_selection_set = None
    if ast.selection_set is not None:
        new_selections = []
        for selection_ast in ast.selection_set.selections:
            new_selection_ast, inner_name_change_map = _remove_colocated_tags(
                non_macro_names, selection_ast)
            name_change_map.update(inner_name_change_map)

            if selection_ast is not new_selection_ast:
                # Since we did not get the exact same object as the input, changes were made.
                # That means this call will also need to make changes and return a new object.
                made_changes = True

            new_selections.append(new_selection_ast)
        new_selection_set = SelectionSet(new_selections)

    # Find which name to use, and remove all other tags
    new_directives = ast.directives
    tag_names = {
        directive.arguments[0].value.value
        for directive in ast.directives
        if directive.name.value == TagDirective.name
    }
    made_changes = made_changes or len(tag_names) > 1
    if tag_names:
        name_to_use = None
        user_specified_names = tag_names & non_macro_names
        if len(user_specified_names) == 0:
            name_to_use = min(tag_names, key=len)
        elif len(user_specified_names) == 1:
            name_to_use = next(iter(user_specified_names))
        else:
            raise AssertionError(u'Multiple tags on the same field are not allowed: {}'
                                 .format(user_specified_names))
        name_change_map.update({
            name: name_to_use
            for name in tag_names
        })
        new_directives = [
            directive
            for directive in ast.directives
            if (directive.name.value != TagDirective.name or
                directive.arguments[0].value.value == name_to_use)
        ]

    if not made_changes:
        # We didn't change anything, return the original input object.
        return ast, name_change_map

    new_ast = copy(ast)
    new_ast.selection_set = new_selection_set
    new_ast.directives = new_directives
    return new_ast, name_change_map


def replace_tag_names(name_change_map, ast):
    """Replace tag names that are already in use."""
    if not isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        return ast

    made_changes = False

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

    # Rename tag names in @tag and @filter directives, and record if we made changes
    new_directives = []
    for directive in ast.directives:
        if directive.name.value == TagDirective.name:
            current_name = directive.arguments[0].value.value
            new_name = name_change_map[current_name]
            if new_name != current_name:
                made_changes = True
            renamed_tag_directive = copy(directive)
            renamed_tag_directive.arguments = [Argument(Name('tag_name'), StringValue(new_name))]
            new_directives.append(renamed_tag_directive)
        elif directive.name.value == FilterDirective.name:
            filter_with_renamed_args = copy(directive)
            filter_with_renamed_args.arguments = []
            for argument in directive.arguments:
                if argument.name.value == 'op_name':
                    filter_with_renamed_args.arguments.append(argument)
                elif argument.name.value == 'value':
                    new_value_list = []
                    for value in argument.value.values:
                        if value.value.startswith('%'):
                            current_name = value.value[1:]
                            new_name = name_change_map[current_name]
                            if new_name != current_name:
                                made_changes = True
                            new_value_list.append(StringValue('%' + new_name))
                        else:
                            new_value_list.append(value)
                    filter_with_renamed_args.arguments.append(
                        Argument(Name('value'), value=ListValue(new_value_list)))
                else:
                    raise AssertionError(u'Unknown argument name {} in filter'
                                         .format(argument.name.value))
            new_directives.append(filter_with_renamed_args)
        else:
            new_directives.append(directive)

    if not made_changes:
        # We didn't change anything, return the original input object.
        return ast

    new_ast = copy(ast)
    new_ast.selection_set = new_selection_set
    new_ast.directives = new_directives
    return new_ast


def merge_colocated_tags(non_macro_names, ast):
    """Return an AST with at most one tag per field by removing tags and renaming their uses.

    Filters that use the values of the removed tags will instead use the value of a different
    tag that was on the same field and not removed.

    Args:
        non_macro_names: set of tag names that the user wrote. We prefer keeping these names.
        ast: GraphQL query AST object that potentially has multiple colocated tags. This AST
             should not contain any duplicate tags (different tags with the same name).

    Returns:
        tuple (new_ast, name_change_map). new_ast is the ast with at most one tag per field.
        name_change_map is a dict (string -> string) that contains the new name for each
        tag name. Names of removed tags are mapped to the name of the colocated tag that was
        not removed.
    """
    deduplicated_ast, name_change_map = _remove_colocated_tags(non_macro_names, ast)
    return replace_tag_names(name_change_map, deduplicated_ast)


def generate_disambiguations(existing_names, new_names):
    """Return a dict mapping the new names to similar names not conflicting with existing names.

    Args:
        existing_names: set of strings, the names that are already taken
        new_names: set of strings, the names that might coincide with exisitng names

    Returns:
        dict mapping the new names to other unique names not present in existing_names
    """
    name_mapping = dict()
    for name in new_names:
        # We try adding different suffixes to disambiguate from the existing names. There will
        # be no collisions among the disambiguations because they will all have unique prefixes.
        disambiguation = name
        index = 0
        while disambiguation in existing_names:
            disambiguation = disambiguation + '_copy_' + str(index)
            index += 1
        name_mapping[name] = disambiguation
    return name_mapping


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
