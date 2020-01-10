# Copyright 2017-present Kensho Technologies, LLC.
from textwrap import dedent
import unittest

from ..query_formatting.graphql_formatting import pretty_print_graphql


class GraphQLPrettyPrintTests(unittest.TestCase):
    def test_graphql_pretty_print_indentation(self) -> None:
        bad_query = """{
          Animal {
                  name @output(out_name: "name")
            }
        }"""

        four_space_output = dedent(
            """\
        {
            Animal {
                name @output(out_name: "name")
            }
        }
        """
        )

        two_space_output = dedent(
            """\
        {
          Animal {
            name @output(out_name: "name")
          }
        }
        """
        )
        self.assertEqual(four_space_output, pretty_print_graphql(bad_query))
        self.assertEqual(two_space_output, pretty_print_graphql(bad_query, use_four_spaces=False))

    def test_filter_directive_order(self) -> None:
        bad_query = """{
            Animal @filter(value: ["$name"], op_name: "name_or_alias") {
                uuid @filter(value: ["$max_uuid"], op_name: "<=")
                out_Entity_Related {
                  ...on Species{
                      name @output(out_name: "related_species")
                    }
                }
            }
        }"""

        expected_output = dedent(
            """\
        {
            Animal @filter(op_name: "name_or_alias", value: ["$name"]) {
                uuid @filter(op_name: "<=", value: ["$max_uuid"])
                out_Entity_Related {
                    ... on Species {
                        name @output(out_name: "related_species")
                    }
                }
            }
        }
        """
        )

        self.assertEqual(expected_output, pretty_print_graphql(bad_query))

    def test_args_not_in_schema(self) -> None:
        bad_query = """{
            Animal @filter(value: ["$name"], unknown_arg: "value", op_name: "name_or_alias") {
                uuid @filter(value: ["$max_uuid"], op_name: "<=")
                out_Entity_Related {
                  ...on Species{
                      name @output(out_name: "related_species")
                    }
                }
            }
        }"""

        expected_output = dedent(
            """\
        {
            Animal @filter(op_name: "name_or_alias", value: ["$name"], unknown_arg: "value") {
                uuid @filter(op_name: "<=", value: ["$max_uuid"])
                out_Entity_Related {
                    ... on Species {
                        name @output(out_name: "related_species")
                    }
                }
            }
        }
        """
        )

        self.assertEqual(expected_output, pretty_print_graphql(bad_query))

    def test_missing_args(self) -> None:
        bad_query = """{
            Animal @filter(value: ["$name"]) {
                uuid @filter(value: ["$max_uuid"], op_name: "<=")

                out_Entity_Related {
                  ...on Species{
                      name @output(out_name: "related_species")
                    }
                }
            }
        }"""

        expected_output = dedent(
            """\
        {
            Animal @filter(value: ["$name"]) {
                uuid @filter(op_name: "<=", value: ["$max_uuid"])
                out_Entity_Related {
                    ... on Species {
                        name @output(out_name: "related_species")
                    }
                }
            }
        }
        """
        )

        self.assertEqual(expected_output, pretty_print_graphql(bad_query))

    def test_other_directive(self) -> None:
        bad_query = """{
            Animal @filter(value: ["$name"]) {
                uuid @filter(value: ["$max_uuid"], op_name: "<=")

                out_Entity_Related @other(arg1: "val1", arg2: "val2") {
                  ...on Species{
                      name @output(out_name: "related_species")
                    }
                }
            }
        }"""

        expected_output = dedent(
            """\
        {
            Animal @filter(value: ["$name"]) {
                uuid @filter(op_name: "<=", value: ["$max_uuid"])
                out_Entity_Related @other(arg1: "val1", arg2: "val2") {
                    ... on Species {
                        name @output(out_name: "related_species")
                    }
                }
            }
        }
        """
        )

        self.assertEqual(expected_output, pretty_print_graphql(bad_query))
