from typing import Any, Dict, Iterable, Tuple, Union

from ...compiler.expressions import (
    ContextField, ContextFieldExistence, Literal, LocalField, OutputContextField, Variable,
)
from ..typedefs import DataContext, DataToken, InterpreterAdapter
from .typedefs import ExpressionEvaluatorFunc


def evaluate_local_field(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    current_type_name: str,
    expression: LocalField,
    data_contexts: Iterable[DataContext],
) -> Iterable[Tuple[DataContext, Any]]:
    field_name = expression.field_name
    return adapter.project_property(data_contexts, current_type_name, field_name)


def evaluate_context_field(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    current_type_name: str,
    expression: Union[ContextField, OutputContextField],
    data_contexts: Iterable[DataContext],
) -> Iterable[Tuple[DataContext, Any]]:
    location = expression.location.at_vertex()
    field_name = expression.location.field

    moved_contexts = (
        data_context.get_context_for_location(location).push_value_onto_stack(data_context)
        for data_context in data_contexts
    )

    # TODO(predrag): Current_type_name here is passed incorrectly!
    #                It's the type of the current evaluation scope, whereas it should be
    #                the type of the location from the given context!

    return (
        (moved_data_context.pop_value_from_stack(), value)
        for moved_data_context, value in adapter.project_property(
            moved_contexts, current_type_name, field_name,
        )
    )


def evaluate_context_field_existence(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    current_type_name: str,
    expression: ContextFieldExistence,
    data_contexts: Iterable[DataContext],
) -> Iterable[Tuple[DataContext, Any]]:
    location = expression.location.at_vertex()

    for data_context in data_contexts:
        existence_value = data_context.token_at_location[location] is not None
        yield (data_context, existence_value)


def evaluate_variable(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    current_type_name: str,
    expression: Variable,
    data_contexts: Iterable[DataContext],
) -> Iterable[Tuple[DataContext, Any]]:
    variable_value = query_arguments[expression.variable_name[1:]]
    return (
        (data_context, variable_value)
        for data_context in data_contexts
    )


def evaluate_literal(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_arguments: Dict[str, Any],
    current_type_name: str,
    expression: Literal,
    data_contexts: Iterable[DataContext],
) -> Iterable[Tuple[DataContext, Any]]:
    return (
        (data_context, expression.value)
        for data_context in data_contexts
    )
