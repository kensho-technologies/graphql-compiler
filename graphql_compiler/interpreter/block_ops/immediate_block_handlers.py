from typing import Any, Dict, Iterable, Iterator, Optional

from ...compiler.blocks import Backtrack, CoerceType, Filter, MarkLocation, Traverse
from ...compiler.helpers import BaseLocation, get_only_element_from_collection
from ...compiler.metadata import QueryMetadataTable
from ..expression_ops import evaluate_expression
from ..hinting import get_hints_for_location_via_readthrough_cache
from ..typedefs import DataContext, DataToken, InterpreterAdapter, InterpreterHints


def handle_filter_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    post_block_location: Optional[BaseLocation],  # None means global location
    block: Filter,
    data_contexts: Iterable[DataContext],
) -> Iterator[DataContext]:
    if post_block_location is None:
        raise AssertionError()

    # TODO(predrag): Handle the "filters depending on missing optional values pass" rule.
    #                Currently, pre-lowering IR has the invariant: one @filter = one Filter block.
    #                Add an explicit test to ensure this continues to be the case, then make use of
    #                missing optional value return a "ALWAYS_TRUE" special constant that causes all
    #                BinaryComposition operators except boolean logic ones to return True no matter
    #                what when encountering it.
    predicate = block.predicate
    yield from (
        data_context
        for data_context, predicate_value in evaluate_expression(
            adapter,
            query_metadata_table,
            query_arguments,
            per_query_hint_cache,
            post_block_location,
            predicate,
            data_contexts,
        )
        if predicate_value or data_context.current_token is None
    )


def handle_traverse_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    post_block_location: Optional[BaseLocation],  # None means global location
    block: Traverse,
    data_contexts: Iterable[DataContext],
) -> Iterator[DataContext]:
    if post_block_location is None:
        raise AssertionError()

    # We are getting the neighbors of the parent location's vertex, and those neighbors
    # are located at the post_block_location query location.
    #
    # TODO(predrag): Apply the same logic to Fold blocks, once implemented.
    post_block_location_info = query_metadata_table.get_location_info(post_block_location)
    parent_location_info = query_metadata_table.get_location_info(
        post_block_location_info.parent_location
    )

    interpreter_hints = get_hints_for_location_via_readthrough_cache(
        query_metadata_table, query_arguments, per_query_hint_cache, post_block_location
    )

    neighbor_data = adapter.project_neighbors(
        data_contexts,
        parent_location_info.type.name,
        (block.direction, block.edge_name),
        **interpreter_hints
    )
    for data_context, neighbor_tokens in neighbor_data:
        has_neighbors = False
        for neighbor_token in neighbor_tokens:
            has_neighbors = True
            yield (
                # TODO(predrag): Make a helper staticmethod on DataContext for this.
                DataContext(
                    neighbor_token, data_context.token_at_location, data_context.expression_stack
                )
            )
        if block.optional and not has_neighbors:
            yield DataContext(None, data_context.token_at_location, data_context.expression_stack)


def handle_coerce_type_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    post_block_location: Optional[BaseLocation],  # None means global location
    block: CoerceType,
    data_contexts: Iterable[DataContext],
) -> Iterator[DataContext]:
    location_info = query_metadata_table.get_location_info(post_block_location)

    interpreter_hints = get_hints_for_location_via_readthrough_cache(
        query_metadata_table,
        query_arguments,
        per_query_hint_cache,
        post_block_location,
    )

    coercion_type = get_only_element_from_collection(block.target_class)
    return (
        data_context
        for data_context, can_coerce in adapter.can_coerce_to_type(
            data_contexts, location_info.coerced_from_type.name, coercion_type, **interpreter_hints
        )
        if can_coerce or data_context.current_token is None
    )


def handle_mark_location_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    post_block_location: Optional[BaseLocation],  # None means global location
    block: MarkLocation,
    data_contexts: Iterable[DataContext],
) -> Iterator[DataContext]:
    current_location = block.location
    for data_context in data_contexts:
        token_at_location = dict(data_context.token_at_location)
        token_at_location[current_location] = data_context.current_token
        yield DataContext(
            data_context.current_token,
            token_at_location,
            data_context.expression_stack,
        )


def handle_backtrack_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    post_block_location: Optional[BaseLocation],  # None means global location
    block: Backtrack,
    data_contexts: Iterable[DataContext],
) -> Iterator[DataContext]:
    backtrack_location = block.location
    for data_context in data_contexts:
        yield DataContext(
            data_context.token_at_location[backtrack_location],
            data_context.token_at_location,
            data_context.expression_stack,
        )
