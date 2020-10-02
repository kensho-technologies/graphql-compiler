from dataclasses import fields
from typing import Any, ClassVar, Dict, Optional
from unittest import TestCase

from graphql import GraphQLSchema

from .in_memory_test_adapter import InMemoryTestAdapter
from ..test_helpers import get_schema
from ...compiler.metadata import FilterInfo
from ...compiler.helpers import Location
from ...interpreter import DataContext, interpret_query
from ...interpreter.debugging import AdapterOperation, RecordedTrace, InterpreterAdapterTap
from ...interpreter.immutable_stack import ImmutableStack, make_empty_stack


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

        # We expect the trace to contain no operations, since nothing should have been called.
        trace = adapter.recorder.get_trace()

        scooby_doo_token = {"name": "Scooby Doo", "uuid": "1001"}
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
                            'runtime_arg_hints': {},
                            'used_property_hints': frozenset({'name'}),
                            'filter_hints': [],
                            'neighbor_hints': [],
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
                AdapterOperation("yield", "get_tokens_of_type", 2, 1, scooby_doo_token),
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

    def test_with_local_field(self) -> None:
        # Test that correct hints are given when calling project_property
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

        result_gen = interpret_query(adapter, self.schema, query, args)
        list(result_gen)  # drain the iterator

        trace = adapter.recorder.get_trace()

        project_property_calls = [
            operation
            for operation in trace.operations
            if operation.kind == "call" and operation.name == "project_property"
        ]

        # The interpreter calls project property to get:
        # - the color for the tag
        # - the name for the output
        # - the name again for the filter
        # The calls are batched across different vertices.
        self.assertEqual(3, len(project_property_calls))

        expected_hints = {
            'runtime_arg_hints': {},
            'used_property_hints': frozenset({'name', 'color'}),
            'filter_hints': [
                FilterInfo(fields=('name',), op_name='=', args=('%color',))
            ],
            'neighbor_hints': []
        }
        for project_property_call in project_property_calls:
            _, hints = project_property_call.data
            self.assertEqual(expected_hints, hints)
