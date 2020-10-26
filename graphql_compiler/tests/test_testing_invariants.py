# Copyright 2017-present Kensho Technologies, LLC.
"""Common GraphQL test inputs and expected outputs."""
import unittest

from . import test_input_data as test_input_data
from .test_helpers import get_function_names_from_module, get_test_function_names_from_class


# The namedtuple function is imported from test_input_data,
# but does not correspond to any test inputs.
IGNORED_FUNCTIONS = frozenset({"namedtuple"})


class TestingInvariants(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        input_names = get_function_names_from_module(test_input_data)
        self.expected_test_functions = {
            "test_" + input_name
            for input_name in input_names
            if input_name not in IGNORED_FUNCTIONS
        }

    def test_ir_generation_test_invariants(self) -> None:
        # Importing IrGenerationTests globally would expose them to py.test a second time.
        # We import them here so that these tests are not run again.
        from .test_ir_generation import IrGenerationTests

        ir_generation_test_names = get_test_function_names_from_class(IrGenerationTests)
        for expected_test_function_name in self.expected_test_functions:
            if expected_test_function_name not in ir_generation_test_names:
                raise AssertionError(
                    'Test case "{}" not found in test_ir_generation.py.'.format(
                        expected_test_function_name
                    )
                )

    def test_compiler_test_invariants(self) -> None:
        # Importing CompilerTests globally would expose them to py.test a second time.
        # We import them here so that these tests are not run again.
        from .test_compiler import CompilerTests

        compiler_test_names = get_test_function_names_from_class(CompilerTests)
        for expected_test_function_name in self.expected_test_functions:
            if expected_test_function_name not in compiler_test_names:
                raise AssertionError(
                    'Test case "{}" not found in test_compiler.py.'.format(
                        expected_test_function_name
                    )
                )
