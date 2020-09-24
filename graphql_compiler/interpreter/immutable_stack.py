# Copyright 2020-present Kensho Technologies, LLC.
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True, init=False)
class ImmutableStack:
    """An immutable stack of arbitrary (heterogeneously-typed) values.

    Specifically designed for cheap structural sharing, in order to avoid deep copies or
    bugs caused by mutations of shared data.
    """

    __slots__ = ("value", "depth", "tail")

    # The following attributes are considered visible and safe for direct external use.
    #
    # N.B.: Keep "depth" defined before "tail"! The default "==" implementation for dataclasses
    #       compares instances as if they were tuples with their attribute values in the order in
    #       which they were declared. The "depth" is much cheaper to check for equality, so it must
    #       be checked first.
    value: Any  # The value contained within this stack node.
    depth: int  # The number of stack nodes contained in the tail of the stack.
    tail: Optional["ImmutableStack"]  # The node that represents the rest of the stack, if any.

    def __init__(self, value: Any, tail: Optional["ImmutableStack"]) -> None:
        """Initialize the ImmutableStack."""
        # Per the docs, frozen dataclasses use object.__setattr__() to write their attributes.
        # We have to do that too since we are dynamically setting the "depth" attribute.
        # Docs link: https://docs.python.org/3/library/dataclasses.html#frozen-instances
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "tail", tail)

        depth = 0 if tail is None else tail.depth + 1
        object.__setattr__(self, "depth", depth)

    def __copy__(self) -> "ImmutableStack":
        """Produce a shallow copy of the ImmutableStack. Required because depth is not settable."""
        return ImmutableStack(self.value, self.tail)

    def __deepcopy__(self, memo: Optional[Dict[int, Any]]) -> "ImmutableStack":
        """Produce a deep copy of the ImmutableStack. Required because depth is not settable."""
        # ImmutableStack objects cannot have reference cycles among each other,
        # so we don't need to check the memo dict or write to it.
        value_copy = deepcopy(self.value, memo)
        tail_copy = deepcopy(self.tail, memo)
        return ImmutableStack(value_copy, tail_copy)

    def push(self, value: Any) -> "ImmutableStack":
        """Create a new ImmutableStack with the given value at its top."""
        return ImmutableStack(value, self)

    def pop(self) -> Tuple[Any, Optional["ImmutableStack"]]:
        """Return a tuple with the topmost value and a node for the rest of the stack, if any."""
        return (self.value, self.tail)


def make_empty_stack() -> ImmutableStack:
    """Create a new empty stack, with initial value None at its bottom level.

    Using an explicit None at the bottom of the stack allows us to eliminate some None checks, since
    pushing N elements, then popping N elements still leaves us with an ImmutableStack instance as
    the tail (remainder) of the stack, instead of the None tail we'd get otherwise.
    """
    return ImmutableStack(None, None)
