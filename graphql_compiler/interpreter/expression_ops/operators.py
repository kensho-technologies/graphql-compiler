from typing import Any


def apply_operator(operator: str, left_value: Any, right_value: Any) -> Any:
    if operator == '=':
        if right_value is None:
            return left_value is None
        else:
            return left_value == right_value
    elif operator == '!=':
        if right_value is None:
            return left_value is not None
        else:
            return left_value != right_value
    elif operator == '>=':
        return left_value >= right_value
    elif operator == 'contains' or operator == 'has_substring':
        return left_value is not None and right_value in left_value
    elif operator == 'not_contains':
        return left_value is not None and right_value not in left_value
    elif operator == 'starts_with':
        return left_value is not None and left_value.startswith(right_value)
    elif operator == 'ends_with':
        return left_value is not None and left_value.endswith(right_value)
    else:
        raise NotImplementedError()
