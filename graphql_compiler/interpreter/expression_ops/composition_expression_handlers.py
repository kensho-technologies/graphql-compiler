from typing import Any, Dict, Iterable, Iterator, Optional, Tuple

from ...compiler.expressions import BinaryComposition, TernaryConditional
from ...compiler.helpers import BaseLocation, Location
from ...compiler.metadata import QueryMetadataTable
from ..typedefs import DataContext, DataToken, InterpreterAdapter, InterpreterHints
from .operators import apply_operator
from .typedefs import ExpressionEvaluatorFunc


def _push_values_onto_data_context_stack(
    contexts_and_values: Iterable[Tuple[DataContext, Any]]
) -> Iterator[DataContext]:
    return (
        data_context.push_value_onto_stack(value) for data_context, value in contexts_and_values
    )


def evaluate_binary_composition(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    current_location: Optional[Location],
    expression: BinaryComposition,
    data_contexts: Iterable[DataContext],
) -> Iterator[Tuple[DataContext, Any]]:
    data_contexts = _push_values_onto_data_context_stack(
        expression_evaluator_func(
            adapter,
            query_metadata_table,
            query_arguments,
            per_query_hint_cache,
            current_location,
            expression.left,
            data_contexts,
        )
    )
    data_contexts = _push_values_onto_data_context_stack(
        expression_evaluator_func(
            adapter,
            query_metadata_table,
            query_arguments,
            per_query_hint_cache,
            current_location,
            expression.right,
            data_contexts,
        )
    )

    for data_context in data_contexts:
        # N.B.: The left sub-expression is evaluated first, therefore its value in the stack
        #       is *below* the value of the right sub-expression.
        #       These two lines cannot be inlined into the _apply_operator() call since
        #       the popping order there would be incorrectly reversed.
        right_value = data_context.pop_value_from_stack()
        left_value = data_context.pop_value_from_stack()
        final_expression_value = apply_operator(expression.operator, left_value, right_value)
        yield (data_context, final_expression_value)


def evaluate_ternary_conditional(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    current_location: Optional[Location],
    expression: TernaryConditional,
    data_contexts: Iterable[DataContext],
) -> Iterator[Tuple[DataContext, Any]]:
    # TODO(predrag): Try to optimize this to avoid evaluating sides of expressions we might not use.
    data_contexts = _push_values_onto_data_context_stack(
        expression_evaluator_func(
            adapter,
            query_metadata_table,
            query_arguments,
            per_query_hint_cache,
            current_location,
            expression.predicate,
            data_contexts,
        )
    )
    data_contexts = _push_values_onto_data_context_stack(
        expression_evaluator_func(
            adapter,
            query_metadata_table,
            query_arguments,
            per_query_hint_cache,
            current_location,
            expression.if_true,
            data_contexts,
        )
    )
    data_contexts = _push_values_onto_data_context_stack(
        expression_evaluator_func(
            adapter,
            query_metadata_table,
            query_arguments,
            per_query_hint_cache,
            current_location,
            expression.if_false,
            data_contexts,
        )
    )

    for data_context in data_contexts:
        # N.B.: The expression evaluation order is "predicate, if_true, if_false", and since the
        #       results are pushed onto a stack (LIFO order), the pop order has to be inverted.
        if_false_value = data_context.pop_value_from_stack()
        if_true_value = data_context.pop_value_from_stack()
        predicate_value = data_context.pop_value_from_stack()
        result_value = if_true_value if predicate_value else if_false_value
        yield (data_context, result_value)
