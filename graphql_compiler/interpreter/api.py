from typing import Any, Dict, Iterator, List, Tuple

from graphql import GraphQLSchema

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
from ..compiler.compiler_frontend import IrAndMetadata, graphql_to_ir
from ..compiler.helpers import BaseLocation, get_only_element_from_collection
from ..compiler.metadata import QueryMetadataTable
from ..query_formatting.common import validate_arguments
from .block_ops import generate_block_outputs, generate_construct_result_outputs
from .debugging import print_tap
from .hinting import get_hints_for_location_via_readthrough_cache
from .typedefs import DataContext, DataToken, InterpreterAdapter, InterpreterHints


def _get_local_operation_post_block_locations(
    query_metadata_table: QueryMetadataTable, local_operations_blocks: List[BasicBlock]
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

    return [location_at_index[i] for i in range(len(local_operations_blocks))]


def _split_out_global_operations(
    ir_blocks: List[BasicBlock],
) -> Tuple[List[BasicBlock], List[BasicBlock]]:
    # TODO(bojanserafimov): Maybe use emit_sql._traverse_and_validate_blocks
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


def _get_initial_data_contexts(
    adapter: InterpreterAdapter[DataToken],
    start_class: str,
    hints: InterpreterHints,
) -> Iterator[DataContext[DataToken]]:
    # N.B.: Do not replace the below for-yield with a generator, and do not inline this function
    #       into the caller! It's important to have an explicit generator to start the computation.
    #       Without this setup, get_tokens_of_type() is *immediately* called by interpret_ir(),
    #       even if the returned generator is never advanced. That violates our minimality property:
    #       data was loaded via a call to get_tokens_of_type(), even though it wasn't (yet) needed.
    for token in adapter.get_tokens_of_type(start_class, **hints):
        yield DataContext.make_empty_context_from_token(token)


# ##############
# # Public API #
# ##############


def interpret_ir(
    adapter: InterpreterAdapter[DataToken],
    ir_and_metadata: IrAndMetadata,
    query_arguments: Dict[str, Any],
) -> Iterator[Dict[str, Any]]:
    validate_arguments(ir_and_metadata.input_metadata, query_arguments)

    ir_blocks = ir_and_metadata.ir_blocks
    query_metadata_table = ir_and_metadata.query_metadata_table
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints] = {}

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
        query_metadata_table, local_operations
    )

    # Process the first block.
    start_class = get_only_element_from_collection(first_block.start_class)
    root_location = query_metadata_table.root_location
    root_location_hints = get_hints_for_location_via_readthrough_cache(
        query_metadata_table, query_arguments, per_query_hint_cache, root_location
    )
    current_data_contexts: Iterator[DataContext[DataToken]] = _get_initial_data_contexts(
        adapter, start_class, root_location_hints
    )

    current_data_contexts = print_tap("starting contexts", current_data_contexts)

    # Process all local operation blocks after the first one (already processed above).
    for block, block_location in zip(
        local_operations[1:], local_operation_post_block_locations[1:]
    ):
        current_data_contexts = generate_block_outputs(
            adapter,
            query_metadata_table,
            query_arguments,
            per_query_hint_cache,
            block_location,
            block,
            current_data_contexts,
        )

    # Process all global operations except the last block, which constructs the final result.
    for block in global_operations[:-1]:
        current_data_contexts = generate_block_outputs(
            adapter,
            query_metadata_table,
            query_arguments,
            per_query_hint_cache,
            None,
            block,
            current_data_contexts,
        )

    current_data_contexts = print_tap("ending contexts", current_data_contexts)

    # Process the final block.
    return generate_construct_result_outputs(
        adapter,
        query_metadata_table,
        query_arguments,
        per_query_hint_cache,
        last_block,
        current_data_contexts,
    )


def interpret_query(
    adapter: InterpreterAdapter[DataToken],
    schema: GraphQLSchema,
    query: str,
    query_arguments: Dict[str, Any],
) -> Iterator[Dict[str, Any]]:
    ir_and_metadata = graphql_to_ir(schema, query)
    return interpret_ir(adapter, ir_and_metadata, query_arguments)
