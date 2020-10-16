from typing import Any, Dict, Iterable, Iterator, Optional, Tuple

from ...compiler.expressions import (
    BinaryComposition,
    ContextField,
    ContextFieldExistence,
    Expression,
    Literal,
    LocalField,
    OutputContextField,
    TernaryConditional,
    Variable,
)
from ...compiler.helpers import BaseLocation, Location
from ...compiler.metadata import QueryMetadataTable
from ..typedefs import DataContext, DataToken, InterpreterAdapter, InterpreterHints
from .composition_expression_handlers import (
    evaluate_binary_composition,
    evaluate_ternary_conditional,
)
from .immediate_expression_handlers import (
    evaluate_context_field,
    evaluate_context_field_existence,
    evaluate_literal,
    evaluate_local_field,
    evaluate_variable,
)


def evaluate_expression(
    adapter: InterpreterAdapter[DataToken],
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    current_location: Optional[Location],
    expression: Expression,
    data_contexts: Iterable[DataContext],
) -> Iterator[Tuple[DataContext, Any]]:
    type_to_handler = {
        BinaryComposition: evaluate_binary_composition,
        TernaryConditional: evaluate_ternary_conditional,
        LocalField: evaluate_local_field,
        ContextFieldExistence: evaluate_context_field_existence,
        Variable: evaluate_variable,
        Literal: evaluate_literal,
        # These two are intentionally using the same handler, no difference in their semantics here.
        ContextField: evaluate_context_field,
        OutputContextField: evaluate_context_field,
    }
    handler = type_to_handler[type(expression)]

    # N.B.: We pass "evaluate_expression" (i.e. this dispatch function) into
    #       the specific expression handler since some expressions contain nested sub-expressions.
    #       If we hadn't passed in this function as an argument, we'd have a circular import issue.
    return handler(
        evaluate_expression,
        adapter,
        query_metadata_table,
        query_arguments,
        per_query_hint_cache,
        current_location,
        expression,
        data_contexts,
    )
