from typing import Any, Dict, Iterable

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
        yield from (
            # TODO(predrag): Make a helper staticmethod on DataContext for this.
            DataContext(
                neighbor_token, data_context.token_at_location, data_context.expression_stack
            )
            for neighbor_token in neighbor_tokens
        )
        current_token = data_context.current_token
        if current_token is None:
            # The context is already inactive so its neighbors
            # will not be visited in the next iteration.
            yield data_context
        else:
            # We just visited this context's neighbors, deactivate the context
            # so we don't end up visiting them again in the next iteration.
            data_context.push_value_onto_stack(current_token)
            yield DataContext(
                None, data_context.token_at_location, data_context.expression_stack
            )


def _unwrap_recursed_data_contexts(
    data_contexts: Iterable[DataContext]
) -> Iterable[DataContext]:
    for data_context in data_contexts:
        if data_context.current_token is not None:
            # Got a still-active context, produce it as-is.
            yield data_context
        else:
            # Got an inactivated context, reactivate it by replacing the token from the stack.
            current_token = data_context.pop_value_from_stack()
            yield DataContext(
                current_token, data_context.token_at_location, data_context.expression_stack
            )


def handle_recurse_block(
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    block: Recurse,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
    data_contexts = _handle_already_inactive_tokens(data_contexts)

    for current_depth in range(block.depth):
        data_contexts = _iterative_recurse_handler(
            adapter, query_arguments, block, data_contexts, current_depth
        )

    return _unwrap_recursed_data_contexts(data_contexts)

