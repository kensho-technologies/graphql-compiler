from pprint import pformat
from typing import Any, Dict, Generic, List, Optional, TypeVar

from ..compiler.helpers import Location
from .immutable_stack import ImmutableStack, make_empty_stack


DataToken = TypeVar("DataToken")


class DataContext(Generic[DataToken]):

    __slots__ = (
        "current_token",
        "token_at_location",
        "expression_stack",
        "piggyback_contexts",
    )

    current_token: Optional[DataToken]
    token_at_location: Dict[Location, Optional[DataToken]]
    expression_stack: ImmutableStack
    piggyback_contexts: Optional[List["DataContext"]]

    def __init__(
        self,
        current_token: Optional[DataToken],
        token_at_location: Dict[Location, Optional[DataToken]],
        expression_stack: ImmutableStack,
    ) -> None:
        self.current_token = current_token
        self.token_at_location = token_at_location
        self.expression_stack = expression_stack
        self.piggyback_contexts = None

    def __repr__(self) -> str:
        return (
            f"DataContext(current={self.current_token}, "
            f"locations={pformat(self.token_at_location)}, "
            f"stack={pformat(self.expression_stack)}, "
            f"piggyback={self.piggyback_contexts})"
        )

    __str__ = __repr__

    @staticmethod
    def make_empty_context_from_token(token: DataToken) -> "DataContext":
        return DataContext(token, dict(), make_empty_stack())

    def push_value_onto_stack(self, value: Any) -> "DataContext":
        self.expression_stack = self.expression_stack.push(value)
        return self  # for chaining

    def peek_value_on_stack(self) -> Any:
        return self.expression_stack.value

    def pop_value_from_stack(self) -> Any:
        value, remaining_stack = self.expression_stack.pop()
        if remaining_stack is None:
            raise AssertionError(
                'We always start the stack with a "None" element pushed on, but '
                "that element somehow got popped off. This is a bug."
            )
        self.expression_stack = remaining_stack
        return value

    def get_context_for_location(self, location: Location) -> "DataContext":
        return DataContext(
            self.token_at_location[location],
            dict(self.token_at_location),
            self.expression_stack,
        )

    def add_piggyback_context(self, piggyback: "DataContext") -> None:
        # First, move any nested piggyback contexts to this context's piggyback list
        nested_piggyback_contexts = piggyback.consume_piggyback_contexts()

        if self.piggyback_contexts:
            self.piggyback_contexts.extend(nested_piggyback_contexts)
        else:
            self.piggyback_contexts = nested_piggyback_contexts

        # Then, append the new piggyback element to our own piggyback contexts.
        self.piggyback_contexts.append(piggyback)

    def consume_piggyback_contexts(self) -> List["DataContext"]:
        piggybacks = self.piggyback_contexts
        if piggybacks is None:
            return []

        self.piggyback_contexts = None
        return piggybacks

    def ensure_deactivated(self) -> None:
        if self.current_token is not None:
            self.push_value_onto_stack(self.current_token)
            self.current_token = None

    def reactivate(self) -> None:
        if self.current_token is not None:
            raise AssertionError(f"Attempting to reactivate an already-active context: {self}")
        self.current_token = self.pop_value_from_stack()
