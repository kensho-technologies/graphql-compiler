from itertools import chain
from typing import Any, Dict, Iterable, Optional

from ...compiler.blocks import Recurse
from ..typedefs import DataContext, DataToken, InterpreterAdapter


def _handle_already_inactive_tokens(
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
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
    block: Recurse,
    data_contexts: Iterable[DataContext],
    current_depth: int,
) -> Iterable[DataContext]:
    neighbor_data = adapter.project_neighbors(data_contexts, block.direction, block.edge_name)
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


def _unwrap_recursed_data_context(
    data_context: DataContext
) -> Iterable[DataContext]:
    # If any deactivated contexts were piggybacking on this one, unpack and yield them.
    for piggyback_context in data_context.consume_piggyback_contexts():
        yield from _unwrap_recursed_data_context(piggyback_context)

    if data_context.current_token is None:
        # Got a deactivated context, reactivate it first.
        data_context.reactivate()

    yield data_context


def _print_tap(info: str, data_contexts: Iterable[DataContext]) -> Iterable[DataContext]:
    return data_contexts
    # print('\n')
    # unique_id = hash(info)
    # print(unique_id, info)
    # from pprint import pprint
    # from funcy.py3 import chunks
    # for context_chunk in chunks(1, data_contexts):
    #     for context in context_chunk:
    #         pprint((unique_id, context))
    #         yield context


def _counting_tap(info: str, data_contexts: Iterable[DataContext]) -> Iterable[DataContext]:
    counter = 0

    print(f"\n{info} - open")

    for data_context in data_contexts:
        counter += 1
        yield data_context

    print(f"\n{info} - closed, count = {counter}")


def handle_recurse_block(
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    block: Recurse,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
    data_contexts = _handle_already_inactive_tokens(data_contexts)

    # data_contexts = _print_tap("pre-recursion", data_contexts)

    for current_depth in range(block.depth):
        data_contexts = _iterative_recurse_handler(
            adapter, query_arguments, block, data_contexts, current_depth
        )
        # data_contexts = _print_tap(f"after recursion level {current_depth}", data_contexts)

    # data_contexts = _counting_tap("after recursion, before unwrapping", data_contexts)

    all_data_contexts = chain.from_iterable(
        _unwrap_recursed_data_context(data_context)
        for data_context in data_contexts
    )

    # all_data_contexts = _counting_tap("after unwrapping", all_data_contexts)

    return all_data_contexts
