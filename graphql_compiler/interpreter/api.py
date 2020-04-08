from typing import Any, Dict, Iterable, List, Optional

from ..compiler.blocks import (
    Backtrack,
    CoerceType,
    ConstructResult,
    EndOptional,
    Filter,
    Fold,
    GlobalOperationsStart,
    MarkLocation,
    OutputSource,
    QueryRoot,
    Recurse,
    Traverse,
    Unfold,
)
from ..compiler.compiler_entities import BasicBlock
from ..compiler.compiler_frontend import IrAndMetadata
from ..compiler.helpers import BaseLocation, get_only_element_from_collection
from ..compiler.metadata import QueryMetadataTable
from .block_ops import generate_construct_result_outputs, generate_block_outputs
from .debugging import print_tap
from .typedefs import GLOBAL_LOCATION_TYPE_NAME, DataContext, DataToken, InterpreterAdapter


def _make_block_current_type_list(
    query_metadata_table: QueryMetadataTable,
    middle_blocks: List[BasicBlock]
) -> List[str]:
    """Make a parallel list containing the current type name for each block."""
    location_at_index: Dict[int, BaseLocation] = {}
    location_stack: List[BaseLocation] = []
    block_indexes_at_next_mark_location: List[int] = []
    global_operations_index: Optional[int] = None

    for block_index, block in enumerate(middle_blocks):
        if isinstance(block, GlobalOperationsStart):
            # The blocks from this point onward are all global operations, and do not belong
            # to any single location in the query. Therefore, they have no entries in the result.
            global_operations_index = block_index
            break
        elif isinstance(block, MarkLocation):
            current_location = block.location
            location_stack.append(current_location)
            location_at_index[block_index] = current_location

            # Drain the queued-up block indexes, setting them all to the current location.
            for index in block_indexes_at_next_mark_location:
                location_at_index[index] = current_location
            block_indexes_at_next_mark_location = []
        elif isinstance(block, (Traverse, Recurse, Fold, EndOptional)):
            # Each of these blocks "happens" at the current location, even though for some of them,
            # their effect may be to immediately thereafter change the current location.
            location_at_index[block_index] = location_stack[-1]
        elif isinstance(block, (Backtrack, Unfold)):
            # Each of these blocks "happens" at the current location, and
            # then unwinds the location stack one step.
            location_at_index[block_index] = location_stack.pop()
        elif isinstance(block, (OutputSource, Filter, CoerceType)):
            # These blocks all "happen" at the location given by the first subsequent MarkLocation.
            block_indexes_at_next_mark_location.append(block_index)
        else:
            raise AssertionError(f"Unexpected block type '{type(block).__name__}': {block}")

    if block_indexes_at_next_mark_location:
        raise AssertionError(
            f"Unassigned block indexes: {block_indexes_at_next_mark_location} {middle_blocks}"
        )

    if global_operations_index is None:
        raise AssertionError(
            f"Unexpectedly, no global_operations_index found: {middle_blocks}"
        )

    # Create the parallel result list.
    result: List[str] = []
    for i in range(global_operations_index):
        location_info = query_metadata_table.get_location_info(location_at_index[i])
        block = middle_blocks[i]

        current_location_type = location_info.type
        if isinstance(block, CoerceType):
            # Type coercions "happen" at the pre-coercion type.
            current_location_type = location_info.coerced_from_type
            if current_location_type is None:
                raise AssertionError(
                    f"Unexpectedly got {current_location_type} as the coerced-from type for "
                    f"location {location_info} corresponding to block {block}."
                )

        result.append(current_location_type.name)

    for i in range(global_operations_index, len(middle_blocks)):
        result.append(GLOBAL_LOCATION_TYPE_NAME)

    return result


def interpret_ir(
    adapter: InterpreterAdapter[DataToken],
    ir_and_metadata: IrAndMetadata,
    query_arguments: Dict[str, Any]
) -> Iterable[Dict[str, Any]]:
    ir_blocks = ir_and_metadata.ir_blocks
    query_metadata_table = ir_and_metadata.query_metadata_table

    if not ir_blocks:
        raise AssertionError()

    first_block = ir_blocks[0]
    if not isinstance(first_block, QueryRoot):
        raise AssertionError()

    last_block = ir_blocks[-1]
    if not isinstance(last_block, ConstructResult):
        raise AssertionError()

    middle_blocks = ir_blocks[1:-1]
    current_type_list = _make_block_current_type_list(query_metadata_table, middle_blocks)

    start_class = get_only_element_from_collection(first_block.start_class)

    current_data_contexts: Iterable[DataContext[Any]] = (
        DataContext.make_empty_context_from_token(token)
        for token in adapter.get_tokens_of_type(start_class)
    )

    current_data_contexts = print_tap('starting contexts', current_data_contexts)

    for block, current_type_name in zip(middle_blocks, current_type_list):
        current_data_contexts = generate_block_outputs(
            adapter, query_arguments, current_type_name, block, current_data_contexts)

    current_data_contexts = print_tap('ending contexts', current_data_contexts)

    return generate_construct_result_outputs(
        adapter, query_arguments, last_block, current_data_contexts)
