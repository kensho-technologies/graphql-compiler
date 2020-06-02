from typing import Any, Dict, Iterable, List, Optional, Tuple

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
from .typedefs import DataContext, DataToken, InterpreterAdapter


def _get_local_operation_post_block_locations(
    query_metadata_table: QueryMetadataTable,
    local_operations_blocks: List[BasicBlock]
) -> List[BaseLocation]:
    """Return a parallel list of the locations into which the block's operation moves us."""
    location_at_index: Dict[int, BaseLocation] = {}
    location_stack: List[BaseLocation] = []
    block_indexes_at_next_mark_location: List[int] = []

    for block_index, block in enumerate(local_operations_blocks):
        if isinstance(block, GlobalOperationsStart):
            raise AssertionError(
                f"GlobalOperationsStart found in local operations blocks: {local_operations_blocks}"
            )
        elif isinstance(block, MarkLocation):
            current_location = block.location
            location_stack.append(current_location)
            location_at_index[block_index] = current_location

            # Drain the queued-up block indexes, setting them all to the current location.
            for index in block_indexes_at_next_mark_location:
                location_at_index[index] = current_location
            block_indexes_at_next_mark_location = []
        elif isinstance(block, (EndOptional)):
            # This blocks "happens" and stays at the current location,
            # given by the preceding MarkLocation block.
            location_at_index[block_index] = location_stack[-1]
        elif isinstance(block, (Backtrack, Unfold)):
            # Each of these blocks unwinds the location stack one step as its effect.
            # The post-block location is therefore whatever is on the stack after the pop.
            location_stack.pop()
            location_at_index[block_index] = location_stack[-1]
        elif isinstance(
            block, (QueryRoot, Traverse, Recurse, Fold, OutputSource, Filter, CoerceType)
        ):
            # These blocks all "happen" at the location given by the first subsequent MarkLocation.
            block_indexes_at_next_mark_location.append(block_index)
        else:
            raise AssertionError(f"Unexpected block type '{type(block).__name__}': {block}")

    if block_indexes_at_next_mark_location:
        raise AssertionError(
            f"Unassigned block indexes: {block_indexes_at_next_mark_location} "
            f"for blocks {local_operations_blocks}"
        )

    return [
        location_at_index[i]
        for i in range(len(local_operations_blocks))
    ]


def _split_out_global_operations(
    ir_blocks: List[BasicBlock]
) -> Tuple[List[BasicBlock], List[BasicBlock]]:
    for block_index, block in enumerate(ir_blocks):
        if isinstance(block, GlobalOperationsStart):
            global_operations_index = block_index
            break
    else:
        raise AssertionError(
            f"Unexpectedly, did not find GlobalOperationsStart block in IR blocks: {ir_blocks}."
        )

    local_operations = ir_blocks[:global_operations_index]
    global_operations = ir_blocks[global_operations_index:]

    return local_operations, global_operations


def interpret_ir(
    adapter: InterpreterAdapter[DataToken],
    ir_and_metadata: IrAndMetadata,
    query_arguments: Dict[str, Any]
) -> Iterable[Dict[str, Any]]:
    ir_blocks = ir_and_metadata.ir_blocks
    query_metadata_table = ir_and_metadata.query_metadata_table

    if not ir_blocks:
        raise AssertionError()

    local_operations, global_operations = _split_out_global_operations(ir_blocks)
    if not local_operations or not global_operations:
        raise AssertionError()

    first_block = local_operations[0]
    if not isinstance(first_block, QueryRoot):
        raise AssertionError()

    last_block = global_operations[-1]
    if not isinstance(last_block, ConstructResult):
        raise AssertionError()

    local_operation_post_block_locations = _get_local_operation_post_block_locations(
        query_metadata_table, local_operations)

    start_class = get_only_element_from_collection(first_block.start_class)

    # Process the first block.
    current_data_contexts: Iterable[DataContext[Any]] = (
        DataContext.make_empty_context_from_token(token)
        for token in adapter.get_tokens_of_type(start_class)
    )

    current_data_contexts = print_tap('starting contexts', current_data_contexts)

    # Process all local operation blocks after the first one (already processed above).
    for block, block_location in zip(
        local_operations[1:], local_operation_post_block_locations[1:]
    ):
        current_data_contexts = generate_block_outputs(
            adapter, query_metadata_table, query_arguments,
            block_location, block, current_data_contexts,
        )

    # Process all global operations except the last block, which constructs the final result.
    for block in global_operations[:-1]:
        current_data_contexts = generate_block_outputs(
            adapter, query_metadata_table, query_arguments,
            None, block, current_data_contexts,
        )

    current_data_contexts = print_tap('ending contexts', current_data_contexts)

    # Process the final block.
    return generate_construct_result_outputs(
        adapter, query_metadata_table, query_arguments, last_block, current_data_contexts)
