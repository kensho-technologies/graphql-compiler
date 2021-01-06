# Copyright 2018-present Kensho Technologies, LLC.
from ..ir_lowering_common.common import (
    lower_context_field_existence,
    merge_consecutive_filter_clauses,
    optimize_boolean_expression_comparisons,
)
from ..ir_self_consistency_checks import self_consistency_check_ir_blocks_from_frontend
from .ir_lowering import (
    lower_coerce_type_block_type_data,
    lower_coerce_type_blocks,
    lower_folded_outputs_and_context_fields,
    rewrite_filters_in_optional_blocks,
)


##############
# Public API #
##############


def lower_ir(schema_info, ir):
    """Lower the IR into an IR form that can be represented in Gremlin queries.

    Args:
        schema_info: CommonSchemaInfo containing all relevant schema information
        ir: IrAndMetadata representing the query to lower into Gremlin-compatible form

    Returns:
        list of IR blocks suitable for outputting as Gremlin
    """
    self_consistency_check_ir_blocks_from_frontend(ir.ir_blocks, ir.query_metadata_table)

    ir_blocks = lower_context_field_existence(ir.ir_blocks, ir.query_metadata_table)
    ir_blocks = optimize_boolean_expression_comparisons(ir_blocks)

    if schema_info.type_equivalence_hints:
        ir_blocks = lower_coerce_type_block_type_data(ir_blocks, schema_info.type_equivalence_hints)

    ir_blocks = lower_coerce_type_blocks(ir_blocks)
    ir_blocks = rewrite_filters_in_optional_blocks(ir_blocks)
    ir_blocks = merge_consecutive_filter_clauses(ir_blocks)
    ir_blocks = lower_folded_outputs_and_context_fields(ir_blocks)

    return ir_blocks
