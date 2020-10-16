from itertools import chain
from typing import Any, Dict, Iterable, Iterator, Optional

from ...compiler.blocks import Recurse
from ...compiler.helpers import BaseLocation
from ...compiler.metadata import QueryMetadataTable
from ..typedefs import DataContext, DataToken, InterpreterAdapter, InterpreterHints


def _handle_already_inactive_tokens(
    data_contexts: Iterable[DataContext],
) -> Iterator[DataContext]:
    for data_context in data_contexts:
        current_token = data_context.current_token
        if current_token is None:
            # Got a context that is already deactivated at the start of the recursion.
            # Push "None" onto the stack to make sure it remains deactivated at the end of it too.
            data_context.push_value_onto_stack(None)
        yield data_context


def _iterative_recurse_handler(
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    current_type_name: str,
    block: Recurse,
    data_contexts: Iterable[DataContext],
    current_depth: int,
) -> Iterator[DataContext]:
    # TODO(predrag): Add hints to this call.
    neighbor_data = adapter.project_neighbors(
        data_contexts,
        current_type_name,
        (block.direction, block.edge_name),
    )
    for data_context, neighbor_tokens in neighbor_data:
        # Deal with the current context. It needs to be deactivated (it might already be so),
        # so we don't end up visiting its neighbors again in the next iteration.
        data_context.ensure_deactivated()

        data_context_to_piggyback: Optional[DataContext] = data_context

        # Yield contexts for all neighbors.
        for neighbor_token in neighbor_tokens:
            neighbor_context = DataContext(
                neighbor_token, data_context.token_at_location, data_context.expression_stack
            )
            if data_context_to_piggyback is not None:
                # We haven't yet managed to set the current context as a piggy-back
                # onto a neighbor context. Let's do that now.
                neighbor_context.add_piggyback_context(data_context_to_piggyback)
                data_context_to_piggyback = None

            yield neighbor_context

        if data_context_to_piggyback is not None:
            # We failed to find a context to piggyback onto. Yield the current context directly.
            yield data_context_to_piggyback


def _unwrap_recursed_data_context(data_context: DataContext) -> Iterator[DataContext]:
    # If any deactivated contexts were piggybacking on this one, unpack and yield them.
    for piggyback_context in data_context.consume_piggyback_contexts():
        yield from _unwrap_recursed_data_context(piggyback_context)

    if data_context.current_token is None:
        # Got a deactivated context, reactivate it first.
        data_context.reactivate()

    yield data_context


def handle_recurse_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    post_block_location: Optional[BaseLocation],  # None means global location
    block: Recurse,
    data_contexts: Iterable[DataContext],
) -> Iterator[DataContext]:
    if post_block_location is None:
        raise AssertionError()

    if block.depth < 1:
        raise AssertionError()

    data_contexts = _handle_already_inactive_tokens(data_contexts)

    # In the very first level of recursion, we are getting the neighbors of
    # the parent location's vertex, with the neighbors in question located at
    # the post_block_location query location.
    #
    # That means that for the first recursion level, the "current_type_name" is
    # the type at the parent location. For subsequent recursion levels, we are recursing
    # from a vertex produced by the recursion's first level to its neighbors. Therefore,
    # for each subsequent recursion level after the first, the "current_type_name" is
    # the type at the post-block location.
    #
    # TODO(predrag): This is a tricky edge case. Cover this with a good set of tests.
    post_block_location_info = query_metadata_table.get_location_info(post_block_location)
    parent_location_info = query_metadata_table.get_location_info(
        post_block_location_info.parent_location
    )
    start_type_name = parent_location_info.type.name
    subsequent_type_name = post_block_location_info.type.name

    current_depth = 0
    data_contexts = _iterative_recurse_handler(
        adapter,
        query_arguments,
        start_type_name,
        block,
        data_contexts,
        current_depth,
    )

    for current_depth in range(1, block.depth):
        data_contexts = _iterative_recurse_handler(
            adapter, query_arguments, subsequent_type_name, block, data_contexts, current_depth
        )

    all_data_contexts = chain.from_iterable(
        _unwrap_recursed_data_context(data_context) for data_context in data_contexts
    )

    return all_data_contexts
