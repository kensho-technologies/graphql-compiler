# Copyright 2018-present Kensho Technologies, LLC.
import six

from ...schema.schema_info import CommonSchemaInfo
from ..blocks import Filter
from ..compiler_frontend import IrAndMetadata
from ..ir_lowering_common.common import (
    extract_optional_location_root_info,
    extract_simple_optional_location_info,
    lower_context_field_existence,
    merge_consecutive_filter_clauses,
    optimize_boolean_expression_comparisons,
    remove_end_optionals,
)
from ..ir_self_consistency_checks import self_consistency_check_ir_blocks_from_frontend
from ..match_query import MatchQuery, convert_to_match_query
from ..workarounds import (
    orientdb_class_with_while,
    orientdb_eval_scheduling,
    orientdb_query_execution,
)
from .between_lowering import lower_comparisons_to_between
from .ir_lowering import (
    lower_backtrack_blocks,
    lower_folded_coerce_types_into_filter_blocks,
    lower_string_operators,
    remove_backtrack_blocks_from_fold,
    rewrite_binary_composition_inside_ternary_conditional,
    truncate_repeated_single_step_traversals,
    truncate_repeated_single_step_traversals_in_sub_queries,
)
from .optional_traversal import (
    collect_filters_to_first_location_occurrence,
    convert_optional_traversals_to_compound_match_query,
    lower_context_field_expressions,
    prune_non_existent_outputs,
)
from .utils import construct_where_filter_predicate


##############
# Public API #
##############


def lower_ir(schema_info: CommonSchemaInfo, ir: IrAndMetadata) -> MatchQuery:
    """Lower the IR into an IR form that can be represented in MATCH queries.

    Args:
        schema_info: CommonSchemaInfo containing all relevant schema information
        ir: IrAndMetadata representing the query to lower into MATCH-compatible form

    Returns:
        MatchQuery object containing the IR blocks organized in a MATCH-like structure
    """
    self_consistency_check_ir_blocks_from_frontend(ir.ir_blocks, ir.query_metadata_table)

    # Construct the mapping of each location to its corresponding GraphQL type.
    location_types = {
        location: location_info.type
        for location, location_info in ir.query_metadata_table.registered_locations
    }

    # Compute the set of all locations that have associated type coercions.
    coerced_locations = {
        location
        for location, location_info in ir.query_metadata_table.registered_locations
        if location_info.coerced_from_type is not None
    }

    # Extract information for both simple and complex @optional traverses
    location_to_optional_results = extract_optional_location_root_info(ir.ir_blocks)
    complex_optional_roots, location_to_optional_roots = location_to_optional_results
    simple_optional_root_info = extract_simple_optional_location_info(
        ir.ir_blocks, complex_optional_roots, location_to_optional_roots
    )
    ir_blocks = remove_end_optionals(ir.ir_blocks)

    # Append global operation block(s) to filter out incorrect results
    # from simple optional match traverses (using a WHERE statement)
    if len(simple_optional_root_info) > 0:
        where_filter_predicate = construct_where_filter_predicate(
            ir.query_metadata_table, simple_optional_root_info
        )
        # The GlobalOperationsStart block should already exist at this point. It is inserted
        # in the compiler_frontend, and this function asserts that at the beginning.
        ir_blocks.insert(-1, Filter(where_filter_predicate))

    # These lowering / optimization passes work on IR blocks.
    ir_blocks = lower_context_field_existence(ir_blocks, ir.query_metadata_table)
    ir_blocks = optimize_boolean_expression_comparisons(ir_blocks)
    ir_blocks = rewrite_binary_composition_inside_ternary_conditional(ir_blocks)
    ir_blocks = merge_consecutive_filter_clauses(ir_blocks)
    ir_blocks = lower_string_operators(ir_blocks)
    ir_blocks = orientdb_eval_scheduling.workaround_lowering_pass(
        ir_blocks, ir.query_metadata_table
    )

    # Here, we lower from raw IR blocks into a MatchQuery object.
    # From this point on, the lowering / optimization passes work on the MatchQuery representation.
    match_query = convert_to_match_query(ir_blocks)

    match_query = lower_comparisons_to_between(match_query)

    match_query = lower_backtrack_blocks(match_query, ir.query_metadata_table)
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
        match_query, complex_optional_roots, location_to_optional_roots
    )
    compound_match_query = prune_non_existent_outputs(compound_match_query)
    compound_match_query = collect_filters_to_first_location_occurrence(compound_match_query)
    compound_match_query = lower_context_field_expressions(compound_match_query)

    compound_match_query = truncate_repeated_single_step_traversals_in_sub_queries(
        compound_match_query
    )
    compound_match_query = orientdb_query_execution.expose_ideal_query_execution_start_points(
        compound_match_query, location_types, coerced_locations
    )

    return compound_match_query
