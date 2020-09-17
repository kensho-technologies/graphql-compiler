from typing import Any, Callable, Optional


# Define the various operators' behavior for values other than None.
# The behavior with respect to None is defined explicitly in the "apply_operator()" function.
_operator_definitions_for_non_null_values = {
    "=": lambda left, right: left == right,
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    "!=": lambda left, right: left != right,
    "contains": lambda left, right: right in left,
    "not_contains": lambda left, right: right not in left,
    "has_substring": lambda left, right: right in left,
    "starts_with": lambda left, right: left.startswith(right),
    "ends_with": lambda left, right: left.endswith(right),
    "in_collection": lambda left, right: left in right,
    "&&": lambda left, right: left and right,
    "||": lambda left, right: left or right,
}


def apply_operator(operator: str, left_value: Any, right_value: Any) -> Any:
    # SQL-like semantics: comparisons with "None" generally produce False unless comparing to None:
    # - None is equal to None
    # - None != <anything other than None> is True
    # - None is not greater than, nor less than, any other value
    # - None contains nothing and is never contained in anything
    # - None starts/ends with nothing, and nothing starts or ends with None
    #
    # TODO(predrag): Implement the "filtering with non-existing tag from optional scope passes" rule
    #                See matching TODO note in the handling of Filter IR blocks.
    left_none = left_value is None
    right_none = right_value is None

    if left_none and right_none:
        if operator in {"=", ">=", "<="}:
            # The operation simplifies to None = None, which we define as True.
            return True
        elif operator == "!=":
            # We have None != None, which is False.
            return False
        else:
            # All other comparisons vs None produce False.
            return False
    elif left_none or right_none:
        # Only one of the values is None. We define this to always be False, for all operators.
        return False
    elif not left_none and not right_none:
        # Neither side of the operator is None, apply operator normally.
        operator_handler: Optional[
            Callable[[Any, Any], Any]
        ] = _operator_definitions_for_non_null_values.get(operator, None)
        if operator_handler is not None:
            return operator_handler(left_value, right_value)
        else:
            raise NotImplementedError(f"Operator {operator} is not currently implemented.")

    raise AssertionError(
        f"Unreachable code reached: (left operator right) "
        f"was ({left_value} {operator} {right_value})"
    )
