# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy
from itertools import chain

from graphql.language.ast import InlineFragment, SelectionSet
import six

from ..ast_manipulation import (
    get_ast_field_name, get_only_query_definition, get_only_selection_from_ast
)
from ..compiler.helpers import get_uniquely_named_objects_by_name, get_vertex_field_type
from ..exceptions import GraphQLCompilationError, GraphQLInvalidMacroError
from ..schema import is_vertex_field_name
from .macro_edge.directives import MacroEdgeTargetDirective
from .macro_edge.helpers import find_target_and_copy_path_to_it, get_all_tag_names, replace_tag_names, generate_disambiguations


def _merge_non_overlapping_dicts(merge_target, new_data):
    """Produce the merged result of two dicts that are supposed to not overlap."""
    result = dict(merge_target)

    for key, value in six.iteritems(new_data):
        if key in merge_target:
            raise AssertionError(u'Overlapping key "{}" found in dicts that are supposed '
                                 u'to not overlap. Values: {} {}'
                                 .format(key, merge_target[key], value))

        result[key] = value

    return result


def _merge_selection_sets(selection_set_a, selection_set_b):
    """Merge selection sets, merging directives on name conflict.

    Create a selection set that contains the selections of both inputs. If there is a name
    collision on a property field, we take the directives from both inputs on that field and
    merge them. We disallow name collision on a vertex field.

    The value None represents an empty SelectionSet.

    The order of selections in the resulting SelectionSet has the following properties:
    - property fields are before vertex fields.
    - property fields in selection_set_b come later than other property fields.
    - vertex fields in selection_set_b come later than other vertex fields.
    - ties are resolved by respecting the ordering of fields in the input arguments.

    Args:
        selection_set_a: SelectionSet or None to be merged with the other
        selection_set_b: SelectionSet or None to be merged with the other

    Returns:
        SelectionSet or None with contents from both input selection sets
    """
    if selection_set_a is None:
        return selection_set_b
    if selection_set_b is None:
        return selection_set_a

    # Convert to dict
    selection_dict_a = get_uniquely_named_objects_by_name(selection_set_a.selections)
    selection_dict_b = get_uniquely_named_objects_by_name(selection_set_b.selections)

    # Compute intersection by name
    common_selection_dict = dict()
    common_fields = set(selection_dict_a.keys()) & set(selection_dict_b.keys())
    for field_name in common_fields:
        field_a = selection_dict_a[field_name]
        field_b = selection_dict_b[field_name]
        if field_a.selection_set is not None or field_b.selection_set is not None:
            raise GraphQLCompilationError(u'Macro expansion results in a query traversing the '
                                          u'same edge {} twice, which is disallowed.'
                                          .format(field_name))

        merged_field = copy(field_a)
        merged_field.directives = list(chain(field_a.directives, field_b.directives))
        common_selection_dict[field_name] = merged_field

    # Merge dicts, using common_selection_dict for keys present in both selection sets.
    merged_selection_dict = copy(selection_dict_a)
    merged_selection_dict.update(selection_dict_b)
    merged_selection_dict.update(common_selection_dict)  # Overwrite keys in the intersection.

    # The macro or the user code could have an unused (pro-forma) field for the sake of not
    # having an empty selection in a vertex field. We remove pro-forma fields if they are
    # no longer necessary.
    if len(merged_selection_dict) > 1:  # Otherwise we need a pro-forma field
        merged_selection_dict = {
            name: ast
            for name, ast in six.iteritems(merged_selection_dict)
            if ast.selection_set is not None or len(ast.directives) > 0
            # If there's selections or directives under the field, it is not pro-forma.
        }

    # Get a deterministic ordering of the merged selections
    selection_name_order = list(chain((
        ast.name.value
        for ast in selection_set_a.selections
        if ast.name.value not in selection_dict_b
    ), (
        ast.name.value
        for ast in selection_set_b.selections
    )))

    # Make sure that all property fields come before all vertex fields. Note that sort is stable.
    merged_selections = [
        merged_selection_dict[name]
        for name in selection_name_order
        if name in merged_selection_dict
    ]
    return SelectionSet(sorted(
        merged_selections,
        key=lambda ast: ast.selection_set is not None
    ))


def _merge_selection_into_target(target_ast, selection_ast, subclass_sets=None):
    """Add the selections, directives, and coercions from the selection_ast to the target_ast.

    Mutate the target_ast, merging into it everything from the selection_ast. If the target
    is at a type coercion and the selection_ast starts with a type coercion, combine them
    into one coercion that preserves the semantics of nested coercions, which are disallowed.

    For details on how fields and directives are merged, see _merge_selection_sets.

    Args:
        target_ast: AST at the @macro_edge_target directive
        selection_ast: AST to merge inside the target. Required to have a nonempty selection set.
        subclass_sets: optional dict mapping class names to the set of its subclass names
    """
    if selection_ast.selection_set is None or not selection_ast.selection_set.selections:
        raise AssertionError(u'Precondition violated. selection_ast is expected to be nonempty {}'
                             .format(selection_ast))

    # See if there's a type coercion in the selection_ast
    coercion = None
    for selection in selection_ast.selection_set.selections:
        if isinstance(selection, InlineFragment):
            if len(selection_ast.selection_set.selections) != 1:
                raise GraphQLCompilationError(u'Found selections outside type coercion. '
                                              u'Please move them inside the coercion.')
            else:
                coercion = selection

    # Deal with coercions at the target
    continuation_ast = selection_ast
    if coercion is not None:
        coercion_class = coercion.type_condition.name.value
        if isinstance(target_ast, InlineFragment):
            target_class = target_ast.type_condition.name.value
            continuation_ast = coercion
            target_ast.type_condition = coercion.type_condition

            # coercion_class is required to subclass target_class so we can merge the type coercions
            if coercion_class != target_class:
                if subclass_sets is None:
                    # TODO(bojanserafimov): Write test for this failure
                    raise GraphQLCompilationError(
                        u'Cannot prove type coercion at macro target is valid. Please provide a '
                        u'hint that {} subclasses {} using the subclass_sets argument.'
                        .format(coercion_class, target_class))
                else:
                    if (target_class not in subclass_sets or
                            coercion_class not in subclass_sets[target_class]):
                        raise GraphQLCompilationError(u'Invalid type coercion at macro target. {} '
                                                      u'is expected to subclass {}.'
                                                      .format(coercion_class, target_class))
        else:
            # TODO(bojanserafimov): Compute the type at the target and use it to validate.
            raise NotImplementedError(u'Cannot coerce from macro that does not end '
                                      u'in a coercion.')

    # Merge the continuation into the target
    target_ast.directives += continuation_ast.directives
    target_ast.selection_set = _merge_selection_sets(
        target_ast.selection_set, continuation_ast.selection_set)
    target_ast.directives = [
        directive
        for directive in target_ast.directives
        if directive.name.value != MacroEdgeTargetDirective.name
    ]


def _expand_specific_macro_edge(macro_selection_set, selection_ast, subclass_sets=None):
    """Produce a tuple containing the new replacement selection AST, and a list of extra selections.

    Args:
        macro_selection_set: SelectionSet GraphQL object containing the selections defining the
                             macro edge. Can be retrieved as the "expansion_selection_set" key from
                             a MacroEdgeDescriptor.
        selection_ast: GraphQL AST object containing the selection that is relying on a macro edge.
        subclass_sets: optional dict mapping class names to the set of its subclass names

    Returns:
        (replacement selection AST, list of extra selections that need to be added and merged)
        The first value of the tuple is a replacement
    """
    replacement_selection_ast = None
    extra_selections = []

    for macro_ast in macro_selection_set.selections:
        new_ast, target_ast = find_target_and_copy_path_to_it(macro_ast)
        if target_ast is None:
            extra_selections.append(macro_ast)
        else:
            if replacement_selection_ast is not None:
                raise AssertionError(u'Found multiple @macro_edge_target directives. {}'
                                     .format(macro_selection_set))
            replacement_selection_ast = new_ast
            _merge_selection_into_target(target_ast, selection_ast, subclass_sets=subclass_sets)

    if replacement_selection_ast is None:
        raise AssertionError(u'Found no @macro_edge_target directives in macro selection set. {}'
                             .format(macro_selection_set))

    return replacement_selection_ast, extra_selections


def _expand_macros_in_inner_ast(schema, macro_registry, current_schema_type,
                                ast, query_args, tag_names, subclass_sets=None):
    """Return (new_ast, new_query_args) containing the AST after macro expansion.

    Args:
        schema: GraphQL schema object, created using the GraphQL library
        macro_registry: MacroRegistry, the registry of macro descriptors used for expansion
        current_schema_type: GraphQL type object describing the current type at the given AST node
        ast: GraphQL AST object that potentially requires macro expansion
        query_args: dict mapping strings to any type, containing the arguments for the query
        tag_names: set of names of tags currently in use. The set is mutated in this function.
        subclass_sets: optional dict mapping class names to the set of its subclass names

    Returns:
        tuple (new_ast, new_graphql_args) containing a potentially-rewritten GraphQL AST object
        and its new args. If the input GraphQL AST did not make use of any macros,
        the returned values are guaranteed to be the exact same objects as the input ones.
    """
    if ast.selection_set is None:
        # No macro expansion happens at this level if there are no selections.
        return ast, query_args

    macro_edges_at_this_type = macro_registry.macro_edges.get(current_schema_type.name, dict())

    made_changes = False
    new_selections = []
    new_query_args = query_args

    extra_selection_set = None

    for selection_ast in ast.selection_set.selections:
        new_selection_ast = selection_ast

        if isinstance(selection_ast, InlineFragment):
            vertex_field_type = schema.get_type(selection_ast.type_condition.name.value)
            new_selection_ast, new_query_args = _expand_macros_in_inner_ast(
                schema, macro_registry, vertex_field_type,
                selection_ast, new_query_args, tag_names, subclass_sets=subclass_sets)
        else:
            field_name = get_ast_field_name(selection_ast)
            if is_vertex_field_name(field_name):
                # Check if this is a macro edge.
                if field_name in macro_edges_at_this_type:
                    macro_edge_descriptor = macro_edges_at_this_type[field_name]

                    macro_tag_names = get_all_tag_names(macro_edge_descriptor.expansion_selection_set)
                    name_change_map = generate_disambiguations(tag_names, macro_tag_names)
                    tag_names |= set(name_change_map.values())
                    sanitized_macro_ast = replace_tag_names(
                        name_change_map, macro_edge_descriptor.expansion_selection_set)

                    new_selection_ast, extra_selections = _expand_specific_macro_edge(
                        sanitized_macro_ast, selection_ast, subclass_sets=subclass_sets)
                    extra_selection_set = _merge_selection_sets(
                        SelectionSet(extra_selections), extra_selection_set)

                    new_query_args = _merge_non_overlapping_dicts(
                        new_query_args, macro_edge_descriptor.macro_args)

                    # There is now a new AST field name for the selection, after macro expansion.
                    field_name = get_ast_field_name(new_selection_ast)

                # Recurse on the new_selection_ast, to expand any macros
                # that exist at a deeper level.
                # TODO(predrag): Move get_vertex_field_type() to the top-level schema.py file,
                #                instead of reaching into the compiler.helpers module.
                vertex_field_type = get_vertex_field_type(current_schema_type, field_name)
                new_selection_ast, new_query_args = _expand_macros_in_inner_ast(
                    schema, macro_registry, vertex_field_type, new_selection_ast, new_query_args,
                    tag_names, subclass_sets=subclass_sets)

        if new_selection_ast is not selection_ast:
            made_changes = True

        new_selections.append(new_selection_ast)

    if extra_selection_set is not None:
        made_changes = True

    if made_changes:
        result_ast = copy(ast)
        result_ast.selection_set = _merge_selection_sets(
            extra_selection_set, SelectionSet(new_selections))
    else:
        result_ast = ast

    return result_ast, new_query_args


# ############
# Public API #
# ############

def expand_macros_in_query_ast(schema, macro_registry, query_ast, query_args, subclass_sets=None):
    """Return (new_query_ast, new_query_args) containing the GraphQL after macro expansion.

    Args:
        schema: GraphQL schema object, created using the GraphQL library
        macro_registry: MacroRegistry, the registry of macro descriptors used for expansion
        query_ast: GraphQL query AST object that potentially requires macro expansion
        query_args: dict mapping strings to any type, containing the arguments for the query
        subclass_sets: optional dict mapping class names to the set of its subclass names

    Returns:
        tuple (new_query_ast, new_graphql_args) containing a potentially-rewritten GraphQL query AST
        and its new args. If the input GraphQL query AST did not make use of any macros,
        the returned values are guaranteed to be the exact same objects as the input ones.
    """
    definition_ast = get_only_query_definition(query_ast, GraphQLInvalidMacroError)
    base_ast = get_only_selection_from_ast(definition_ast, GraphQLInvalidMacroError)

    base_start_type_name = get_ast_field_name(base_ast)
    query_type = schema.get_query_type()
    base_start_type = query_type.fields[base_start_type_name].type
    tag_names = get_all_tag_names(base_ast)

    new_base_ast, new_query_args = _expand_macros_in_inner_ast(
        schema, macro_registry, base_start_type, base_ast, query_args,
        tag_names, subclass_sets=subclass_sets)

    if new_base_ast is base_ast:
        # No macro expansion happened.
        if new_query_args != query_args:
            raise AssertionError(u'No macro expansion happened, but the query args object changed: '
                                 u'{} vs {}. This should be impossible. GraphQL query AST: {}'
                                 .format(query_args, new_query_args, query_ast))

        new_query_ast = query_ast
        new_query_args = query_args
    else:
        new_definition = copy(definition_ast)
        new_definition.selection_set = SelectionSet([new_base_ast])

        new_query_ast = copy(query_ast)
        new_query_ast.definitions = [new_definition]

    # TODO(bojanserafimov): Remove macro tags if the user has tagged the same field.
    return new_query_ast, new_query_args
