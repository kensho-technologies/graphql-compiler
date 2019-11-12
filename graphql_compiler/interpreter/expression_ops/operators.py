from typing import Any


def apply_operator(operator: str, left_value: Any, right_value: Any) -> Any:
    if operator == '=':
        return left_value == right_value
    elif operator == 'contains':
        return right_value in left_value
    else:
        raise NotImplementedError()
