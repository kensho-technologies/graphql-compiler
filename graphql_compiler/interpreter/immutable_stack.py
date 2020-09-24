from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class ImmutableStack:
    value: Any
    depth: int
    tail: Optional["ImmutableStack"]

    def push(self, value: Any) -> "ImmutableStack":
        return ImmutableStack(value, self.depth + 1, self)

    def pop(self) -> Tuple[Any, Optional["ImmutableStack"]]:
        return (self.value, self.tail)


def make_empty_stack() -> ImmutableStack:
    return ImmutableStack(None, 0, None)
