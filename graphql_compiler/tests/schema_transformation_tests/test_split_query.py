# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from textwrap import dedent
import unittest

from graphql import parse, print_ast

from ...exceptions import GraphQLValidationError
from ...schema_transformation.split_query import split_query
from .example_schema import (
    basic_merged_schema, interface_merged_schema, three_merged_schema, union_merged_schema
)


# The below namedtuple is used to check the structure of SubQueryNodes in tests
ExampleQueryNode = namedtuple(
    'ExampleQueryNode', (
        'query_str',
        'schema_id',
        'child_query_nodes_and_out_names',
        # List[Tuple[ExampleQueryNode, str, str]]
        # child example query node, parent out name, child out name
    )
)


class TestSplitQuery(unittest.TestCase):
    def _check_query_node_structure(self, root_query_node, root_example_query_node):
        """Check root_query_node has no parent and has the same structure as the example input."""
        self.assertIs(root_query_node.parent_query_connection, None)
        self._check_query_node_structure_helper(root_query_node, root_example_query_node)

    def _check_query_node_structure_helper(self, query_node, example_query_node):
        """Check query_node has the same structure as example_query_node."""
        # Check AST and id of the parent
        self.assertEqual(print_ast(query_node.query_ast), example_query_node.query_str)
        self.assertEqual(query_node.schema_id, example_query_node.schema_id)
        # Check number of children matches
        self.assertEqual(len(query_node.child_query_connections),
                         len(example_query_node.child_query_nodes_and_out_names))
        for i in range(len(query_node.child_query_connections)):
            # Check child and parent connections
            child_query_connection = query_node.child_query_connections[i]
            child_query_node = child_query_connection.sink_query_node
            child_example_query_node, parent_out_name, child_out_name = \
                example_query_node.child_query_nodes_and_out_names[i]
            self._check_query_node_edge(query_node, i, child_query_node, parent_out_name,
                                        child_out_name)
            # Recurse
            self._check_query_node_structure_helper(child_query_node, child_example_query_node)

    def _check_query_node_edge(self, parent_query_node, parent_to_child_edge_index,
                               child_query_node, parent_out_name, child_out_name):
        """Check the edge between parent and child is symmetric, with the right output names."""
        parent_to_child_connection = \
            parent_query_node.child_query_connections[parent_to_child_edge_index]
        child_to_parent_connection = child_query_node.parent_query_connection

        self.assertIs(parent_to_child_connection.sink_query_node, child_query_node)
        self.assertIs(child_to_parent_connection.sink_query_node, parent_query_node)
        self.assertEqual(parent_to_child_connection.source_field_out_name, parent_out_name)
        self.assertEqual(child_to_parent_connection.sink_field_out_name, parent_out_name)
        self.assertEqual(parent_to_child_connection.sink_field_out_name, child_out_name)
        self.assertEqual(child_to_parent_connection.source_field_out_name, child_out_name)

    def _get_intermediate_outputs_set(self, number_of_outputs):
        output_names = set(
            '__intermediate_output_' + str(count) for count in range(number_of_outputs)
        )
        return frozenset(output_names)
