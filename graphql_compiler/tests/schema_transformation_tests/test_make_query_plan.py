# Copyright 2019-present Kensho Technologies, LLC.
from textwrap import dedent
import unittest

from graphql import parse, print_ast

from ...schema_transformation.make_query_plan import make_query_plan
from ...schema_transformation.split_query import split_query
from .example_schema import basic_merged_schema


class TestMakeQueryPlan(unittest.TestCase):
    def test_basic_make_query_plan(self):
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
        child_str_no_filter = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1")
              }
            }
        """
        )
        child_str_with_filter = dedent(
            """\
            {
              Creature {
                age @output(out_name: "age")
                id @output(out_name: "__intermediate_output_1") \
@filter(op_name: "in_collection", value: ["$__intermediate_output_0"])
              }
            }
        """
        )
        query_node, intermediate_outputs = split_query(parse(query_str), basic_merged_schema)
        query_plan_descriptor = make_query_plan(query_node, intermediate_outputs)
        # Check the child ASTs in the input query node are unchanged (@filter not added))
        child_query_node = query_node.child_query_connections[0].sink_query_node
        self.assertEqual(print_ast(child_query_node.query_ast), child_str_no_filter)
        # Check the query plan
        parent_sub_query_plan = query_plan_descriptor.root_sub_query_plan
        self.assertEqual(print_ast(parent_sub_query_plan.query_ast), parent_str)
        self.assertEqual(parent_sub_query_plan.schema_id, "first")
        self.assertIsNone(parent_sub_query_plan.parent_query_plan)
        self.assertEqual(len(parent_sub_query_plan.child_query_plans), 1)
        # Check the child query plan
        child_sub_query_plan = parent_sub_query_plan.child_query_plans[0]
        self.assertEqual(print_ast(child_sub_query_plan.query_ast), child_str_with_filter)
        self.assertEqual(child_sub_query_plan.schema_id, "second")
        self.assertIs(child_sub_query_plan.parent_query_plan, parent_sub_query_plan)
        self.assertEqual(len(child_sub_query_plan.child_query_plans), 0)
        # Check the output join descriptors
        output_join_descriptors = query_plan_descriptor.output_join_descriptors
        self.assertEqual(len(output_join_descriptors), 1)
        output_join_descriptor = output_join_descriptors[0]
        self.assertEqual(
            output_join_descriptor.output_names,
            ("__intermediate_output_0", "__intermediate_output_1"),
        )
        # Check set of intermediate output names
        self.assertEqual(
            query_plan_descriptor.intermediate_output_names,
            {"__intermediate_output_0", "__intermediate_output_1"},
        )
