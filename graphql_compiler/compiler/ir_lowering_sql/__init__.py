# Copyright 2018-present Kensho Technologies, LLC.
from ...compiler.compiler_frontend import IrAndMetadata
from ..ir_lowering_common import common


##############
# Public API #
##############


def lower_ir(schema_info, ir):
    """Lower the IR blocks into a form that can be represented by a SQL query.

    Args:
        schema_info: SqlAlchemySchemaInfo containing all relevant schema information
        ir: IrAndMetadata representing the query to lower into SQL-compatible form

    Returns:
        ir IrAndMetadata containing lowered blocks, ready to emit
    """
    ir_blocks = ir.ir_blocks
    ir_blocks = common.remove_output_context_field_existence(ir_blocks, ir.query_metadata_table)
    ir_blocks = common.short_circuit_ternary_conditionals(ir_blocks, ir.query_metadata_table)
    return IrAndMetadata(ir_blocks, ir.input_metadata, ir.output_metadata, ir.query_metadata_table)
