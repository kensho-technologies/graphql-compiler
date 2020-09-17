from typing import Any, ClassVar, Dict
from unittest import TestCase

from graphql import GraphQLSchema

from .in_memory_test_adapter import InMemoryTestAdapter
from ..test_helpers import get_schema
from ...compiler.compiler_frontend import graphql_to_ir
from ...interpreter import interpret_ir
from ...interpreter.debugging import InterpreterAdapterTap


class InterpreterBehaviorTests(TestCase):
    schema: ClassVar[GraphQLSchema]

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

        ir_and_metadata = graphql_to_ir(self.schema, query)

        # Make but do not consume or advance the generator produced here!
        # This should not result in any calls to the adapter.
        interpret_ir(adapter, ir_and_metadata, args)

        # We expect the trace to contain no operations, since nothing should have been called.
        trace = adapter.recorder.get_trace()
        self.assertEqual(tuple(), trace.operations)
