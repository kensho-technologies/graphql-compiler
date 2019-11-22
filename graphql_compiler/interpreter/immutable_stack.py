from typing import Any, NamedTuple, Optional, Tuple


class ImmutableStack(NamedTuple):
    value: Any
    depth: int
    tail: Optional['ImmutableStack']  # type: ignore # https://github.com/python/mypy/issues/731

    def peek(self) -> Any:
        return self.value

    def push(self, value: Any) -> 'ImmutableStack':
        return ImmutableStack(value, self.depth + 1, self)

    def pop(self) -> Tuple[Any, Optional['ImmutableStack']]:
        return (self.value, self.tail)


def make_empty_stack() -> ImmutableStack:
    return ImmutableStack(None, 0, None)
