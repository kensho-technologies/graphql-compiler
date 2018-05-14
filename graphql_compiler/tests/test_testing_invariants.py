# Copyright 2017 Kensho Technologies, LLC.
"""Common GraphQL test inputs and expected outputs."""
from inspect import getmembers, isfunction
import unittest

import test_input_data


def get_function_names_from_module(module):
    return [
        member
        for (member, member_type) in getmembers(module)
        if isfunction(member_type)
    ]


def get_function_names_from_class(test_class):
    member_dict = test_class.__dict__
    return set(
        member
        for member in member_dict
        if isfunction(member_dict[member]) and member[:5] == 'test_'
    )


IGNORED_FUNCTIONS = ['namedtuple']


class TestingInvariants(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        input_names_list = get_function_names_from_module(test_input_data)
        self.expected_test_functions_list = [
            'test_' + input_name
            for input_name in input_names_list
            if input_name not in IGNORED_FUNCTIONS
        ]

    def test_ir_generation_test_invariants(self):
        # Importing IrGenerationTests globally would expose them to py.test a second time.
        # We import them here so that these tests are not run again.
        from .test_ir_generation import IrGenerationTests
        ir_generation_test_names = get_function_names_from_class(IrGenerationTests)
        for expected_test_function_name in self.expected_test_functions_list:
            if expected_test_function_name not in ir_generation_test_names:
                raise AssertionError(u'Test case "{}" not found in ir_generation_tests.py.'
                                     .format(expected_test_function_name))

    def test_compiler_test_invariants(self):
        # Importing CompilerTests globally would expose them to py.test a second time.
        # We import them here so that these tests are not run again.
        from .test_compiler import CompilerTests
        compiler_test_names = get_function_names_from_class(CompilerTests)
        for expected_test_function_name in self.expected_test_functions_list:
            if expected_test_function_name not in compiler_test_names:
                raise AssertionError(u'Test case "{}" not found in compiler_tests.py.'
                                     .format(expected_test_function_name))
