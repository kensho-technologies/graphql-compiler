from copy import deepcopy
from dataclasses import dataclass
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
from uuid import uuid4

from typing_extensions import Literal

from .typedefs import DataContext, DataToken, EdgeInfo, InterpreterAdapter


def print_tap(info: str, data_contexts: Iterable[DataContext]) -> Iterable[DataContext]:
    # TODO(predrag): Debug-only code. Remove before merging.
    return data_contexts


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
    # N.B.: This is unlike enumerate(sequence, start=first_index) in that enumerate() always
    #       iterates the entire sequence and only changes the counter's value based on the start.
    #       In this function, we skip elements with indices in [0, first_index) in the sequence,
    #       and only iterate over elements with indices in [first_index, len(sequence)).
    for index in range(first_index, len(sequence)):
        yield index, sequence[index]


def _unzip_and_yield_second(iterable: Iterable[Tuple[T, U]]) -> Iterable[U]:
    for _, second in iterable:
        yield second


@dataclass(frozen=True)
class AdapterOperation:
    kind: Literal["call", "yield", "return"]
    name: str
    uid: str
    parent_uid: str
    data: Any


@dataclass(frozen=True)
class RecordedTrace(Generic[DataToken]):
    root_uid: str
    operations: Tuple[AdapterOperation, ...]


class TraceRecorder(Generic[DataToken]):

    # We expose an immutable (copied) version of the operation log through get_trace().
    # Other attributes are considered public.
    _operation_log: List[AdapterOperation]
    root_uid: str

    def __init__(self) -> None:
        self._operation_log = []
        self.root_uid = str(uuid4())

    def record_call(
        self,
        operation_name: str,
        parent_uid: str,
        call_args: Tuple[Any, ...],
        call_kwargs: Dict[str, Any],
    ) -> str:
        uid = str(uuid4())
        call_args = deepcopy(call_args)
        call_kwargs = deepcopy(call_kwargs)
        self._operation_log.append(
            AdapterOperation("call", operation_name, uid, parent_uid, (call_args, call_kwargs))
        )
        return uid

    def record_iterable(
        self, operation_name: str, parent_uid: str, iterable: Iterable[T]
    ) -> Iterable[Tuple[str, T]]:
        for item in iterable:
            item_uid = str(uuid4())
            self._operation_log.append(
                AdapterOperation("yield", operation_name, item_uid, parent_uid, deepcopy(item))
            )
            yield item_uid, item

    def record_compound_iterable(
        self,
        operation_name: str,
        parent_uid: str,
        compound_iterable: Iterable[Tuple[U, Iterable[T]]],
    ) -> Iterable[Tuple[str, Tuple[U, Iterable[T]]]]:
        for item_index, item in enumerate(compound_iterable):
            item_uid = str(uuid4())
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
        return RecordedTrace(self.root_uid, tuple(self._operation_log))


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
        self, operation_name: str, parent_uid: str, trace_index: int
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
        self, iterable_name: str, parent_uid: str, trace_index: int
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
