from typing import Any, Dict, Iterable

from ..compiler.blocks import ConstructResult, QueryRoot
from ..compiler.compiler_frontend import IrAndMetadata
from ..compiler.utils import get_only_element_from_collection
from .block_ops import generate_construct_result_outputs, generate_block_outputs
from .debugging import print_tap
from .typedefs import DataContext, DataToken, InterpreterAdapter


def interpret_ir(
    adapter: InterpreterAdapter[DataToken],
    ir_and_metadata: IrAndMetadata,
    query_arguments: Dict[str, Any]
) -> Iterable[Dict[str, Any]]:
    ir_blocks = ir_and_metadata.ir_blocks

    if not ir_blocks:
        raise AssertionError()

    first_block = ir_blocks[0]
    if not isinstance(first_block, QueryRoot):
        raise AssertionError()

    last_block = ir_blocks[-1]
    if not isinstance(last_block, ConstructResult):
        raise AssertionError()

    middle_blocks = ir_blocks[1:-1]

    start_class = get_only_element_from_collection(first_block.start_class)

    current_data_contexts: Iterable[DataContext[Any]] = (
        DataContext.make_empty_context_from_token(token)
        for token in adapter.get_tokens_of_type(start_class)
    )

    current_data_contexts = print_tap('starting contexts', current_data_contexts)

    for block in middle_blocks:
        current_data_contexts = generate_block_outputs(
            adapter, query_arguments, block, current_data_contexts)

    current_data_contexts = print_tap('ending contexts', current_data_contexts)

    return generate_construct_result_outputs(
        adapter, query_arguments, last_block, current_data_contexts)
