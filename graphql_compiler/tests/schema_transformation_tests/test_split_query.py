# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from textwrap import dedent
import unittest

from graphql import parse, print_ast
import six

from ...exceptions import GraphQLValidationError
from ...schema_transformation.split_query import split_query
from .example_schema import (
    basic_merged_schema,
    interface_merged_schema,
    stitch_arguments_flipped_schema,
    three_merged_schema,
    union_merged_schema,
)


# The below namedtuple is used to check the structure of SubQueryNodes in tests
ExpectedQueryNode = namedtuple(
    "ExpectedQueryNode",
    (
        "query_str",
        "schema_id",
        "child_query_nodes_and_out_names",
        # List[Tuple[ExpectedQueryNode, str, str]]
        # child expected query node, parent out name, child out name
    ),
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
            self._check_query_node_edge(
                query_node, i, child_query_node, parent_out_name, child_out_name
            )
            # Recurse
            self._check_query_node_structure_helper(child_query_node, child_expected_query_node)

    def _check_query_node_edge(
        self,
        parent_query_node,
        parent_to_child_edge_index,
        child_query_node,
        parent_out_name,
        child_out_name,
    ):
        """Check the edge between parent and child is symmetric, with the right output names."""
        parent_to_child_connection = parent_query_node.child_query_connections[
            parent_to_child_edge_index
        ]
        child_to_parent_connection = child_query_node.parent_query_connection

        self.assertIs(parent_to_child_connection.sink_query_node, child_query_node)
        self.assertIs(child_to_parent_connection.sink_query_node, parent_query_node)
        self.assertEqual(parent_to_child_connection.source_field_out_name, parent_out_name)
        self.assertEqual(child_to_parent_connection.sink_field_out_name, parent_out_name)
        self.assertEqual(parent_to_child_connection.sink_field_out_name, child_out_name)
        self.assertEqual(child_to_parent_connection.source_field_out_name, child_out_name)

    def _get_intermediate_outputs_set(self, number_of_outputs):
        output_names = set(
            "__intermediate_output_" + str(count) for count in range(number_of_outputs)
        )
        return frozenset(output_names)

    def test_no_split(self):
        query_str = dedent(
            """\
            {
              Animal {
                name @output(out_name: "name")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=query_str, schema_id="first", child_query_nodes_and_out_names=[]
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(0))

    def test_no_existing_fields_split(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  age @output(out_name: "age")
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(2))

    def test_stitch_arguments_flipped(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  age @output(out_name: "age")
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(
            parse(query_str), stitch_arguments_flipped_schema
        )
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(2))

    def test_original_unmodified(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  age @output(out_name: "age")
                }
              }
            }
        """
        )
        query_ast = parse(query_str)
        split_query(query_ast, basic_merged_schema)
        self.assertEqual(query_ast, parse(query_str))

    def test_existing_output_field_in_parent(self):
        query_str = dedent(
            """\
            {
              Animal {
                uuid @output(out_name: "result")
                out_Animal_Creature {
                  age @output(out_name: "age")
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @output(out_name: "result")
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "result",
                    "__intermediate_output_0",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(1))

    def test_existing_output_field_in_child(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  id @output(out_name: "result")
                  age @output(out_name: "age")
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                id @output(out_name: "result")
                age @output(out_name: "age")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "result",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(1))

    def test_existing_field_in_both(self):
        query_str = dedent(
            """\
            {
              Animal {
                uuid @filter(op_name: "in_collection", value: ["$uuids"])
                out_Animal_Creature {
                  id @output(out_name: "result")
                  age @output(out_name: "age")
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @filter(op_name: "in_collection", value: ["$uuids"]) \
@output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                id @output(out_name: "result")
                age @output(out_name: "age")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "result",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(1))

    def test_nested_query(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_ParentOf {
                  color @output(out_name: "color")
                  out_Animal_Creature {
                    age @output(out_name: "age1")
                    friend {
                      age @output(out_name: "age2")
                    }
                  }
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                out_Animal_ParentOf {
                  color @output(out_name: "color")
                  uuid @output(out_name: "__intermediate_output_0")
                }
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age1")
                id @output(out_name: "__intermediate_output_1")
                friend {
                  age @output(out_name: "age2")
                }
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(2))

    def test_existing_optional_on_edge(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature @optional {
                  age @output(out_name: "age")
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @optional @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(2))

    def test_existing_optional_on_edge_and_field(self):
        query_str = dedent(
            """\
            {
              Animal {
                uuid @optional @filter(op_name: "=", value: ["$uuid_to_select"])
                out_Animal_Creature @optional {
                  age @output(out_name: "age")
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @optional @filter(op_name: "=", value: ["$uuid_to_select"]) \
@output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(2))

    def test_type_coercion_before_edge(self):
        query_str = dedent(
            """\
            {
              Entity {
                ... on Animal {
                  out_Animal_Creature {
                    age @output(out_name: "age")
                  }
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Entity {
                ... on Animal {
                  uuid @output(out_name: "__intermediate_output_0")
                }
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(2))

    def test_interface_type_coercion_after_edge(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  ... on Cat {
                    age @output(out_name: "age")
                  }
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Cat {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), interface_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(2))

    def test_union_type_coercion_after_edge(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  ... on Cat {
                    age @output(out_name: "age")
                  }
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Cat {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), union_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(2))

    def test_two_children_stitch_on_same_field(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  age @output(out_name: "age1")
                }
                out_Animal_ParentOf {
                  out_Animal_Creature {
                    age @output(out_name: "age2")
                  }
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @output(out_name: "__intermediate_output_0")
                out_Animal_ParentOf {
                  uuid @output(out_name: "__intermediate_output_2")
                }
              }
            }
        """
        )
        child_str1 = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age1")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        child_str2 = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age2")
                id @output(out_name: "__intermediate_output_3")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str1, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                ),
                (
                    ExpectedQueryNode(
                        query_str=child_str2, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_2",
                    "__intermediate_output_3",
                ),
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(4))

    def test_cross_schema_edge_field_after_normal_vertex_field(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_ParentOf {
                  color @output(out_name: "color")
                }
                out_Animal_Creature {
                  age @output(out_name: "age")
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                uuid @output(out_name: "__intermediate_output_0")
                out_Animal_ParentOf {
                  color @output(out_name: "color")
                }
              }
            }
        """
        )
        child_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                )
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(2))

    def test_two_edges_on_same_field_in_V(self):
        query_str = dedent(
            """\
            {
              Animal {
                name
                out_Animal_Creature {
                  age @output(out_name: "age")
                }
                out_Animal_Critter {
                  size @output(out_name: "size")
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Animal {
                name
                uuid @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child1_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        child2_str = dedent(
            """\
            {
              Critter {
                size @output(out_name: "size")
                ID @output(out_name: "__intermediate_output_2")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child1_str, schema_id="second", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                ),
                (
                    ExpectedQueryNode(
                        query_str=child2_str, schema_id="third", child_query_nodes_and_out_names=[]
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_2",
                ),
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), three_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(3))

    def test_two_edges_on_same_field_in_chain(self):
        query_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                in_Animal_Creature {
                  name @output(out_name: "name")
                  out_Animal_Critter {
                    size @output(out_name: "size")
                  }
                }
              }
            }
        """
        )
        parent_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        child1_str = dedent(
            """\
            {
              Animal {
                name @output(out_name: "name")
                uuid @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )

        child2_str = dedent(
            """\
            {
              Critter {
                size @output(out_name: "size")
                ID @output(out_name: "__intermediate_output_2")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=parent_str,
            schema_id="second",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=child1_str,
                        schema_id="first",
                        child_query_nodes_and_out_names=[
                            (
                                ExpectedQueryNode(
                                    query_str=child2_str,
                                    schema_id="third",
                                    child_query_nodes_and_out_names=[],
                                ),
                                "__intermediate_output_1",
                                "__intermediate_output_2",
                            )
                        ],
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                ),
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), three_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(3))

    def test_complex_query_structure(self):
        query_str = dedent(
            """\
            {
              Animal {
                color @output(out_name: "color")
                out_Animal_Creature {
                  age @output(out_name: "age")
                  in_Animal_Creature {
                    description @output(out_name: "description")
                  }
                  friend {
                    in_Animal_Creature {
                      description @output(out_name: "friend_description")
                    }
                  }
                }
              }
            }
        """
        )
        query_piece1_str = dedent(
            """\
            {
              Animal {
                color @output(out_name: "color")
                uuid @output(out_name: "__intermediate_output_0")
              }
            }
        """
        )
        query_piece2_str = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
                friend {
                  id @output(out_name: "__intermediate_output_3")
                }
              }
            }
        """
        )
        query_piece3_str = dedent(
            """\
            {
              Animal {
                description @output(out_name: "description")
                uuid @output(out_name: "__intermediate_output_2")
              }
            }
        """
        )
        query_piece4_str = dedent(
            """\
            {
              Animal {
                description @output(out_name: "friend_description")
                uuid @output(out_name: "__intermediate_output_4")
              }
            }
        """
        )
        expected_query_node = ExpectedQueryNode(
            query_str=query_piece1_str,
            schema_id="first",
            child_query_nodes_and_out_names=[
                (
                    ExpectedQueryNode(
                        query_str=query_piece2_str,
                        schema_id="second",
                        child_query_nodes_and_out_names=[
                            (
                                ExpectedQueryNode(
                                    query_str=query_piece3_str,
                                    schema_id="first",
                                    child_query_nodes_and_out_names=[],
                                ),
                                "__intermediate_output_1",
                                "__intermediate_output_2",
                            ),
                            (
                                ExpectedQueryNode(
                                    query_str=query_piece4_str,
                                    schema_id="first",
                                    child_query_nodes_and_out_names=[],
                                ),
                                "__intermediate_output_3",
                                "__intermediate_output_4",
                            ),
                        ],
                    ),
                    "__intermediate_output_0",
                    "__intermediate_output_1",
                ),
            ],
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        self._check_query_node_structure(query_node, expected_query_node)
        self.assertEqual(intermediate_outputs, self._get_intermediate_outputs_set(5))


class TestSplitQueryInvalidQuery(unittest.TestCase):
    def test_invalid_query_unsupported_directives(self):
        query_str = dedent(
            """\
            {
              Animal {
                color @tag(tag_name: "color")
                out_Animal_ParentOf {
                  color @filter(op_name: "=", value: ["%color"])
                        @output(out_name: "result")
                }
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            split_query(parse(query_str), basic_merged_schema)

        query_str = dedent(
            """\
            {
              Animal @fold {
                color @output(out_name: "result")
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            split_query(parse(query_str), basic_merged_schema)

        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_ParentOf @recurse(depth: 1) {
                  color @output(out_name: "result")
                }
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            split_query(parse(query_str), basic_merged_schema)

    def test_invalid_query_fails_builtin_validation(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  thing @output(out_name: "thing")
                }
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            split_query(parse(query_str), basic_merged_schema)

    def test_invalid_query_wrong_field_order(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_ParentOf {
                  name @output(out_name: "name")
                }
                color @output(out_name: "color")
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            split_query(parse(query_str), basic_merged_schema)

        query_str = dedent(
            """\
            {
              Entity {
                ... on Animal {
                  color @output(out_name: "color")
                }
                name @output(out_name: "name")
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            split_query(parse(query_str), basic_merged_schema)

    def test_invalid_query_inline_not_only_selection_in_scope(self):
        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  age @output(out_name: "age")
                  ... on Cat {
                    meow @output(out_name: "meow")
                  }
                }
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            split_query(parse(query_str), interface_merged_schema)

        query_str = dedent(
            """\
            {
              Animal {
                out_Animal_Creature {
                  ... on Cat {
                    meow @output(out_name: "meow")
                  }
                  ... on Dog {
                    bark @output(out_name: "bark")
                  }
                }
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            split_query(parse(query_str), interface_merged_schema)
