from abc import ABCMeta, abstractmethod
from pprint import pformat
from typing import Any, Dict, Generic, Iterable, Optional, Tuple, TypeVar

from ..compiler.utils import Location
from .immutable_stack import ImmutableStack, make_empty_stack


DataToken = TypeVar('DataToken')


class DataContext(Generic[DataToken]):

    __slots__ = (
        'current_token',
        'token_at_location',
        'expression_stack',
    )

    def __init__(
        self,
        current_token: Optional[DataToken],
        token_at_location: Dict[Location, Optional[DataToken]],
        expression_stack: ImmutableStack,
    ) -> None:
        self.current_token = current_token
        self.token_at_location = token_at_location
        self.expression_stack = expression_stack

    def __repr__(self) -> str:
        return 'DataContext(current={}, locations={}, stack={})'.format(
            self.current_token, pformat(self.token_at_location), pformat(self.expression_stack))

    __str__ = __repr__

    @staticmethod
    def make_empty_context_from_token(token: DataToken) -> 'DataContext':
        return DataContext(token, dict(), make_empty_stack())

    def push_value_onto_stack(self, value: Any) -> 'DataContext':
        self.expression_stack = self.expression_stack.push(value)
        return self  # for chaining

    def peek_value_on_stack(self) -> Any:
        return self.expression_stack.peek()

    def pop_value_from_stack(self) -> Any:
        value, remaining_stack = self.expression_stack.pop()
        if remaining_stack is None:
            raise AssertionError('We always start the stack with a "None" element pushed on, but '
                                 'that element somehow got popped off. This is a bug.')
        self.expression_stack = remaining_stack
        return value

    def get_context_for_location(self, location: Location) -> 'DataContext':
        return DataContext(
            self.token_at_location[location],
            dict(self.token_at_location),
            self.expression_stack,
        )


class InterpreterAdapter(Generic[DataToken], metaclass=ABCMeta):
    @abstractmethod
    def get_tokens_of_type(
        self,
        type_name: str,
        **hints: Dict[str, Any],
    ) -> Iterable[DataToken]:
        pass

    @abstractmethod
    def project_property(
        self,
        data_contexts: Iterable[DataContext],
        field_name: str,
        **hints: Dict[str, Any],
    ) -> Iterable[Tuple[DataContext, Any]]:
        pass

    @abstractmethod
    def project_neighbors(
        self,
        data_contexts: Iterable[DataContext],
        direction: str,
        edge_name: str,
        **hints: Dict[str, Any],
    ) -> Iterable[Tuple[DataContext, Iterable[DataToken]]]:
        # If using a generator instead of a list for the Iterable[DataToken] part,
        # be careful -- generators are not closures! Make sure any state you pull into
        # the generator from the outside does not change, or that bug will be hard to find.
        # Remember: it's always safer to use a function to produce the generator, since
        # that will explicitly preserve all the external values passed into it.
        pass

    @abstractmethod
    def can_coerce_to_type(
        self,
        data_contexts: Iterable[DataContext],
        type_name: str,
        **hints: Dict[str, Any],
    ) -> Iterable[Tuple[DataContext, bool]]:
        pass
