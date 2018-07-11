# Copyright 2017-present Kensho Technologies, LLC.
"""Common GraphQL test inputs and expected outputs."""
from inspect import getmembers, isfunction
import unittest

import graphql_compiler.tests.test_input_data as test_input_data


def get_function_names_from_module(module):
    """Return a set of function names present in a given module."""
    return {
        member
        for member, member_type in getmembers(module)
        if isfunction(member_type)
    }


def get_test_function_names_from_class(test_class):
    """Return a set of test function names present in a given TestCase class."""
    if not issubclass(test_class, unittest.TestCase):
        raise AssertionError(u'Received non-test class {} as input.'
                             .format(test_class))
    member_dict = test_class.__dict__
    return {
        member
        for member in member_dict
        if isfunction(member_dict[member]) and member[:5] == 'test_'
    }


# The namedtuple function is imported from test_input_data,
# but does not correspond to any test inputs.
IGNORED_FUNCTIONS = frozenset({'namedtuple'})


class TestingInvariants(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        input_names = get_function_names_from_module(test_input_data)
        self.expected_test_functions = {
            'test_' + input_name
            for input_name in input_names
            if input_name not in IGNORED_FUNCTIONS
        }

    def test_ir_generation_test_invariants(self):
        # Importing IrGenerationTests globally would expose them to py.test a second time.
        # We import them here so that these tests are not run again.
        from .test_ir_generation import IrGenerationTests
        ir_generation_test_names = get_test_function_names_from_class(IrGenerationTests)
        for expected_test_function_name in self.expected_test_functions:
            if expected_test_function_name not in ir_generation_test_names:
                raise AssertionError(u'Test case "{}" not found in test_ir_generation.py.'
                                     .format(expected_test_function_name))

    def test_compiler_test_invariants(self):
        # Importing CompilerTests globally would expose them to py.test a second time.
        # We import them here so that these tests are not run again.
        from .test_compiler import CompilerTests
        compiler_test_names = get_test_function_names_from_class(CompilerTests)
        for expected_test_function_name in self.expected_test_functions:
            if expected_test_function_name not in compiler_test_names:
                raise AssertionError(u'Test case "{}" not found in test_compiler.py.'
                                     .format(expected_test_function_name))
