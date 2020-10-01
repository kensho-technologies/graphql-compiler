# Copyright 2019-present Kensho Technologies, LLC.
from graphql.language.ast import FieldNode, InlineFragmentNode, SelectionSetNode

from ...ast_manipulation import get_ast_field_name
from ...exceptions import GraphQLCompilationError
from ...global_utils import merge_non_overlapping_dicts
from ...schema import FilterDirective, is_vertex_field_name
from .ast_rewriting import find_target_and_copy_path_to_it, merge_selection_sets, replace_tag_names
from .ast_traversal import get_all_tag_names
from .directives import MacroEdgeTargetDirective
from .name_generation import generate_disambiguations


def _ensure_directives_on_macro_edge_are_supported(macro_edge_field):
    """Raise GraphQLCompilationError if an unsupported directive is used on the macro edge."""
    macro_name = get_ast_field_name(macro_edge_field)
    directives_supported_at_macro_expansion = frozenset({FilterDirective.name})
    for directive in macro_edge_field.directives:
        directive_name = directive.name.value
        if directive_name not in directives_supported_at_macro_expansion:
            raise GraphQLCompilationError(
                "Encountered a {} directive applied to the {} macro edge, which is "
                "not currently supported by the macro system. Please alter your query to not use "
                "unsupported directives on macro edges. Supported directives are: {}".format(
                    directive_name, macro_name, set(directives_supported_at_macro_expansion)
                )
            )


def _merge_selection_into_target(subclass_sets, target_ast, target_class_name, selection_ast):
    """Add the selections, directives, and coercions from the selection_ast to the target_ast.

    Mutate the target_ast, merging into it everything from the selection_ast. If the target
    is at a type coercion and the selection_ast starts with a type coercion, combine them
    into one coercion that preserves the semantics while avoiding nested coercions,
    which are disallowed.

    For details on how fields and directives are merged, see merge_selection_sets().

    Args:
        subclass_sets: dict mapping class names to the set of names of their subclasses
        target_ast: AST at the @macro_edge_target directive
        target_class_name: str, the name of the GraphQL type to which the macro edge points
        selection_ast: AST to merge inside the target. Required to have a nonempty selection set.
    """
    if selection_ast.selection_set is None or not selection_ast.selection_set.selections:
        raise AssertionError(
            "Precondition violated. selection_ast is expected to be nonempty {}".format(
                selection_ast
            )
        )

    # Remove @macro_edge_target directive.
    new_target_directives = [
        directive
        for directive in target_ast.directives
        if directive.name.value != MacroEdgeTargetDirective.name
    ]
    if len(target_ast.directives) != len(new_target_directives) + 1:
        raise AssertionError(
            "Expected the target_ast to contain a single @macro_edge_target "
            "directive, but that was unexpectedly not the case: "
            "{} {}".format(target_ast, new_target_directives)
        )
    target_ast.directives = new_target_directives

    # See if there's a type coercion in the selection_ast.
    coercion = None
    for selection in selection_ast.selection_set.selections:
        if isinstance(selection, InlineFragmentNode):
            if len(selection_ast.selection_set.selections) != 1:
                raise GraphQLCompilationError(
                    "Found selections outside type coercion. "
                    "Please move them inside the coercion. "
                    "Error near field name: {}".format(get_ast_field_name(selection_ast))
                )
            else:
                coercion = selection

    continuation_ast = selection_ast

    # Deal with type coercions immediately within the macro edge, if any.
    if coercion is not None:
        coercion_class = coercion.type_condition.name.value

        # Ensure the coercion is valid. It may only go to a subtype of the type of the vertex field
        # created by the macro edge, where we allow subtypes to be defined by subclass_sets
        # to work around the limitations of the GraphQL type system. If the user's coercion
        # is to a subtype of the macro edge target's type, then this is a narrowing conversion and
        # we simply add the user's coercion, or replace any existing coercion if one is present.
        if coercion_class != target_class_name:
            if coercion_class not in subclass_sets.get(target_class_name, set()):
                raise GraphQLCompilationError(
                    "Attempting to use a type coercion to coerce a value of type {field_type} "
                    "(from field named {field_name}) to incompatible type {coercion_type}, which "
                    "is not a subtype of {field_type}. Only coercions "
                    "to a subtype are allowed.".format(
                        field_type=target_class_name,
                        coercion_type=coercion_class,
                        field_name=get_ast_field_name(selection_ast),
                    )
                )

        continuation_ast = coercion
        if isinstance(target_ast, InlineFragmentNode):
            # The macro edge definition has a type coercion as well, replace it with the user's one.
            target_ast.type_condition = coercion.type_condition
        else:
            # No coercion in the macro edge definition,
            # slip the user's type coercion inside the target AST.
            new_coercion = InlineFragmentNode(
                type_condition=coercion.type_condition,
                selection_set=target_ast.selection_set,
                directives=[],
            )
            target_ast.selection_set = SelectionSetNode(selections=[new_coercion])
            target_ast = new_coercion

    # Merge the continuation into the target
    # target_ast.directives += continuation_ast.directives
    target_ast.directives = list(target_ast.directives) + list(continuation_ast.directives)
    target_ast.selection_set = merge_selection_sets(
        target_ast.selection_set, continuation_ast.selection_set
    )


def _expand_specific_macro_edge(subclass_sets, target_class_name, macro_ast, selection_ast):
    """Produce a tuple containing the new replacement selection AST, and a list of extra selections.

    Args:
        subclass_sets: dict mapping class names to the set of names of its subclasses
        target_class_name: str, the name of the GraphQL type to which the macro edge points
        macro_ast: AST GraphQL object defining the macro edge. Originates from
                   the "expansion_ast" key from a MacroEdgeDescriptor, though potentially sanitized.
        selection_ast: GraphQL AST object containing the selection that is relying on a macro edge.

    Returns:
        tuple of:
        - replacement_selection_ast: GraphQL AST object to replace the given selection_ast
        - sibling_prefix_selections: list of GraphQL AST objects describing the selections
          to be added somewhere in the same scope but before the replacement_selection_ast.
        - sibling_suffix_selections: list of GraphQL AST objects describing the selections
          to be added somewhere in the same scope but after the replacement_selection_ast.
          Since the replacemet_selection_ast is a vertex field, and vertex fields always
          go after property fields, these selections are all vertex fields.
    """
    replacement_selection_ast = None
    sibling_prefix_selections = []
    sibling_suffix_selections = []

    for macro_selection in macro_ast.selection_set.selections:
        new_ast, target_ast = find_target_and_copy_path_to_it(macro_selection)
        if target_ast is None:
            if replacement_selection_ast is None:
                sibling_prefix_selections.append(macro_selection)
            else:
                sibling_suffix_selections.append(macro_selection)
        else:
            if replacement_selection_ast is not None:
                raise AssertionError(
                    "Found multiple @macro_edge_target directives. This means "
                    "the macro definition is invalid, and should never happen "
                    "as it should have been caught during validation. Macro AST: "
                    "{}".format(macro_ast)
                )
            replacement_selection_ast = new_ast
            _merge_selection_into_target(
                subclass_sets, target_ast, target_class_name, selection_ast
            )

    if replacement_selection_ast is None:
        raise AssertionError(
            "Found no @macro_edge_target directives in macro selection set. {}".format(macro_ast)
        )

    return replacement_selection_ast, sibling_prefix_selections, sibling_suffix_selections


# ############
# Public API #
# ############


def expand_potential_macro_edge(macro_registry, current_schema_type, ast, query_args, tag_names):
    """Expand the macro edge at the provided field, if it refers to a macro edge.

    Args:
        macro_registry: MacroRegistry, the registry of macro descriptors used for expansion
        current_schema_type: GraphQL type object describing the current type at the given AST node
        ast: GraphQL AST object that potentially requires macro expansion
        query_args: dict mapping strings to any type, containing the arguments for the query
        tag_names: set of names of tags currently in use. The set is mutated in this function.

    Returns:
        tuple (new_ast, new_query_args, sibling_prefix_selections, sibling_suffix_selections)
        It contains a potentially-rewritten GraphQL AST object and its matching args, as well as
        any sibling selections (lists of fields existing in the same scope as the new_ast)
        that should be added either before (prefix) or after (suffix) the appearance of new_ast
        in its scope. If no changes were made (e.g. if the AST was not a macro edge), the new_ast
        and new_query_args values are guaranteed to be the exact same objects as the input ones,
        whereas the prefix and suffix sibling selections values are guaranteed to be empty lists.
    """
    no_op_result = (ast, query_args, [], [])

    macro_edges_at_this_type = macro_registry.macro_edges_at_class.get(
        current_schema_type.name, dict()
    )

    # If the input AST isn't a Field, it can't be a macro edge. Nothing to be done.
    if not isinstance(ast, FieldNode):
        return no_op_result

    # If the field isn't a vertex field, it can't be a macro edge. Nothing to be done.
    field_name = get_ast_field_name(ast)
    if not is_vertex_field_name(field_name):
        return no_op_result

    # If the vertex field isn't a macro edge, there's nothing to be done.
    macro_edge_descriptor = macro_edges_at_this_type.get(field_name, None)
    if macro_edge_descriptor is None:
        return no_op_result

    # We're dealing with a macro edge. Ensure its use is legal.
    _ensure_directives_on_macro_edge_are_supported(ast)

    # Sanitize the macro, making sure it doesn't use any taken tag names.
    macro_tag_names = get_all_tag_names(macro_edge_descriptor.expansion_ast)
    name_change_map = generate_disambiguations(tag_names, macro_tag_names)
    tag_names.update(name_change_map.values())
    sanitized_macro_ast = replace_tag_names(name_change_map, macro_edge_descriptor.expansion_ast)
    tag_names.update(name_change_map.values())

    new_ast, prefix_selections, suffix_selections = _expand_specific_macro_edge(
        macro_registry.subclass_sets,
        macro_edge_descriptor.target_class_name,
        sanitized_macro_ast,
        ast,
    )
    # TODO(predrag): Write a test that makes sure we've chosen names for filter arguments that
    #                do not overlap with user's filter arguments.
    new_query_args = merge_non_overlapping_dicts(query_args, macro_edge_descriptor.macro_args)

    return (new_ast, new_query_args, prefix_selections, suffix_selections)
