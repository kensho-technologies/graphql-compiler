from typing import Any, Dict, Iterable

from ...compiler.blocks import Backtrack, CoerceType, Filter, MarkLocation, Traverse
from ...compiler.helpers import get_only_element_from_collection
from ...compiler.metadata import QueryMetadataTable
from ..expression_ops import evaluate_expression
from ..typedefs import DataContext, DataToken, InterpreterAdapter


def handle_filter_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    current_type_name: str,
    block: Filter,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
    predicate = block.predicate

    # TODO(predrag): Handle the "filters depending on missing optional values pass" rule.
    #                Currently, pre-lowering IR has the invariant: one @filter = one Filter block.
    #                Add an explicit test to ensure this continues to be the case, then make use of
    #                missing optional value return a "ALWAYS_TRUE" special constant that causes all
    #                BinaryComposition operators except boolean logic ones to return True no matter
    #                what when encountering it.

    yield from (
        data_context
        for data_context, predicate_value in evaluate_expression(
            adapter, query_metadata_table, query_arguments,
            current_type_name, predicate, data_contexts,
        )
        if predicate_value or data_context.current_token is None
    )


def handle_traverse_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    current_type_name: str,
    block: Traverse,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
    neighbor_data = adapter.project_neighbors(
        data_contexts, current_type_name, block.direction, block.edge_name
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
            yield DataContext(
                None, data_context.token_at_location, data_context.expression_stack
            )


def handle_coerce_type_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    current_type_name: str,
    block: CoerceType,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
    coercion_type = get_only_element_from_collection(block.target_class)
    return (
        data_context
        for data_context, can_coerce in adapter.can_coerce_to_type(
            data_contexts, current_type_name, coercion_type
        )
        if can_coerce or data_context.current_token is None
    )


def handle_mark_location_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    current_type_name: str,
    block: MarkLocation,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
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
    current_type_name: str,
    block: Backtrack,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
    backtrack_location = block.location
    for data_context in data_contexts:
        yield DataContext(
            data_context.token_at_location[backtrack_location],
            data_context.token_at_location,
            data_context.expression_stack,
        )
