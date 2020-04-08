from typing import Any, Dict, Iterable

from ...compiler.blocks import ConstructResult
from ...compiler.expressions import Expression
from ..debugging import print_tap
from ..typedefs import GLOBAL_LOCATION_TYPE_NAME, DataContext, DataToken, InterpreterAdapter
from ..expression_ops import evaluate_expression


def _produce_output(
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    output_name: str,
    output_expression: Expression,
    data_contexts: Iterable[DataContext],
) -> Iterable[DataContext]:
    data_contexts = print_tap(
        'outputting ' + output_name, data_contexts)

    contexts_and_values = evaluate_expression(
        adapter, query_arguments, GLOBAL_LOCATION_TYPE_NAME, output_expression, data_contexts)

    for data_context, value in contexts_and_values:
        data_context.peek_value_on_stack()[output_name] = value
        yield data_context


def generate_construct_result_outputs(
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    block: ConstructResult,
    data_contexts: Iterable[DataContext],
) -> Iterable[Dict[str, Any]]:
    output_fields = block.fields

    data_contexts = (
        data_context.push_value_onto_stack(dict())
        for data_context in data_contexts
    )

    for output_name, output_expression in output_fields.items():
        data_contexts = _produce_output(
            adapter, query_arguments, output_name, output_expression, data_contexts)

    return (
        data_context.pop_value_from_stack()
        for data_context in data_contexts
    )
