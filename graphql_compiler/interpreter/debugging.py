# Copyright 2020-present Kensho Technologies, LLC.
from copy import deepcopy
from dataclasses import dataclass, field
from typing import (
    Any,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    cast,
)

from ..typedefs import Literal
from .typedefs import DataContext, DataToken, EdgeInfo, InterpreterAdapter


def print_tap(info: str, data_contexts: Iterable[DataContext]) -> Iterator[DataContext]:
    # TODO(predrag): Debug-only code. Remove before merging.
    return iter(data_contexts)


#     print('\n')
#     unique_id = hash(info)
#     print(unique_id, info)
#     from funcy.py3 import chunks
#     for context_chunk in chunks(100, data_contexts):
#         for context in context_chunk:
#             pprint((unique_id, context))
#             yield context


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
    """The record of an action performed on or by an InterpreterAdapter function as part of a trace.

    Actions that can be recorded like this include function calls, function returns, function yields
    (including yields that contain nested generators, whose yields will also be recorded),
    and yields of generators that were passed as inputs to function calls. The kind of action being
    recorded is reflected in the kind attribute, and carries a value suitable to the kind of action
    in the data attribute.

    For example, calling get_tokens_of_type("Foo") would produce an AdapterOperation
    with kind "call", with name "get_tokens_of_type", with unique ID and parent unique IDs
    appropriate for the trace, and with data (("Foo",), {}) representing a (positional_args, kwargs)
    tuple for the function call. For function returns, the data attribute of AdapterOperation
    holds the value returned by the function. For yields of input or output generators, the content
    of the data attribute is determined by the specific circumstances of the function named in
    the name attribute -- e.g. whether the function outputs a generator of generators, etc.

    The parent_uid field allows us to track dependencies across different operations. For example,
    data yielded by a generator-style function will be recorded in AdapterOperations
    of kind "yield" whose parent_uids point to the AdapterOperation of the particular invocation
    of the function that is generating that data.

    When InterpreterAdapter functions consume iterable arguments, the iterable argument in
    the AdapterOperation "call" record is replaced by a placeholder name. As values from such
    an iterable are consumed, those values are recorded in their own AdapterOperation records
    with kind "yield", parent unique ID matching the unique ID of the "call" record, and
    name matching the placeholder name in the "call" record.
    """

    kind: Literal["call", "yield", "return"]
    name: str
    uid: int
    parent_uid: int
    data: Any


@dataclass(frozen=True)
class RecordedTrace(Generic[DataToken]):
    """A complete, immutable recording of the execution of a query via an InterpreterAdapter.

    Includes a linearized sequence of all operations performed during the execution of the query:
    - adapter function calls, yields, and returns;
    - yields of any iterables that were passed as inputs to the adapter functions.

    Traces may record complete executions of queries (i.e. ones where the generators are run
    to completion), and may also be used to record partial executions (e.g. "fetch only 3 results").

    The recording is sufficiently detailed to be used in at least the following use cases:
    - to examine, either manually or through automated tests, a query's execution flow;
    - to "impersonate" an InterpreterAdapter implementation for a given query, allowing bugs in
      the interpreter code to be isolated and reproduced without an InterpreterAdapter;
    - to "impersonate" the interpreter code toward an InterpreterAdapter implementation,
      allowing adapter implementers to test and examine their implementations in isolation from
      the rest of the interpreter code.
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
            for each piece of data yielded by the input iterable, yields a tuple of:
            - the operation's unique identifier for the yielded data, and
            - the input iterable's yielded data itself.
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
            for each piece of data yielded by the input compound_iterable, yields a tuple of:
            - the operation's unique identifier for the yielded data, and
            - the input compound_iterable's yielded data itself.
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


class InterpreterAdapterTap(InterpreterAdapter[DataToken], Generic[DataToken]):
    inner_adapter: InterpreterAdapter[DataToken]
    recorder: TraceRecorder[DataToken]

    INPUT_ITERABLE_NAME: ClassVar[str] = "__input_iterable"

    def __init__(self, inner_adapter: InterpreterAdapter[DataToken]) -> None:
        self.inner_adapter = inner_adapter
        self.recorder = TraceRecorder()

    def get_tokens_of_type(
        self,
        type_name: str,
        **hints: Any,
    ) -> Iterable[DataToken]:
        operation_name = "get_tokens_of_type"
        call_uid = self.recorder.record_call(
            operation_name, self.recorder.root_uid, (type_name,), hints
        )
        return _unzip_and_yield_second(
            self.recorder.record_iterable(
                operation_name,
                call_uid,
                self.inner_adapter.get_tokens_of_type(type_name, **hints),
            )
        )

    def project_property(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        field_name: str,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], Any]]:
        operation_name = "project_property"
        input_iterable_name = InterpreterAdapterTap.INPUT_ITERABLE_NAME
        call_uid = self.recorder.record_call(
            operation_name,
            self.recorder.root_uid,
            (input_iterable_name, current_type_name, field_name),
            hints,
        )
        wrapped_data_contexts = _unzip_and_yield_second(
            self.recorder.record_iterable(input_iterable_name, call_uid, data_contexts)
        )
        return _unzip_and_yield_second(
            self.recorder.record_iterable(
                operation_name,
                call_uid,
                self.inner_adapter.project_property(
                    wrapped_data_contexts, current_type_name, field_name, **hints
                ),
            )
        )

    def project_neighbors(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        edge_info: EdgeInfo,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], Iterable[DataToken]]]:
        operation_name = "project_neighbors"
        input_iterable_name = InterpreterAdapterTap.INPUT_ITERABLE_NAME
        call_uid = self.recorder.record_call(
            operation_name,
            self.recorder.root_uid,
            (input_iterable_name, current_type_name, edge_info),
            hints,
        )
        wrapped_data_contexts = _unzip_and_yield_second(
            self.recorder.record_iterable(input_iterable_name, call_uid, data_contexts)
        )

        return _unzip_and_yield_second(
            self.recorder.record_compound_iterable(
                operation_name,
                call_uid,
                self.inner_adapter.project_neighbors(
                    wrapped_data_contexts, current_type_name, edge_info, **hints
                ),
            )
        )

    def can_coerce_to_type(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        coerce_to_type_name: str,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], bool]]:
        operation_name = "can_coerce_to_type"
        input_iterable_name = InterpreterAdapterTap.INPUT_ITERABLE_NAME
        call_uid = self.recorder.record_call(
            operation_name,
            self.recorder.root_uid,
            (input_iterable_name, current_type_name, coerce_to_type_name),
            hints,
        )
        wrapped_data_contexts = _unzip_and_yield_second(
            self.recorder.record_iterable(input_iterable_name, call_uid, data_contexts)
        )

        return _unzip_and_yield_second(
            self.recorder.record_iterable(
                operation_name,
                call_uid,
                self.inner_adapter.can_coerce_to_type(
                    wrapped_data_contexts, current_type_name, coerce_to_type_name, **hints
                ),
            )
        )


class TraceReplayAdapter(InterpreterAdapter[DataToken], Generic[DataToken]):

    _recording: RecordedTrace[DataToken]
    _next_possible_function_call: Iterator[Tuple[int, AdapterOperation]]
    _used_operations: List[bool]

    def __init__(self, recording: RecordedTrace[DataToken]) -> None:
        self._recording = recording
        self._next_possible_function_call = enumerate(self._recording.operations)
        self._used_operations = [False] * len(self._recording.operations)

    def _mark_operation_used(self, operation_index: int) -> None:
        if self._used_operations[operation_index]:
            marked_operation = self._recording.operations[operation_index]
            raise AssertionError(
                f"Unexpectedly, the operation in the trace is marked as already "
                f"having been used elsewhere; this is likely a bug in the TraceReplayAdapter "
                f"implementation itself. The operation record is at index {operation_index}: "
                f"{marked_operation}"
            )

        if operation_index > 0 and not self._used_operations[operation_index - 1]:
            predecessor_operation = self._recording.operations[operation_index - 1]
            raise AssertionError(
                f"While marking the operation at index {operation_index} as used, unexpectedly "
                f"discovered that its predecessor operation was not already used. This indicates "
                f"that the trace is not being followed in order, which is an error -- "
                f"the expectation that a single-threaded, deterministic computation always "
                f"proceeds with the same order of operations was violated. "
                f"Unused operation at index {operation_index - 1}: {predecessor_operation}"
            )

        self._used_operations[operation_index] = True

    def _find_next_top_level_function_call(
        self,
        function_name: str,
        positional_args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> Tuple[int, AdapterOperation]:
        for index, operation in self._next_possible_function_call:
            if operation.kind != "call":
                continue

            if operation.parent_uid != self._recording.root_uid:
                raise AssertionError(
                    f"Found an unexpected function call whose parent uid is not the root uid of "
                    f"the recorded trace. This is not supported by this adapter implementation. "
                    f"Root uid {self._recording.root_uid}, problematic operation entry "
                    f"at trace index {index}: {operation}"
                )

            if operation.name != function_name:
                raise AssertionError(
                    f"Found an unexpected function call in the trace. "
                    f"Expected a call to {function_name} with positional args {positional_args} "
                    f"and kwargs {kwargs}, but found the following operation record "
                    f"at index {index} in the trace: {operation}"
                )

            call_payload = (positional_args, kwargs)
            if operation.data != call_payload:
                raise AssertionError(
                    f"Found an unexpected function call in the trace. "
                    f"Expected a call to {function_name} with positional args {positional_args} "
                    f"and kwargs {kwargs}, but found a call to the same function with different "
                    f"arguments at index {index} in the trace: {operation}"
                )

            self._mark_operation_used(index)
            return index, operation

        raise AssertionError(
            f"No function call found with function name {function_name}, "
            f"positional args {positional_args} and kwargs {kwargs}. The trace does not match "
            f"the situation in which it is attempted to be used, so this is a bug."
        )

    def _find_yield_with_parent_uid(
        self, operation_name: str, parent_uid: int, trace_index: int
    ) -> Tuple[int, Optional[AdapterOperation]]:
        for index, operation in _enumerate_starting_at(self._recording.operations, trace_index):
            if operation.kind != "yield":
                continue

            if operation.name != operation_name or operation.parent_uid != parent_uid:
                continue

            self._mark_operation_used(index)
            return index, operation

        return len(self._recording.operations), None

    def _make_neighbors_iterable(
        self, iterable_name: str, parent_uid: int, trace_index: int
    ) -> Iterable[DataToken]:
        next_index = trace_index
        while next_index < len(self._recording.operations):
            yield_index, yield_operation = self._find_yield_with_parent_uid(
                iterable_name, parent_uid, next_index
            )

            if yield_operation is None:
                break
            else:
                next_index = yield_index + 1
                yield cast(DataToken, yield_operation.data)

    def _assert_contexts_are_equivalent(
        self,
        expected_context: DataContext[DataToken],
        actual_input_context: DataContext[DataToken],
    ) -> None:
        # TODO(predrag): Consider actually asserting here.
        #                They currently don't have an equality operation defined.
        pass

    def get_tokens_of_type(
        self,
        type_name: str,
        **hints: Any,
    ) -> Iterable[DataToken]:
        operation_name = "get_tokens_of_type"
        call_index, call_operation = self._find_next_top_level_function_call(
            operation_name, (type_name,), hints
        )

        next_index = call_index + 1
        while next_index < len(self._recording.operations):
            index, operation = self._find_yield_with_parent_uid(
                operation_name, call_operation.uid, next_index
            )
            if operation is None:
                break
            else:
                next_index = index + 1
                yield cast(DataToken, operation.data)

    def project_property(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        field_name: str,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], Any]]:
        operation_name = "project_property"
        input_iterable_name = InterpreterAdapterTap.INPUT_ITERABLE_NAME
        positional_args = (input_iterable_name, current_type_name, field_name)
        call_index, call_operation = self._find_next_top_level_function_call(
            operation_name, positional_args, hints
        )

        next_possible_input_yield_index = call_index + 1
        next_possible_output_yield_index = call_index + 1
        for data_context in data_contexts:
            input_yield_index, input_operation = self._find_yield_with_parent_uid(
                input_iterable_name, call_operation.uid, next_possible_input_yield_index
            )
            if input_operation is None:
                return

            next_possible_input_yield_index = input_yield_index + 1

            self._assert_contexts_are_equivalent(
                cast(DataContext[DataToken], input_operation.data),
                data_context,
            )

            # The output of a given operation is always after its input.
            # Later outputs come after earlier ones, i.e. this index is monotonically increasing.
            next_possible_output_yield_index = max(
                next_possible_input_yield_index, next_possible_output_yield_index
            )
            output_yield_index, output_operation = self._find_yield_with_parent_uid(
                operation_name, call_operation.uid, next_possible_output_yield_index
            )
            if output_operation is None:
                raise AssertionError(
                    f"No yield output found with operation name {operation_name} and "
                    f"parent_uid {call_operation.uid}, when searching beginning at "
                    f"trace index {next_possible_output_yield_index}. This is unexpected, since "
                    f"there is an iterable input at trace index {input_yield_index} for which "
                    f"no iterable output exists. Please ensure you are using a valid trace that "
                    f"was generated by recording an interpreter session. Unmatched iterable input: "
                    f"{input_operation}"
                )
            next_possible_output_yield_index = output_yield_index + 1

            yield cast(Tuple[DataContext[DataToken], Any], output_operation.data)

    def project_neighbors(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        edge_info: EdgeInfo,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], Iterable[DataToken]]]:
        operation_name = "project_neighbors"
        input_iterable_name = InterpreterAdapterTap.INPUT_ITERABLE_NAME
        positional_args = (input_iterable_name, current_type_name, edge_info)
        call_index, call_operation = self._find_next_top_level_function_call(
            operation_name, positional_args, hints
        )

        next_possible_input_yield_index = call_index + 1
        next_possible_output_yield_index = call_index + 1

        for data_context in data_contexts:
            input_yield_index, input_operation = self._find_yield_with_parent_uid(
                input_iterable_name, call_operation.uid, next_possible_input_yield_index
            )
            if input_operation is None:
                return
            next_possible_input_yield_index = input_yield_index + 1

            self._assert_contexts_are_equivalent(
                cast(DataContext[DataToken], input_operation.data),
                data_context,
            )

            # The output of a given operation is always after its input.
            # Later outputs come after earlier ones, i.e. this index is monotonically increasing.
            next_possible_output_yield_index = max(
                next_possible_input_yield_index, next_possible_output_yield_index
            )
            output_yield_index, output_operation = self._find_yield_with_parent_uid(
                operation_name, call_operation.uid, next_possible_output_yield_index
            )
            if output_operation is None:
                raise AssertionError(
                    f"No yield output found with operation name {operation_name} and "
                    f"parent_uid {call_operation.uid}, when searching beginning at "
                    f"trace index {next_possible_output_yield_index}. This is unexpected, since "
                    f"there is an iterable input at trace index {input_yield_index} for which "
                    f"no iterable output exists. Please ensure you are using a valid trace that "
                    f"was generated by recording an interpreter session. Unmatched iterable input: "
                    f"{input_operation}"
                )
            next_possible_output_yield_index = output_yield_index + 1

            temp_data_context, iterable_name = output_operation.data
            yielded_data_context = cast(DataContext[DataToken], temp_data_context)
            self._assert_contexts_are_equivalent(yielded_data_context, data_context)

            neighbors_iterable = self._make_neighbors_iterable(
                iterable_name, output_operation.uid, next_possible_output_yield_index
            )

            yield yielded_data_context, neighbors_iterable

    def can_coerce_to_type(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        coerce_to_type_name: str,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], bool]]:
        operation_name = "can_coerce_to_type"
        input_iterable_name = InterpreterAdapterTap.INPUT_ITERABLE_NAME
        positional_args = (input_iterable_name, current_type_name, coerce_to_type_name)
        call_index, call_operation = self._find_next_top_level_function_call(
            operation_name, positional_args, hints
        )

        next_possible_input_yield_index = call_index + 1
        next_possible_output_yield_index = call_index + 1
        for data_context in data_contexts:
            input_yield_index, input_operation = self._find_yield_with_parent_uid(
                input_iterable_name, call_operation.uid, next_possible_input_yield_index
            )
            next_possible_input_yield_index = input_yield_index + 1
            if input_operation is None:
                return

            self._assert_contexts_are_equivalent(
                cast(DataContext[DataToken], input_operation.data),
                data_context,
            )

            # The output of a given operation is always after its input.
            # Later outputs come after earlier ones, i.e. this index is monotonically increasing.
            next_possible_output_yield_index = max(
                next_possible_input_yield_index, next_possible_output_yield_index
            )
            output_yield_index, output_operation = self._find_yield_with_parent_uid(
                operation_name, call_operation.uid, next_possible_output_yield_index
            )
            if output_operation is None:
                raise AssertionError(
                    f"No yield output found with operation name {operation_name} and "
                    f"parent_uid {call_operation.uid}, when searching beginning at "
                    f"trace index {next_possible_output_yield_index}. This is unexpected, since "
                    f"there is an iterable input at trace index {input_yield_index} for which "
                    f"no iterable output exists. Please ensure you are using a valid trace that "
                    f"was generated by recording an interpreter session. Unmatched iterable input: "
                    f"{input_operation}"
                )
            next_possible_output_yield_index = output_yield_index + 1

            yield cast(Tuple[DataContext[DataToken], bool], output_operation.data)
