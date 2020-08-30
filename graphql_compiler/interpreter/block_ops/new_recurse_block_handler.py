from itertools import chain
from typing import Any, Dict, Generator, Iterable, Optional

from ...compiler.blocks import Recurse
from ...compiler.helpers import BaseLocation
from ...compiler.metadata import QueryMetadataTable
from ..typedefs import DataContext, DataToken, InterpreterAdapter


def _coro(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    current_type_name: str,
    block: Recurse,
    current_depth: int,
) -> Generator[Optional[Tuple[bool, DataContext]], Optional[DataContext], None]:
    can_go_deeper = (current_depth + 1 < block.depth)
    neighbors_generator = (
        adapter.project_neighbors_coro(current_type_name, (block.direction, block.edge_name))
    )

    current_data_context = yield None  # request more input data
    while current_data_context is not None:
        yield (False, current_data_context)  # signal that recursion is over for this context

        # How do I get the neighbors of the current context while keeping project_neighbors()
        # accepting an iterable of contexts?
        next_neighbor = neighbors_generator.send(current_data_context)
        while next_neighbor is not None:
            yield (can_go_deeper, next_neighbor)
            next_neighbor = neighbors_generator.send(None)

        current_data_context = yield None  # request more input data


def handle_recurse_block(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    post_block_location: Optional[BaseLocation],  # None means global location
    block: Recurse,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
    if post_block_location is None:
        raise AssertionError()

    if block.depth < 1:
        raise AssertionError()

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
    coros = [
        _coro(adapter, query_metadata_table, query_arguments, start_type_name, block, current_depth)
    ]
    coros.extend(
        _coro(
            adapter, query_metadata_table, query_arguments,
            subsequent_type_name, block, current_depth,
        )
        for current_depth in range(1, block.depth)
    )

    for data_context in data_contexts:
        current_token = data_context.current_token
        if current_token is None:
            # This context is already inactive, there's nothing to be done here.
            yield data_context
        else:
            yield from recursively_handle_coroutine(coros, 0, data_context)


def recursively_handle_coroutine(coros, current_coro_index, input_data_context) -> Iterable[DataContext]:
    current_coro = coros[current_coro_index]
    coro_state = current_coro.send(input_data_context)
    while coro_state is not None:
        go_deeper, result_context = coro_state
        if go_deeper:
            yield from recursively_handle_coroutine(coros, current_coro_index + 1, result_context)
        else:
            yield result_context

        coro_state = current_coro.send(None)
