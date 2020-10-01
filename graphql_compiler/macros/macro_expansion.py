# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy
from itertools import chain

from graphql.language.ast import InlineFragmentNode, SelectionSetNode

from ..ast_manipulation import (
    get_ast_field_name,
    get_only_query_definition,
    get_only_selection_from_ast,
)
from ..compiler.helpers import get_vertex_field_type, strip_non_null_and_list_from_type
from ..exceptions import GraphQLInvalidMacroError
from ..schema import is_vertex_field_name
from .macro_edge.ast_rewriting import merge_selection_sets
from .macro_edge.ast_traversal import get_all_tag_names
from .macro_edge.expansion import expand_potential_macro_edge


def _expand_macros_in_inner_ast(macro_registry, current_schema_type, ast, query_args, tag_names):
    """Return (new_ast, new_query_args) containing the AST after macro expansion.

    Args:
        macro_registry: MacroRegistry, the registry of macro descriptors used for expansion
        current_schema_type: GraphQL type object describing the current type at the given AST node
        ast: GraphQL AST object that potentially requires macro expansion
        query_args: dict mapping strings to any type, containing the arguments for the query
        tag_names: set of names of tags currently in use. The set is mutated in this function.

    Returns:
        tuple (new_ast, new_graphql_args) containing a potentially-rewritten GraphQL AST object
        and its new args. If the input GraphQL AST did not make use of any macros,
        the returned values are guaranteed to be the exact same objects as the input ones.
    """
    if ast.selection_set is None:
        # No macro expansion happens at this level if there are no selections.
        return ast, query_args

    schema = macro_registry.schema_without_macros

    made_changes = False
    new_selection_set = None
    new_query_args = query_args

    for selection_ast in ast.selection_set.selections:
        new_selection_ast = selection_ast
        prefix_selections = []  # Selections from macro expansion to be added before this selection
        suffix_selections = []  # Selections from macro expansion to be added after this selection

        if isinstance(selection_ast, InlineFragmentNode):
            vertex_field_type = schema.get_type(selection_ast.type_condition.name.value)
            new_selection_ast, new_query_args = _expand_macros_in_inner_ast(
                macro_registry, vertex_field_type, selection_ast, new_query_args, tag_names
            )
        else:
            field_name = get_ast_field_name(selection_ast)
            if is_vertex_field_name(field_name):
                (
                    new_selection_ast,
                    new_query_args,
                    prefix_selections,
                    suffix_selections,
                ) = expand_potential_macro_edge(
                    macro_registry, current_schema_type, selection_ast, new_query_args, tag_names
                )

                if new_selection_ast is not selection_ast:
                    # We expanded a macro edge, make sure the field name stays in sync.
                    field_name = get_ast_field_name(new_selection_ast)

                # Recurse on the new_selection_ast, to expand any macros
                # that exist at a deeper level.
                # TODO(predrag): Move get_vertex_field_type() to the top-level schema.py file,
                #                instead of reaching into the compiler.helpers module.
                vertex_field_type = get_vertex_field_type(current_schema_type, field_name)
                new_selection_ast, new_query_args = _expand_macros_in_inner_ast(
                    macro_registry, vertex_field_type, new_selection_ast, new_query_args, tag_names
                )

        if new_selection_ast is selection_ast and (prefix_selections or suffix_selections):
            raise AssertionError(
                "No macro expansion happened but unexpectedly there are "
                "prefix or suffix selections to expand: {} {}."
                "current_schema_type: {}, ast: {}, field_name: {}".format(
                    prefix_selections, suffix_selections, current_schema_type, ast, field_name
                )
            )

        if new_selection_ast is not selection_ast:
            made_changes = True

        new_selection_set = merge_selection_sets(
            new_selection_set,
            SelectionSetNode(
                selections=list(chain(prefix_selections, [new_selection_ast], suffix_selections))
            ),
        )

    if made_changes:
        result_ast = copy(ast)
        result_ast.selection_set = new_selection_set
        result_query_args = new_query_args
    else:
        if new_query_args is not query_args:
            raise AssertionError(
                "No changes made during macro expansion, but query args changed: "
                "{} vs {}. AST: {}".format(query_args, new_query_args, ast)
            )

        result_ast = ast
        result_query_args = query_args

    return result_ast, result_query_args


# ############
# Public API #
# ############


def expand_macros_in_query_ast(macro_registry, query_ast, query_args):
    """Return (new_query_ast, new_query_args) containing the GraphQL after macro expansion.

    Args:
        macro_registry: MacroRegistry, the registry of macro descriptors used for expansion
        query_ast: GraphQL query AST object that potentially requires macro expansion
        query_args: dict mapping strings to any type, containing the arguments for the query

    Returns:
        tuple (new_query_ast, new_graphql_args) containing a potentially-rewritten GraphQL query AST
        and its new args. If the input GraphQL query AST did not make use of any macros,
        the returned values are guaranteed to be the exact same objects as the input ones.
    """
    definition_ast = get_only_query_definition(query_ast, GraphQLInvalidMacroError)
    base_ast = get_only_selection_from_ast(definition_ast, GraphQLInvalidMacroError)

    base_start_type_name = get_ast_field_name(base_ast)
    query_type = macro_registry.schema_without_macros.query_type
    base_start_type = query_type.fields[base_start_type_name].type
    tag_names = get_all_tag_names(base_ast)

    # Allow list types at the query root in the schema.
    base_start_type = strip_non_null_and_list_from_type(base_start_type)

    new_base_ast, new_query_args = _expand_macros_in_inner_ast(
        macro_registry, base_start_type, base_ast, query_args, tag_names
    )

    if new_base_ast is base_ast:
        # No macro expansion happened.
        if new_query_args != query_args:
            raise AssertionError(
                "No macro expansion happened, but the query args object changed: "
                "{} vs {}. This should be impossible. GraphQL query AST: {}".format(
                    query_args, new_query_args, query_ast
                )
            )

        new_query_ast = query_ast
        new_query_args = query_args
    else:
        new_definition = copy(definition_ast)
        new_definition.selection_set = SelectionSetNode(selections=[new_base_ast])

        new_query_ast = copy(query_ast)
        new_query_ast.definitions = [new_definition]

    return new_query_ast, new_query_args
