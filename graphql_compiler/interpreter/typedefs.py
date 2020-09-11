from abc import ABCMeta, abstractmethod
from pprint import pformat
from typing import Any, Collection, Dict, Generic, Iterable, List, Optional, Tuple, TypeVar

# TODO(predrag): In 3.8+ these should be imported from typing. Make a shim module.
from typing_extensions import Literal, TypedDict

from ..compiler.helpers import Location
from ..compiler.metadata import FilterInfo
from .immutable_stack import ImmutableStack, make_empty_stack


GLOBAL_LOCATION_TYPE_NAME = "__global__"


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

    # https://github.com/python/mypy/issues/731
    piggyback_contexts: Optional[List["DataContext"]]  # type: ignore

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
        return self.expression_stack.peek()

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
            self.token_at_location[location], dict(self.token_at_location), self.expression_stack,
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


EdgeDirection = Literal["in", "out"]
EdgeInfo = Tuple[EdgeDirection, str]  # direction + edge name

# TODO(predrag): Figure out a better type here. We need to balance between finding something
#                easy and lightweight, and letting the user know about things like:
#                optional edges, recursive edges, used fields/filters at the neighbor, etc.
NeighborHint = Any


class InterpreterHints(TypedDict):
    """Describe all known hint types.

    Values of this type are intended to be used as "**hints" syntax in adapter calls.
    """

    runtime_arg_hints: Dict[str, Any]  # the runtime arguments passed for this query
    used_property_hints: Collection[str]  # the names of all property fields used within this scope
    filter_hints: Collection[FilterInfo]  # info on all filters used within this scope
    neighbor_hints: Collection[Tuple[EdgeInfo, NeighborHint]]  # info on all neighbors of this scope


class InterpreterAdapter(Generic[DataToken], metaclass=ABCMeta):
    @abstractmethod
    def get_tokens_of_type(
        self,
        type_name: str,
        *,
        runtime_arg_hints: Optional[Dict[str, Any]] = None,
        used_property_hints: Optional[Collection[str]] = None,
        filter_hints: Optional[Collection[FilterInfo]] = None,
        neighbor_hints: Optional[Collection[Tuple[EdgeInfo, NeighborHint]]] = None,
        **hints: Any,
    ) -> Iterable[DataToken]:
        pass

    @abstractmethod
    def project_property(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        field_name: str,
        *,
        runtime_arg_hints: Optional[Dict[str, Any]] = None,
        used_property_hints: Optional[Collection[str]] = None,
        filter_hints: Optional[Collection[FilterInfo]] = None,
        neighbor_hints: Optional[Collection[Tuple[EdgeInfo, NeighborHint]]] = None,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], Any]]:
        pass

    @abstractmethod
    def project_neighbors(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        edge_info: EdgeInfo,
        *,
        runtime_arg_hints: Optional[Dict[str, Any]] = None,
        used_property_hints: Optional[Collection[str]] = None,
        filter_hints: Optional[Collection[FilterInfo]] = None,
        neighbor_hints: Optional[Collection[Tuple[EdgeInfo, NeighborHint]]] = None,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], Iterable[DataToken]]]:
        # If using a generator instead of a list for the Iterable[DataToken] part,
        # be careful -- generators are not closures! Make sure any state you pull into
        # the generator from the outside does not change, or that bug will be hard to find.
        # Remember: it's always safer to use a function to produce the generator, since
        # that will explicitly preserve all the external values passed into it.
        pass

    @abstractmethod
    def can_coerce_to_type(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        coerce_to_type_name: str,
        *,
        runtime_arg_hints: Optional[Dict[str, Any]] = None,
        used_property_hints: Optional[Collection[str]] = None,
        filter_hints: Optional[Collection[FilterInfo]] = None,
        neighbor_hints: Optional[Collection[Tuple[EdgeInfo, NeighborHint]]] = None,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], bool]]:
        pass
