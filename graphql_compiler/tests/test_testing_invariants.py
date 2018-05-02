# Copyright 2017 Kensho Technologies, LLC.
"""Common GraphQL test inputs and expected outputs."""

from collections import namedtuple
from inspect import getmembers, isfunction
import unittest

from graphql import GraphQLID, GraphQLInt, GraphQLList, GraphQLString

# from test_compiler import CompilerTests
import test_input_data
# from test_ir_generation import IrGenerationTests


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
        if isfunction(member_dict[member]) and member[:4] == 'test'
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
        test_ir_generation_module = __import__('test_ir_generation', globals(), locals(),
                                               ['IrGenerationTests'], -1)
        ir_generation_tests = test_ir_generation_module.IrGenerationTests
        ir_generation_test_names = get_function_names_from_class(ir_generation_tests)
        for expected_test_function_name in self.expected_test_functions_list:
            if expected_test_function_name not in ir_generation_test_names:
                raise AssertionError(u'Test case "{}" not found in ir_generation_tests.py'
                                     u'.'.format(expected_test_function_name))

    def test_compiler_test_invariants(self):
        test_compiler_module = __import__('test_compiler', globals(), locals(),
                                          ['CompilerTests'], -1)
        compiler_tests = test_compiler_module.CompilerTests
        compiler_test_names = get_function_names_from_class(compiler_tests)
        for expected_test_function_name in self.expected_test_functions_list:
            if expected_test_function_name not in compiler_test_names:
                raise AssertionError(u'Test case "{}" not found in ir_generation_tests.py'
                                     u'.'.format(expected_test_function_name))
