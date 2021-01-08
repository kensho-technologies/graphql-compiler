# Copyright 2019-present Kensho Technologies, LLC.
from ..cypher_query import convert_to_cypher_query
from ..ir_lowering_common.common import (
    lower_context_field_existence,
    merge_consecutive_filter_clauses,
    optimize_boolean_expression_comparisons,
)
from ..ir_self_consistency_checks import self_consistency_check_ir_blocks_from_frontend
from .ir_lowering import (
    insert_explicit_type_bounds,
    move_filters_in_optional_locations_to_global_operations,
    remove_mark_location_after_optional_backtrack,
    renumber_locations_to_one,
    replace_local_fields_with_context_fields,
)


##############
# Public API #
##############


def lower_ir(schema_info, ir):
    """Lower the IR into an IR form that can be represented in Cypher queries.

    Args:
        schema_info: CommonSchemaInfo containing all relevant schema information
        ir: IrAndMetadata representing the query to lower into Cypher-compatible form

    Returns:
        CypherQuery object
    """
    self_consistency_check_ir_blocks_from_frontend(ir.ir_blocks, ir.query_metadata_table)

    ir_blocks = insert_explicit_type_bounds(
        ir.ir_blocks,
        ir.query_metadata_table,
        type_equivalence_hints=schema_info.type_equivalence_hints,
    )

    ir_blocks = remove_mark_location_after_optional_backtrack(ir_blocks, ir.query_metadata_table)
    ir_blocks = lower_context_field_existence(ir_blocks, ir.query_metadata_table)
    ir_blocks = replace_local_fields_with_context_fields(ir_blocks)
    ir_blocks = optimize_boolean_expression_comparisons(ir_blocks)
    ir_blocks = merge_consecutive_filter_clauses(ir_blocks)
    ir_blocks = renumber_locations_to_one(ir_blocks)

    cypher_query = convert_to_cypher_query(
        ir_blocks,
        ir.query_metadata_table,
        type_equivalence_hints=schema_info.type_equivalence_hints,
    )

    cypher_query = move_filters_in_optional_locations_to_global_operations(
        cypher_query, ir.query_metadata_table
    )

    return cypher_query
