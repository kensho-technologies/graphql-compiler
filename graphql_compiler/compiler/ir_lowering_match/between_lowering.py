# Copyright 2018-present Kensho Technologies, LLC.
from collections import deque

from ..blocks import Filter
from ..expressions import BinaryComposition, LocalField
from .utils import BetweenClause


def _expression_list_to_conjunction(expression_list):
    """Return an Expression that is the `&&` of all the expressions in the given list."""
    if not isinstance(expression_list, list):
        raise AssertionError(u'Expected list. Received {}: '
                             u'{}'.format(type(expression_list).__name__, expression_list))
    if len(expression_list) == 0:
        raise AssertionError(u'Received empty expression_list '
                             u'(function should never be called with empty list): '
                             u'{}'.format(expression_list))
    elif len(expression_list) == 1:
        return expression_list[0]
    else:
        remaining_conjunction = _expression_list_to_conjunction(expression_list[1:])
        return BinaryComposition(u'&&', expression_list[0], remaining_conjunction)


def _extract_conjuction_elements_from_expression(expression):
    """Return a generator for expressions that are connected by `&&`s in the given expression."""
    if isinstance(expression, BinaryComposition) and expression.operator == u'&&':
        for element in _extract_conjuction_elements_from_expression(expression.left):
            yield element
        for element in _extract_conjuction_elements_from_expression(expression.right):
            yield element
    else:
        yield expression


def _construct_field_operator_expression_dict(expression_list):
    """Construct a mapping from local fields to specified operators, and corresponding expressions.

    Args:
        expression_list: list of expressions to analyze

    Returns:
        local_field_to_expressions:
            dict mapping local field names to "operator -> list of BinaryComposition" dictionaries,
            for each BinaryComposition operator involving the LocalField
        remaining_expression_list:
            list of remaining expressions that were *not*
            BinaryCompositions on a LocalField using any of the between operators
    """
    between_operators = (u'<=', u'>=')
    inverse_operator = {u'>=': u'<=', u'<=': u'>='}
    local_field_to_expressions = {}
    remaining_expression_list = deque([])
    for expression in expression_list:
        if all((
            isinstance(expression, BinaryComposition),
            expression.operator in between_operators,
            isinstance(expression.left, LocalField) or isinstance(expression.right, LocalField)
        )):
            if isinstance(expression.right, LocalField):
                new_operator = inverse_operator[expression.operator]
                new_expression = BinaryComposition(new_operator, expression.right, expression.left)
            else:
                new_expression = expression
            field_name = new_expression.left.field_name
            expressions_dict = local_field_to_expressions.setdefault(field_name, {})
            expressions_dict.setdefault(new_expression.operator, []).append(new_expression)
        else:
            remaining_expression_list.append(expression)
    return local_field_to_expressions, remaining_expression_list


def _lower_expressions_to_between(base_expression):
    """Return a new expression, with any eligible comparisons lowered to `between` clauses."""
    expression_list = list(_extract_conjuction_elements_from_expression(base_expression))
    if len(expression_list) == 0:
        raise AssertionError(u'Received empty expression_list {} from base_expression: '
                             u'{}'.format(expression_list, base_expression))
    elif len(expression_list) == 1:
        return base_expression
    else:
        between_operators = (u'<=', u'>=')
        local_field_to_expressions, new_expression_list = _construct_field_operator_expression_dict(
            expression_list)

        lowering_occurred = False
        for field_name in local_field_to_expressions:
            expressions_dict = local_field_to_expressions[field_name]
            if all(operator in expressions_dict and len(expressions_dict[operator]) == 1
                   for operator in between_operators):
                field = LocalField(field_name)
                lower_bound = expressions_dict[u'>='][0].right
                upper_bound = expressions_dict[u'<='][0].right
                new_expression_list.appendleft(BetweenClause(field, lower_bound, upper_bound))
                lowering_occurred = True
            else:
                for expression in expressions_dict.values():
                    new_expression_list.extend(expression)

        if lowering_occurred:
            return _expression_list_to_conjunction(list(new_expression_list))
        else:
            return base_expression


def lower_comparisons_to_between(match_query):
    """Return a new MatchQuery, with all eligible comparison filters lowered to between clauses."""
    new_match_traversals = []

    for current_match_traversal in match_query.match_traversals:
        new_traversal = []
        for step in current_match_traversal:
            if step.where_block:
                expression = step.where_block.predicate
                new_where_block = Filter(_lower_expressions_to_between(expression))
                new_traversal.append(step._replace(where_block=new_where_block))
            else:
                new_traversal.append(step)

        new_match_traversals.append(new_traversal)

    return match_query._replace(match_traversals=new_match_traversals)
