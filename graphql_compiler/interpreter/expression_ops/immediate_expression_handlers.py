from typing import Any, Dict, Iterable, Iterator, Optional, Tuple, Union

from ...compiler.expressions import (
    ContextField,
    ContextFieldExistence,
    Literal,
    LocalField,
    OutputContextField,
    Variable,
)
from ...compiler.helpers import BaseLocation, Location
from ...compiler.metadata import QueryMetadataTable
from ..hinting import get_hints_for_location_via_readthrough_cache
from ..typedefs import DataContext, DataToken, InterpreterAdapter, InterpreterHints
from .typedefs import ExpressionEvaluatorFunc


def evaluate_local_field(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    current_location: Optional[Location],
    expression: LocalField,
    data_contexts: Iterable[DataContext],
) -> Iterator[Tuple[DataContext, Any]]:
    if current_location is None:
        raise AssertionError(
            f"Unexpectedly attempting to evaluate a LocalField while in the global scope "
            f"(current_location is None). This is a bug: {expression}"
        )

    current_type_name = query_metadata_table.get_location_info(current_location).type.name

    hints = get_hints_for_location_via_readthrough_cache(
        query_metadata_table, query_arguments, per_query_hint_cache, current_location
    )

    field_name = expression.field_name
    return iter(adapter.project_property(data_contexts, current_type_name, field_name, **hints))


def evaluate_context_field(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    current_location: Optional[Location],
    expression: Union[ContextField, OutputContextField],
    data_contexts: Iterable[DataContext],
) -> Iterator[Tuple[DataContext, Any]]:
    location = expression.location.at_vertex()
    field_name = expression.location.field

    hints = get_hints_for_location_via_readthrough_cache(
        query_metadata_table, query_arguments, per_query_hint_cache, location
    )

    if field_name is None:
        raise AssertionError(
            f"Unexpectedly attempted to evaluate a context field without a field name, "
            f"this is a bug: {expression}"
        )

    moved_contexts = (
        data_context.get_context_for_location(location).push_value_onto_stack(data_context)
        for data_context in data_contexts
    )

    # The ContextField being evaluated points to a location different than the location of the scope
    # within which it is found. That means the "current_type_name" when evaluating that field may
    # be different than the caller-provided value for "current_type_name". We load the correct value
    # from the query metadata on the basis of the location within the expression.
    context_type_name = query_metadata_table.get_location_info(location).type.name

    return (
        (moved_data_context.pop_value_from_stack(), value)
        for moved_data_context, value in adapter.project_property(
            moved_contexts,
            context_type_name,
            field_name,
            **hints,
        )
    )


def evaluate_context_field_existence(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    current_location: Optional[Location],
    expression: ContextFieldExistence,
    data_contexts: Iterable[DataContext],
) -> Iterator[Tuple[DataContext, Any]]:
    location = expression.location.at_vertex()

    for data_context in data_contexts:
        existence_value = data_context.token_at_location[location] is not None
        yield (data_context, existence_value)


def evaluate_variable(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    current_location: Optional[Location],
    expression: Variable,
    data_contexts: Iterable[DataContext],
) -> Iterator[Tuple[DataContext, Any]]:
    variable_value = query_arguments[expression.variable_name[1:]]
    return ((data_context, variable_value) for data_context in data_contexts)


def evaluate_literal(
    expression_evaluator_func: ExpressionEvaluatorFunc,
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    current_location: Optional[Location],
    expression: Literal,
    data_contexts: Iterable[DataContext],
) -> Iterator[Tuple[DataContext, Any]]:
    return ((data_context, expression.value) for data_context in data_contexts)
