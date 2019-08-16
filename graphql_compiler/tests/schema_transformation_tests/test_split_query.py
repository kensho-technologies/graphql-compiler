# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
import unittest

from graphql import print_ast


# The below namedtuple is used to check the structure of SubQueryNodes in tests
ExpectedQueryNode = namedtuple(
    'ExpectedQueryNode', (
        'query_str',
        'schema_id',
        'child_query_nodes_and_out_names',
        # List[Tuple[ExpectedQueryNode, str, str]]
        # child expected query node, parent out name, child out name
    )
)


class TestSplitQuery(unittest.TestCase):
    def _check_query_node_structure(self, root_query_node, root_expected_query_node):
        """Check root_query_node has no parent and has the same structure as the expected input."""
        self.assertIsNone(root_query_node.parent_query_connection)
        self._check_query_node_structure_helper(root_query_node, root_expected_query_node)

    def _check_query_node_structure_helper(self, query_node, expected_query_node):
        """Check query_node has the same structure as expected_query_node."""
        # Check AST and id of the parent
        self.assertEqual(print_ast(query_node.query_ast), expected_query_node.query_str)
        self.assertEqual(query_node.schema_id, expected_query_node.schema_id)
        # Check number of children matches
        child_query_connections = query_node.child_query_connections
        expected_child_data = expected_query_node.child_query_nodes_and_out_names
        self.assertEqual(len(child_query_connections), len(expected_child_data))
        for i, (child_query_connection, expected_child_data_piece) in enumerate(
            six.moves.zip(child_query_connections, expected_child_data)
        ):
            # Check child and parent connections
            child_query_node = child_query_connection.sink_query_node
            child_expected_query_node, parent_out_name, child_out_name = expected_child_data_piece
            self._check_query_node_edge(query_node, i, child_query_node, parent_out_name,
                                        child_out_name)
            # Recurse
            self._check_query_node_structure_helper(child_query_node, child_expected_query_node)

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
