# Copyright 2018-present Kensho Technologies, LLC.
import six

from ..ir_lowering_common import (extract_optional_location_root_info,
                                  extract_simple_optional_location_to_root,
                                  lower_context_field_existence, merge_consecutive_filter_clauses,
                                  optimize_boolean_expression_comparisons, remove_end_optionals)
from .ir_lowering import (lower_backtrack_blocks,
                          lower_folded_coerce_types_into_filter_blocks,
                          lower_has_substring_binary_compositions,
                          lower_optional_traverse_blocks, remove_backtrack_blocks_from_fold,
                          rewrite_binary_composition_inside_ternary_conditional,
                          truncate_repeated_single_step_traversals)
from ..ir_sanity_checks import sanity_check_ir_blocks_from_frontend
from .between_lowering import lower_comparisons_to_between
from .optional_traversal import (collect_filters_to_first_location_occurrence,
                                 convert_optional_traversals_to_compound_match_query,
                                 lower_context_field_expressions, prune_non_existent_outputs)
from ..match_query import convert_to_match_query
from ..workarounds import orientdb_class_with_while, orientdb_eval_scheduling

from ..blocks import Filter
from ..helpers import Location
from ..expressions import LocalField, BinaryComposition, NullLiteral, TrueLiteral
from .utils import _expression_list_to_conjunction


##############
# Public API #
##############

def lower_ir(ir_blocks, location_types, type_equivalence_hints=None):
    """Lower the IR into an IR form that can be represented in MATCH queries.

    Args:
        ir_blocks: list of IR blocks to lower into MATCH-compatible form
        location_types: a dict of location objects -> GraphQL type objects at that location
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        MatchQuery object containing the IR blocks organized in a MATCH-like structure
    """
    sanity_check_ir_blocks_from_frontend(ir_blocks)

    # These lowering / optimization passes work on IR blocks.
    location_to_optional_results = extract_optional_location_root_info(ir_blocks)
    complex_optional_roots, location_to_optional_root = location_to_optional_results
    simple_optional_root_info = extract_simple_optional_location_to_root(
        ir_blocks, complex_optional_roots, location_to_optional_root)
    ir_blocks = remove_end_optionals(ir_blocks)


    where_filter_expressions = []
    for root_location, root_info_dict in six.iteritems(simple_optional_root_info):
        edge_field = root_info_dict['edge_field']
        edge_field_location = Location(root_location.query_path, field=edge_field)
        edge_local_field = LocalField(edge_field)
        edge_field_non_existence = BinaryComposition(u'=', edge_local_field, NullLiteral)
        inner_location = root_info_dict['inner_location']
        inner_location_existence = BinaryComposition(u'!=', edge_local_field, NullLiteral)
        where_filter_expressions.append(BinaryComposition(u'||',
                                                          edge_field_non_existence,
                                                          inner_location_existence))
    where_block = Filter(_expression_list_to_conjunction(where_filter_expressions))
    ir_blocks.append(where_block)


    ir_blocks = lower_context_field_existence(ir_blocks)
    ir_blocks = optimize_boolean_expression_comparisons(ir_blocks)
    ir_blocks = rewrite_binary_composition_inside_ternary_conditional(ir_blocks)
    ir_blocks = merge_consecutive_filter_clauses(ir_blocks)
    ir_blocks = lower_has_substring_binary_compositions(ir_blocks)
    ir_blocks = orientdb_eval_scheduling.workaround_lowering_pass(ir_blocks)

    # Here, we lower from raw IR blocks into a MatchQuery object.
    # From this point on, the lowering / optimization passes work on the MatchQuery representation.
    match_query = convert_to_match_query(ir_blocks)

    match_query = lower_comparisons_to_between(match_query)

    match_query = lower_optional_traverse_blocks(match_query, location_types)
    match_query = lower_backtrack_blocks(match_query, location_types)
    match_query = truncate_repeated_single_step_traversals(match_query)
    match_query = orientdb_class_with_while.workaround_type_coercions_in_recursions(match_query)

    # Optimize and lower the IR blocks inside @fold scopes.
    new_folds = {
        key: merge_consecutive_filter_clauses(
            remove_backtrack_blocks_from_fold(
                lower_folded_coerce_types_into_filter_blocks(folded_ir_blocks)
            )
        )
        for key, folded_ir_blocks in six.iteritems(match_query.folds)
    }
    match_query = match_query._replace(folds=new_folds)

    compound_match_query = convert_optional_traversals_to_compound_match_query(
        match_query, complex_optional_roots, location_to_optional_root)
    compound_match_query = prune_non_existent_outputs(compound_match_query)
    compound_match_query = collect_filters_to_first_location_occurrence(compound_match_query)
    compound_match_query = lower_context_field_expressions(
        compound_match_query)

    return compound_match_query
