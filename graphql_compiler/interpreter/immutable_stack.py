# Copyright 2020-present Kensho Technologies, LLC.
from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class ImmutableStack:
    """An immutable stack of arbitrary (heterogeneously-typed) values.

    Specifically designed for cheap structural sharing, in order to avoid deep copies or
    bugs caused by mutations of shared data.
    """

    # The following attributes are considered visible and safe for direct external use.
    value: Any  # The value contained within this stack node.
    depth: int  # The number of stack nodes contained in the tail of the stack.
    tail: Optional["ImmutableStack"]  # The node that represents the rest of the stack, if any.

    def push(self, value: Any) -> "ImmutableStack":
        """Create a new ImmutableStack with the given value at its top."""
        return ImmutableStack(value, self.depth + 1, self)

    def pop(self) -> Tuple[Any, Optional["ImmutableStack"]]:
        """Return a tuple with the topmost value and a node for the rest of the stack, if any."""
        return (self.value, self.tail)


def make_empty_stack() -> ImmutableStack:
    """Create a new empty stack, with initial value None at its bottom level.

    Using an explicit None at the bottom of the stack allows us to eliminate some None checks, since
    pushing N elements, then popping N elements still leaves us with an ImmutableStack instance as
    the tail (remainder) of the stack, instead of the None tail we'd get otherwise.
    """
    return ImmutableStack(None, 0, None)
