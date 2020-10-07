from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Generic, Iterable, List, Sequence, Tuple, TypeVar

from ..typedefs import Literal
from .typedefs import DataToken


T = TypeVar("T")
U = TypeVar("U")


def _enumerate_starting_at(
    sequence: Sequence[T],
    first_index: int,
) -> Iterable[Tuple[int, T]]:
    """Enumerate only a portion of a sequence, without slicing the sequence.

    Equivalent to enumerate(sequence[first_index:], start=first_index). The built-in enumerate()
    always iterates the entire sequence and only changes the counter's value based on
    the start parameter. In this function, we skip elements with indices in [0, first_index)
    in the sequence, and only iterate over elements with indices in [first_index, len(sequence)).

    Args:
        sequence: arbitrary sequence of values over which to iterate
        first_index: the first index of the sequence to produce in the resulting iterable

    Yields:
        tuples (index, element_at_that_index_in_sequence), analogous to the built-in enumerate()
    """
    for index in range(first_index, len(sequence)):
        yield index, sequence[index]


def _unzip_and_yield_second(iterable: Iterable[Tuple[T, U]]) -> Iterable[U]:
    """Unpack an iterable of tuples and only yield the second element of each tuple."""
    for _, second in iterable:
        yield second


@dataclass(frozen=True)
class AdapterOperation:
    """The record of an action performed to or by an InterpreterAdapter function as part of a trace.

    For example, calling get_tokens_of_type("Foo") would be an AdapterOperation with kind "call",
    with name "get_tokens_of_type", with unique ID and parent unique IDs appropriate for the trace,
    and with data (("Foo",), {}) as the tuple of the positional arguments tuple and kwargs dict.

    The parent_uid field allows us to track dependencies across different operations. For example,
    data yielded by a call to a generator-style function will be recorded in AdapterOperations
    with kind "yield" whose parent_uid points to the AdapterOperation of the particular invocation
    of the function that is yielding that data.
    """

    kind: Literal["call", "yield", "return"]
    name: str
    uid: int
    parent_uid: int
    data: Any


@dataclass(frozen=True)
class RecordedTrace(Generic[DataToken]):
    """A complete immutable recording of the execution of a query via an InterpreterAdapter.

    Includes a linearized sequence of all operations performed during the execution of the query:
    - adapter function calls, yields, and returns;
    - actuation of all input and output iterables.

    Traces may record complete executions of queries (i.e. ones where the generators are run
    to completion), and may also be used to record partial executions (e.g. "fetch only 3 results").

    The recording is sufficiently detailed to be used in at least the following use cases:
    - to examine, either manually or through automated tests, a query's execution flow;
    - to "impersonate" an InterpreterAdapter implementation for a given query, allowing bugs in
      the interpreter library code to be isolated and reproduced without an InterpreterAdapter;
    - to "impersonate" the interpreter library code toward an InterpreterAdapter implementation,
      allowing adapter implementers to test and examine their implementations in isolation from
      the rest of the interpreter library code.
    """

    DEFAULT_ROOT_UID: ClassVar[int] = -1

    # AdapterOperations that are part of this trace but do not have a specific parent operation
    # instead get assigned the trace's root_uid value as their parent_uid value.
    root_uid: int = field(init=False, default=DEFAULT_ROOT_UID)
    operations: Tuple[AdapterOperation, ...]


class TraceRecorder(Generic[DataToken]):

    # We expose an immutable (copied) version of the operation log through get_trace().
    # Other attributes are considered public.
    _operation_log: List[AdapterOperation]
    root_uid: int

    def __init__(self) -> None:
        """Initialize the TraceRecorder."""
        self._operation_log = []
        self.root_uid = RecordedTrace[DataToken].DEFAULT_ROOT_UID

    def record_call(
        self,
        operation_name: str,
        parent_uid: int,
        call_args: Tuple[Any, ...],
        call_kwargs: Dict[str, Any],
    ) -> int:
        """Record that a call of the specified function has occurred with the given arguments."""
        uid = len(self._operation_log)
        call_args = deepcopy(call_args)
        call_kwargs = deepcopy(call_kwargs)
        self._operation_log.append(
            AdapterOperation("call", operation_name, uid, parent_uid, (call_args, call_kwargs))
        )
        return uid

    def record_iterable(
        self, operation_name: str, parent_uid: int, iterable: Iterable[T]
    ) -> Iterable[Tuple[int, T]]:
        """Record each data item in the given iterable as a yield with the provided metadata.

        Args:
            operation_name: name to associate with this operation; usually the name of the function
                            whose iterable output is being recorded.
            parent_uid: unique identifier of the parent operation of this operation.
            iterable: iterable to record

        Yields:
            for each piece of data yielded by the input iterable, yields a tuple of the
            operation's unique identifier for that data together with the data itself
        """
        for item in iterable:
            item_uid = len(self._operation_log)
            self._operation_log.append(
                AdapterOperation("yield", operation_name, item_uid, parent_uid, deepcopy(item))
            )
            yield item_uid, item

    def record_compound_iterable(
        self,
        operation_name: str,
        parent_uid: int,
        compound_iterable: Iterable[Tuple[U, Iterable[T]]],
    ) -> Iterable[Tuple[int, Tuple[U, Iterable[T]]]]:
        """Record all yields for the given iterable-of-iterables.

        This function is similar to record_iterable() above, but adapted to the needs of
        the InterpreterAdapter's project_neighbors() function, which yields iterables that
        themselves contain iterables. In that case, making an accurate record of the order of
        all yields is a tricky process: the outer iterable and any of the produced inner iterables
        may be actuated with few limitations (essentially just "can't iterate inner iterables that
        haven't been yielded yet").

        This function tracks all yields of the outer iterable, and uses self.record_iterable() to
        track the yields for each produced inner iterable.

        Args:
            operation_name: name to associate with this operation; usually the name of the function
                            whose compound iterable output is being recorded.
            parent_uid: unique identifier of the parent operation of this operation.
            compound_iterable: iterable to record

        Yields:
            for each piece of data yielded by the input compound_iterable, yields a tuple of the
            operation's unique identifier for that data together with the data itself
        """
        for item_index, item in enumerate(compound_iterable):
            item_uid = len(self._operation_log)
            iterable_name = f"__output_iterable_{item_index}"
            non_iterable_data, iterable_data = item
            non_iterable_data = deepcopy(non_iterable_data)

            operation_data = (non_iterable_data, iterable_name)
            self._operation_log.append(
                AdapterOperation("yield", operation_name, item_uid, parent_uid, operation_data)
            )

            inner_iterable = _unzip_and_yield_second(
                self.record_iterable(iterable_name, item_uid, iterable_data)
            )
            yield item_uid, (non_iterable_data, inner_iterable)

    def get_trace(self) -> RecordedTrace[DataToken]:
        """Create an immutable trace with all the activity up to this point."""
        return RecordedTrace(tuple(self._operation_log))
