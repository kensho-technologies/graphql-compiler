from dataclasses import fields
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from unittest import TestCase

from graphql import GraphQLSchema

from ...compiler.helpers import Location
from ...compiler.metadata import FilterInfo
from ...exceptions import GraphQLInvalidArgumentError
from ...interpreter import DataContext, interpret_query
from ...interpreter.debugging import AdapterOperation, InterpreterAdapterTap, RecordedTrace
from ...interpreter.immutable_stack import ImmutableStack, make_empty_stack
from ..test_helpers import get_schema
from .in_memory_test_adapter import InMemoryTestAdapter


class InterpreterBehaviorTests(TestCase):
    schema: ClassVar[GraphQLSchema]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Register trace and context equality functions for this test suite."""
        super().__init__(*args, **kwargs)
        self.maxDiff = None

        # RecordedTrace and DataContext objects in general aren't necessarily comparable,
        # since they are generic on DataToken, and the DataToken type parameter doesn't necessarily
        # have to support equality-checking. However, for this particular test suite, we know that
        # DataToken is actually dict(), and can construct a proper way to check equality.
        self.addTypeEqualityFunc(DataContext, self._assert_data_contexts_are_equal)
        self.addTypeEqualityFunc(RecordedTrace, self._assert_traces_are_equal)

        # ImmutableStack objects also in general aren't necessarily comparable, but for dict-typed
        # tokens, all data that might end up on the stack is actually going to be comparable,
        # so we can make a reasonable comparison function for this test suite in particular.
        self.addTypeEqualityFunc(ImmutableStack, self._assert_immutable_stacks_are_equal)

        # By default, tuples are compared directly with their own `==` operator. We need to override
        # that behavior since the `==` operator doesn't respect our custom equality rules:
        # we simply check tuples element-wise with self.assertEqual(), which does respect our rules.
        self.addTypeEqualityFunc(tuple, self._assert_tuples_are_equal)

    def _assert_data_contexts_are_equal(
        self,
        expected_context: DataContext[dict],
        actual_context: DataContext[dict],
        msg: Optional[str] = None,
    ) -> None:
        for attribute_name in DataContext.__slots__:
            self.assertEqual(
                getattr(expected_context, attribute_name),
                getattr(actual_context, attribute_name),
                msg=msg,
            )

    def _assert_traces_are_equal(
        self,
        expected_trace: RecordedTrace[dict],
        actual_trace: RecordedTrace[dict],
        msg: Optional[str] = None,
    ) -> None:
        msg_suffix = (" " + msg) if msg is not None else ""
        self.assertEqual(
            expected_trace.root_uid,
            actual_trace.root_uid,
            msg=(
                (
                    f"Traces have different root_uid values: "
                    f"{expected_trace.root_uid} != {actual_trace.root_uid}."
                )
                + msg_suffix
            ),
        )

        # Compare trace prefixes first: zip() stops when the shorter of the two iterables runs out.
        for index, (expected_op, actual_op) in enumerate(
            zip(expected_trace.operations, actual_trace.operations)
        ):
            for field_definition in fields(AdapterOperation):
                field_name = field_definition.name
                self.assertEqual(
                    getattr(expected_op, field_name),
                    getattr(actual_op, field_name),
                    msg=(
                        (
                            f"Trace mismatch at operation index {index} "
                            f'on operation field "{field_name}": '
                            f"{expected_op} != {actual_op}"
                        )
                        + msg_suffix
                    ),
                )

        # Then, compare that the number of operations is equal in both traces.
        # The maximal shared prefix of two equal-length collections is the full collection,
        # so after this check, we know that the lists of operations must have been equal.
        self.assertEqual(
            len(expected_trace.operations),
            len(actual_trace.operations),
            msg=(
                (
                    f"Traces have different numbers of operations: "
                    f"{len(expected_trace.operations)} != {len(actual_trace.operations)}"
                )
                + msg_suffix
            ),
        )

    def _assert_immutable_stacks_are_equal(
        self,
        expected_stack: ImmutableStack,
        actual_stack: ImmutableStack,
        msg: Optional[str] = None,
    ) -> None:
        self.assertEqual(expected_stack.depth, actual_stack.depth, msg=msg)
        self.assertEqual(expected_stack.value, actual_stack.value, msg=msg)
        self.assertEqual(expected_stack.tail, actual_stack.tail, msg=msg)

    def _assert_tuples_are_equal(
        self,
        expected_tuple: tuple,
        actual_tuple: tuple,
        msg: Optional[str] = None,
    ) -> None:
        self.assertEqual(len(expected_tuple), len(actual_tuple), msg=msg)
        for index, (expected_item, actual_item) in enumerate(zip(expected_tuple, actual_tuple)):
            self.assertEqual(
                expected_item,
                actual_item,
                msg=(
                    f"First differing element {index}: {expected_item} != {actual_item}"
                    + (f"\n\n{msg}" if msg is not None else "")
                ),
            )

    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = get_schema()

    def test_eager_exception_on_bad_query_arguments(self) -> None:
        adapter = InterpreterAdapterTap(InMemoryTestAdapter())

        query_with_no_args = """{
            Animal {
                name @output(out_name: "name")
            }
        }"""
        query_with_args = """{
            Animal {
                name @output(out_name: "name") @filter(op_name: "=", value: ["$animal_name"])
            }
        }"""
        string_args = {"animal_name": "Beethoven"}
        int_args = {"animal_name": 123}

        invalid_calls: Tuple[Tuple[str, Dict[str, Any]], ...] = (
            (query_with_no_args, string_args),
            (query_with_args, {}),
            (query_with_args, int_args),
        )

        for invalid_query, invalid_args in invalid_calls:
            # Invalid calls must be caught before the generator is returned, i.e. eagerly.
            with self.assertRaises(GraphQLInvalidArgumentError):
                interpret_query(adapter, self.schema, invalid_query, invalid_args)

        # We expect the trace to contain no operations, since nothing should have been called.
        trace = adapter.recorder.get_trace()
        expected_trace = RecordedTrace[dict](tuple())
        self.assertEqual(expected_trace, trace)

    def test_no_adapter_calls_if_output_generator_is_not_advanced(self) -> None:
        adapter = InterpreterAdapterTap(InMemoryTestAdapter())

        # It shouldn't really matter what kind of query we run here, the outcome should be the same.
        query = """{
            Animal {
                name @output(out_name: "name")
            }
        }"""
        args: Dict[str, Any] = {}

        # Make but do not consume or advance the generator produced here!
        # This should not result in any calls to the adapter.
        interpret_query(adapter, self.schema, query, args)

        # We expect the trace to contain no operations, since nothing should have been called.
        trace = adapter.recorder.get_trace()
        expected_trace = RecordedTrace[dict](tuple())
        self.assertEqual(expected_trace, trace)

    def test_single_generator_pull_grabs_only_one_result_from_adapter(self) -> None:
        adapter = InterpreterAdapterTap(InMemoryTestAdapter())

        query = """{
            Animal {
                name @output(out_name: "name")
            }
        }"""
        args: Dict[str, Any] = {}

        result_gen = interpret_query(adapter, self.schema, query, args)

        next_row = next(result_gen)  # advance the generator one step
        expected_next_row = {
            "name": "Scooby Doo",
        }
        self.assertEqual(expected_next_row, next_row)

        trace = adapter.recorder.get_trace()

        scooby_doo_token = {"name": "Scooby Doo", "uuid": "1001", "__typename": "Animal"}
        scooby_doo_base_context = DataContext[dict](
            scooby_doo_token,
            {
                Location(("Animal",), None, 1): scooby_doo_token,
            },
            make_empty_stack().push({}),
        )
        scooby_doo_context = DataContext[dict](
            scooby_doo_token,
            {
                Location(("Animal",), None, 1): scooby_doo_token,
            },
            scooby_doo_base_context.expression_stack.push(scooby_doo_base_context),
        )

        expected_trace = RecordedTrace[dict](
            (
                AdapterOperation(
                    "call",
                    "project_property",
                    0,
                    RecordedTrace.DEFAULT_ROOT_UID,
                    (
                        ("__input_iterable", "Animal", "name"),
                        {
                            "runtime_arg_hints": {},
                            "used_property_hints": frozenset({"name"}),
                            "filter_hints": [],
                            "neighbor_hints": [],
                        },
                    ),
                ),
                AdapterOperation(
                    "call",
                    "get_tokens_of_type",
                    1,
                    RecordedTrace.DEFAULT_ROOT_UID,
                    (
                        ("Animal",),
                        {
                            "runtime_arg_hints": {},
                            "used_property_hints": frozenset({"name"}),
                            "filter_hints": [],
                            "neighbor_hints": [],
                        },
                    ),
                ),
                AdapterOperation(
                    "yield",
                    "get_tokens_of_type",
                    2,
                    1,
                    scooby_doo_token,
                ),
                AdapterOperation(
                    "yield",
                    InterpreterAdapterTap.INPUT_ITERABLE_NAME,
                    3,
                    0,
                    scooby_doo_context,
                ),
                AdapterOperation(
                    "yield",
                    "project_property",
                    4,
                    0,
                    (scooby_doo_context, "Scooby Doo"),
                ),
            )
        )
        self.assertEqual(expected_trace, trace)

    def test_filtering_a_non_output_value_works_correctly(self) -> None:
        adapter = InterpreterAdapterTap(InMemoryTestAdapter())

        query = """{
            Animal {
                name @filter(op_name: "=", value: ["$scooby_name"])
                uuid @output(out_name: "uuid")
            }
        }"""
        args: Dict[str, Any] = {
            "scooby_name": "Scooby Doo",
        }

        result_gen = interpret_query(adapter, self.schema, query, args)

        next_row = next(result_gen)  # advance the generator one step
        expected_next_row = {
            "uuid": "1001",
        }
        self.assertEqual(expected_next_row, next_row)

        trace = adapter.recorder.get_trace()

        scooby_doo_token = {"name": "Scooby Doo", "uuid": "1001", "__typename": "Animal"}
        scooby_doo_local_context = DataContext[dict](
            scooby_doo_token,
            {},
            make_empty_stack(),
        )
        scooby_doo_global_base_context = DataContext[dict](
            scooby_doo_token,
            {
                Location(("Animal",), None, 1): scooby_doo_token,
            },
            make_empty_stack().push({}),
        )
        scooby_doo_global_context = DataContext[dict](
            scooby_doo_token,
            {
                Location(("Animal",), None, 1): scooby_doo_token,
            },
            scooby_doo_global_base_context.expression_stack.push(scooby_doo_global_base_context),
        )
        expected_hints = {
            "runtime_arg_hints": {
                "scooby_name": "Scooby Doo",
            },
            "used_property_hints": frozenset({"name", "uuid"}),
            "filter_hints": [FilterInfo(("name",), "=", ("$scooby_name",))],
            "neighbor_hints": [],
        }
        expected_trace = RecordedTrace[dict](
            (
                AdapterOperation(
                    "call",
                    "project_property",
                    0,
                    RecordedTrace.DEFAULT_ROOT_UID,
                    (
                        ("__input_iterable", "Animal", "uuid"),
                        expected_hints,
                    ),
                ),
                AdapterOperation(
                    "call",
                    "project_property",
                    1,
                    RecordedTrace.DEFAULT_ROOT_UID,
                    (
                        ("__input_iterable", "Animal", "name"),
                        expected_hints,
                    ),
                ),
                AdapterOperation(
                    "call",
                    "get_tokens_of_type",
                    2,
                    RecordedTrace.DEFAULT_ROOT_UID,
                    (
                        ("Animal",),
                        expected_hints,
                    ),
                ),
                AdapterOperation(
                    "yield",
                    "get_tokens_of_type",
                    3,
                    2,
                    scooby_doo_token,
                ),
                AdapterOperation(
                    "yield",
                    InterpreterAdapterTap.INPUT_ITERABLE_NAME,
                    4,
                    1,
                    scooby_doo_local_context,
                ),
                AdapterOperation(
                    "yield",
                    "project_property",
                    5,
                    1,
                    (scooby_doo_local_context, "Scooby Doo"),
                ),
                AdapterOperation(
                    "yield",
                    InterpreterAdapterTap.INPUT_ITERABLE_NAME,
                    6,
                    0,
                    scooby_doo_global_context,
                ),
                AdapterOperation(
                    "yield",
                    "project_property",
                    7,
                    0,
                    (scooby_doo_global_context, "1001"),
                ),
            )
        )
        self.assertEqual(expected_trace, trace)

    def test_filter_hints_on_get_tokens_of_type_optimize_initial_data_loading(self) -> None:
        adapter = InterpreterAdapterTap(InMemoryTestAdapter())

        query = """{
            Animal {
                uuid @output(out_name: "uuid") @filter(op_name: "=", value: ["$uuid"])
            }
        }"""
        args: Dict[str, Any] = {
            "uuid": "1008",
        }

        result_gen = interpret_query(adapter, self.schema, query, args)

        all_data = list(result_gen)  # drain the generator
        expected_next_row = {
            "uuid": "1008",
        }
        self.assertEqual([expected_next_row], all_data)

        trace = adapter.recorder.get_trace()

        domino_token = {"name": "Domino", "uuid": "1008", "__typename": "Animal"}
        domino_local_context = DataContext[dict](
            domino_token,
            {},
            make_empty_stack(),
        )
        domino_global_base_context = DataContext[dict](
            domino_token,
            {
                Location(("Animal",), None, 1): domino_token,
            },
            make_empty_stack().push({}),
        )
        domino_global_context = DataContext[dict](
            domino_token,
            {
                Location(("Animal",), None, 1): domino_token,
            },
            domino_global_base_context.expression_stack.push(domino_global_base_context),
        )
        expected_hints = {
            "runtime_arg_hints": {
                "uuid": "1008",
            },
            "used_property_hints": frozenset({"uuid"}),
            "filter_hints": [FilterInfo(("uuid",), "=", ("$uuid",))],
            "neighbor_hints": [],
        }
        expected_trace = RecordedTrace[dict](
            (
                AdapterOperation(
                    "call",
                    "project_property",
                    0,
                    RecordedTrace.DEFAULT_ROOT_UID,
                    (
                        ("__input_iterable", "Animal", "uuid"),
                        expected_hints,
                    ),
                ),
                AdapterOperation(
                    "call",
                    "project_property",
                    1,
                    RecordedTrace.DEFAULT_ROOT_UID,
                    (
                        ("__input_iterable", "Animal", "uuid"),
                        expected_hints,
                    ),
                ),
                AdapterOperation(
                    "call",
                    "get_tokens_of_type",
                    2,
                    RecordedTrace.DEFAULT_ROOT_UID,
                    (
                        ("Animal",),
                        expected_hints,
                    ),
                ),
                AdapterOperation(
                    # This is the only "yield" from get_tokens_of_type(), since its implementation
                    # is able to use the provided hints to eliminate other vertices. This is
                    # an example of the predicate pushdown optimization: even though the filter
                    # semantically happens later, it can be applied early by "pushing it down" into
                    # the get_tokens_of_type() call.
                    "yield",
                    "get_tokens_of_type",
                    3,
                    2,
                    domino_token,
                ),
                AdapterOperation(
                    "yield",
                    InterpreterAdapterTap.INPUT_ITERABLE_NAME,
                    4,
                    1,
                    domino_local_context,
                ),
                AdapterOperation(
                    "yield",
                    "project_property",
                    5,
                    1,
                    (domino_local_context, "1008"),
                ),
                AdapterOperation(
                    "yield",
                    InterpreterAdapterTap.INPUT_ITERABLE_NAME,
                    6,
                    0,
                    domino_global_context,
                ),
                AdapterOperation(
                    "yield",
                    "project_property",
                    7,
                    0,
                    (domino_global_context, "1008"),
                ),
            )
        )
        self.assertEqual(expected_trace, trace)

    def test_tag_and_filter_on_local_field(self) -> None:
        # Test for correct behavior (including proper hints) when querying with @tag and @filter
        # for a local field (the tagged value in the same scope).
        adapter = InterpreterAdapterTap(InMemoryTestAdapter())

        query = """{
            Animal {
                color @tag(tag_name: "color")
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["%color"])
            }
        }"""
        args: Dict[str, Any] = {}
        expected_results: List[Dict[str, Any]] = []

        result_gen = interpret_query(adapter, self.schema, query, args)
        actual_results = list(result_gen)  # drain the iterator
        self.assertEqual(expected_results, actual_results)

        trace = adapter.recorder.get_trace()

        # The first exactly four elements of the traces have operation.kind == "call".
        num_calls = 4
        for operation in trace.operations[:num_calls]:
            self.assertEqual("call", operation.kind)

        # None of the other operations in the trace are calls.
        # This is because all operations of the same flavor are batched across vertices.
        for operation in trace.operations[num_calls:]:
            self.assertNotEqual("call", trace.operations[num_calls].kind)

        actual_call_operations = trace.operations[:num_calls]

        expected_hints = {
            "runtime_arg_hints": {},
            "used_property_hints": frozenset({"name", "color"}),
            "filter_hints": [FilterInfo(fields=("name",), op_name="=", args=("%color",))],
            "neighbor_hints": [],
        }
        output_operation_uid = 0
        filter_name_operation_uid = 1
        filter_color_tag_operation_uid = 2
        get_tokens_operation_uid = 3
        expected_call_operations = (
            AdapterOperation(  # The @output on the "name" field.
                "call",
                "project_property",
                output_operation_uid,
                RecordedTrace.DEFAULT_ROOT_UID,
                (
                    ("__input_iterable", "Animal", "name"),
                    expected_hints,
                ),
            ),
            AdapterOperation(  # The @filter on the "name" field.
                "call",
                "project_property",
                filter_name_operation_uid,
                RecordedTrace.DEFAULT_ROOT_UID,
                (
                    ("__input_iterable", "Animal", "name"),
                    expected_hints,
                ),
            ),
            AdapterOperation(  # Resolving the "%color" in the filter, coming from @tag on "color".
                "call",
                "project_property",
                filter_color_tag_operation_uid,
                RecordedTrace.DEFAULT_ROOT_UID,
                (
                    ("__input_iterable", "Animal", "color"),
                    expected_hints,
                ),
            ),
            AdapterOperation(  # The @filter on the "name" field.
                "call",
                "get_tokens_of_type",
                get_tokens_operation_uid,
                RecordedTrace.DEFAULT_ROOT_UID,
                (
                    ("Animal",),
                    expected_hints,
                ),
            ),
        )

        self.assertEqual(expected_call_operations, actual_call_operations)

        # We already asserted that this query outputs no results.
        # Let's ensure that:
        # 1. The get_tokens_of_type() produced some tokens.
        # 2. Those tokens progressed through the two project_property() calls that
        #    together form the @filter's evaluation.
        # 3. The @filter discarded all tokens, i.e. the project_property() call corresponding
        #    to the single @output in the query received an empty iterable as input.
        # ------
        # 1. The get_tokens_of_type() produced some tokens.
        #    We find "yield"-kind operations whose "parent_uid" matches the uid of
        #    our get_tokens_of_type() operation, and ensure we get a non-empty list.
        get_tokens_yield_operations = [
            operation
            for operation in trace.operations
            if operation.kind == "yield" and operation.parent_uid == get_tokens_operation_uid
        ]
        self.assertNotEqual([], get_tokens_yield_operations)

        get_tokens_yielded_tokens = tuple(
            operation.data for operation in get_tokens_yield_operations
        )

        # 2. The two project_property() calls consume and produce the same number of tokens
        #    (wrapped in DataContext objects), in the same order as originally returned
        #    by get_tokens_of_type().
        filter_name_input_iterable_operations = [
            operation
            for operation in trace.operations
            if (
                operation.kind == "yield"
                and operation.parent_uid == filter_name_operation_uid
                and operation.name == InterpreterAdapterTap.INPUT_ITERABLE_NAME
            )
        ]
        filter_name_input_tokens = tuple(
            operation.data.current_token for operation in filter_name_input_iterable_operations
        )
        self.assertEqual(get_tokens_yielded_tokens, filter_name_input_tokens)

        filter_name_yielded_operations = [
            operation
            for operation in trace.operations
            if (
                operation.kind == "yield"
                and operation.parent_uid == filter_name_operation_uid
                and operation.name == "project_property"
            )
        ]
        filter_name_yielded_tokens = tuple(
            operation.data[0].current_token  # operation.data is Tuple[DataContext[DataToken], Any]
            for operation in filter_name_yielded_operations
        )
        self.assertEqual(get_tokens_yielded_tokens, filter_name_yielded_tokens)

        filter_color_tag_input_iterable_operations = [
            operation
            for operation in trace.operations
            if (
                operation.kind == "yield"
                and operation.parent_uid == filter_color_tag_operation_uid
                and operation.name == InterpreterAdapterTap.INPUT_ITERABLE_NAME
            )
        ]
        filter_color_tag_input_tokens = tuple(
            operation.data.current_token for operation in filter_color_tag_input_iterable_operations
        )
        self.assertEqual(get_tokens_yielded_tokens, filter_color_tag_input_tokens)

        filter_color_tag_yielded_operations = [
            operation
            for operation in trace.operations
            if (
                operation.kind == "yield"
                and operation.parent_uid == filter_color_tag_operation_uid
                and operation.name == "project_property"
            )
        ]
        filter_color_tag_yielded_tokens = tuple(
            operation.data[0].current_token  # operation.data is Tuple[DataContext[DataToken], Any]
            for operation in filter_color_tag_yielded_operations
        )
        self.assertEqual(get_tokens_yielded_tokens, filter_color_tag_yielded_tokens)

        # 3. The @filter discarded all tokens, i.e. the project_property() call corresponding
        #    to the single @output in the query received an empty iterable as input.
        output_operation_input_iterable_operations = [
            operation
            for operation in trace.operations
            if (
                operation.kind == "yield"
                and operation.parent_uid == output_operation_uid
                and operation.name == InterpreterAdapterTap.INPUT_ITERABLE_NAME
            )
        ]
        self.assertEqual([], output_operation_input_iterable_operations)
