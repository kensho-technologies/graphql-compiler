from typing import Any


def apply_operator(operator: str, left_value: Any, right_value: Any) -> Any:
    if operator == '=':
        return left_value == right_value
    elif operator == '>=':
        return left_value >= right_value
    elif operator == 'contains':
        return right_value in left_value
    elif operator == 'not_contains':
        return right_value not in left_value
    elif operator == 'starts_with':
        return left_value.startswith(right_value)
    elif operator == 'ends_with':
        return left_value.endswith(right_value)
    else:
        raise NotImplementedError()
