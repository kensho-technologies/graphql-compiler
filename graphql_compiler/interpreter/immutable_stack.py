from typing import Any, NamedTuple, Optional, Tuple


class ImmutableStack(NamedTuple):
    value: Any
    depth: int
    tail: Optional['ImmutableStack']

    def peek(self) -> Any:
        return self.value

    def push(self, value: Any):
        return ImmutableStack(value, self.depth + 1, self)

    def pop(self) -> Tuple[Any, 'ImmutableStack']:
        return (self.value, self.tail)


def make_empty_stack():
    return ImmutableStack(None, 0, None)
