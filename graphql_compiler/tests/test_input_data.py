# Copyright 2017 Kensho Technologies, Inc.
"""Common GraphQL test inputs and expected outputs."""

from collections import namedtuple

from graphql import GraphQLString

from ..compiler.compiler_frontend import OutputMetadata


CommonTestData = namedtuple(
    'CommonTestData',
    ('graphql_input', 'expected_output_metadata', 'expected_input_metadata'))


def immediate_output():
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata)
