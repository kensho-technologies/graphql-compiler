# Copyright 2018-present Kensho Technologies, LLC.

import six

from .. import blocks
from ...compiler import expressions
from ...compiler.compiler_frontend import IrAndMetadata
from ..ir_lowering_common.common import (extract_optional_location_root_info,
                                         extract_simple_optional_location_info,
                                         lower_context_field_existence,
                                         merge_consecutive_filter_clauses,
                                         optimize_boolean_expression_comparisons,
                                         remove_end_optionals)
from ...compiler.helpers import Location
from ..ir_lowering_sql import constants
from ..metadata import LocationInfo
from .sql_tree import SqlNode, SqlQueryTree


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
    ir_blocks = lower_context_field_existence(ir.ir_blocks, ir.query_metadata_table)
    return IrAndMetadata(ir_blocks, ir.input_metadata, ir.output_metadata, ir.query_metadata_table)
