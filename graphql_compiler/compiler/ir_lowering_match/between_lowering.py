# Copyright 2018-present Kensho Technologies, LLC.
from collections import deque
from typing import Deque, Dict, Iterable, List, Tuple

from graphql import GraphQLOutputType

from ..blocks import Filter
from ..compiler_entities import Expression
from ..expressions import BinaryComposition, LocalField
from ..match_query import MatchQuery, MatchStep
from .utils import BetweenClause, expression_list_to_conjunction


def _extract_conjuction_elements_from_expression(expression: Expression) -> Iterable[Expression]:
    """Return a generator for expressions that are connected by `&&`s in the given expression."""
    if isinstance(expression, BinaryComposition) and expression.operator == "&&":
        for element in _extract_conjuction_elements_from_expression(expression.left):
            yield element
        for element in _extract_conjuction_elements_from_expression(expression.right):
            yield element
    else:
        yield expression


def _construct_field_operator_expression_dict(
    expression_list: List[Expression],
) -> Tuple[
    Dict[str, Dict[str, List[BinaryComposition]]],
    Dict[str, GraphQLOutputType],
    Deque[Expression],
]:
    """Construct a mapping from local fields to specified operators, and corresponding expressions.

    Args:
        expression_list: list of expressions to analyze

    Returns:
        tuple (field_name_to_expressions, field_name_to_type, remaining_expression_deque) containing
        - field_name_to_expressions:
            dict mapping local field names to "operator -> list of BinaryComposition" dictionaries,
            for each BinaryComposition operator involving the LocalField
        - field_name_to_type:
            dict mapping local field names to field type
        - remaining_expression_deque:
            deque of remaining expressions that were *not*
            BinaryCompositions on a LocalField using any of the between operators
    """
    between_operators = ("<=", ">=")
    inverse_operator = {">=": "<=", "<=": ">="}
    field_name_to_expressions: Dict[str, Dict[str, List[BinaryComposition]]] = {}
    field_name_to_type: Dict[str, GraphQLOutputType] = {}
    remaining_expression_deque: Deque[Expression] = deque([])

    for expression in expression_list:
        if (
            isinstance(expression, BinaryComposition)
            and expression.operator in between_operators
            and (
                isinstance(expression.left, LocalField) or isinstance(expression.right, LocalField)
            )
        ):
            # Ensure we rewrite the BinaryComposition in such a way that the left expression
            # is always a LocalField.
            if isinstance(expression.right, LocalField):
                new_operator = inverse_operator[expression.operator]
                new_expression = BinaryComposition(new_operator, expression.right, expression.left)
            else:
                new_expression = expression

            left_clause = new_expression.left
            if not isinstance(left_clause, LocalField):
                raise AssertionError(
                    f"Expected left_clause to be a LocalField, but instead found {left_clause}. "
                    f"This is a bug."
                )

            field_name = left_clause.field_name
            field_type = left_clause.field_type
            if field_type is None:
                raise AssertionError(
                    f"Unexpectedly encountered untyped clause while performing BETWEEN lowering, "
                    f"this is a bug: {left_clause}"
                )

            field_name_to_type[field_name] = field_type
            expressions_dict = field_name_to_expressions.setdefault(field_name, {})
            expressions_dict.setdefault(new_expression.operator, []).append(new_expression)
        else:
            remaining_expression_deque.append(expression)

    return field_name_to_expressions, field_name_to_type, remaining_expression_deque


def _lower_expressions_to_between(base_expression: Expression) -> Expression:
    """Return a new expression, with any eligible comparisons lowered to `between` clauses."""
    expression_list = list(_extract_conjuction_elements_from_expression(base_expression))
    if len(expression_list) == 0:
        raise AssertionError(
            "Received empty expression_list {} from base_expression: "
            "{}".format(expression_list, base_expression)
        )
    elif len(expression_list) == 1:
        return base_expression
    else:
        between_operators = ("<=", ">=")
        (
            field_name_to_expressions,
            field_name_to_type,
            new_expression_deque,
        ) = _construct_field_operator_expression_dict(expression_list)

        lowering_occurred = False
        for field_name in field_name_to_expressions:
            expressions_dict = field_name_to_expressions[field_name]
            if all(
                operator in expressions_dict and len(expressions_dict[operator]) == 1
                for operator in between_operators
            ):
                field = LocalField(field_name, field_name_to_type[field_name])
                lower_bound = expressions_dict[">="][0].right
                upper_bound = expressions_dict["<="][0].right
                new_expression_deque.appendleft(BetweenClause(field, lower_bound, upper_bound))
                lowering_occurred = True
            else:
                for expression in expressions_dict.values():
                    new_expression_deque.extend(expression)

        if lowering_occurred:
            return expression_list_to_conjunction(list(new_expression_deque))
        else:
            return base_expression


def lower_comparisons_to_between(match_query: MatchQuery) -> MatchQuery:
    """Return a new MatchQuery, with all eligible comparison filters lowered to between clauses."""
    new_match_traversals: List[List[MatchStep]] = []

    for current_match_traversal in match_query.match_traversals:
        new_traversal: List[MatchStep] = []
        for step in current_match_traversal:
            if step.where_block:
                expression = step.where_block.predicate
                new_where_block = Filter(_lower_expressions_to_between(expression))
                new_traversal.append(step._replace(where_block=new_where_block))
            else:
                new_traversal.append(step)

        new_match_traversals.append(new_traversal)

    return match_query._replace(match_traversals=new_match_traversals)
