from typing import Any, Dict, Iterable

from ...compiler.blocks import (
    Backtrack, BasicBlock, CoerceType, EndOptional, Filter, GlobalOperationsStart, MarkLocation,
    Recurse, Traverse,
)
from ...compiler.metadata import QueryMetadataTable
from ..debugging import print_tap
from ..typedefs import DataContext, DataToken, InterpreterAdapter
from .immediate_block_handlers import (
    handle_backtrack_block, handle_coerce_type_block, handle_filter_block,
    handle_mark_location_block, handle_traverse_block,
)
from .recurse_block_handler import handle_recurse_block


def generate_block_outputs(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    current_type_name: str,
    block: BasicBlock,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
    no_op_types = (EndOptional, GlobalOperationsStart,)
    if isinstance(block, no_op_types):
        return data_contexts

    data_contexts = print_tap('pre: ' + str(block), data_contexts)

    handler_functions = {
        CoerceType: handle_coerce_type_block,
        Filter: handle_filter_block,
        MarkLocation: handle_mark_location_block,
        Traverse: handle_traverse_block,
        Backtrack: handle_backtrack_block,
        Recurse: handle_recurse_block,
    }
    handler = handler_functions[type(block)]

    return handler(
        adapter, query_metadata_table, query_arguments, current_type_name, block, data_contexts,
    )
