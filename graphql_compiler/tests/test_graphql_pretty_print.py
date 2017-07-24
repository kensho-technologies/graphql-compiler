# Copyright 2017 Kensho Technologies, Inc.
import unittest

from ..query_formatting.graphql_formatting import pretty_print_graphql


class GraphQLPrettyPrintTests(unittest.TestCase):
    def test_graphql_pretty_print_indentation(self):
        bad_query = '''{
          Animal {
                  name @output(out_name: "name")
            }
        }'''

        # indentation starts at 0
        four_space_output = '''{
    Animal {
        name @output(out_name: "name")
    }
}
'''

        two_space_output = '''{
  Animal {
    name @output(out_name: "name")
  }
}
'''
        self.assertEquals(four_space_output, pretty_print_graphql(bad_query))
        self.assertEquals(two_space_output, pretty_print_graphql(bad_query, use_four_spaces=False))

    def test_filter_directive_order(self):
        bad_query = '''{
            Animal @filter(value: ["$name"], op_name: "name_or_alias"){
                uuid @filter(value: ["$max_uuid"], op_name: "<=")


                out_Entity_Related {
                  ...on Species{
                      name @output(out_name: "related_species")
                    }
                }
            }
        }'''

        expected_output = '''{
    Animal @filter(op_name: "name_or_alias", value: ["$name"]) {
        uuid @filter(op_name: "<=", value: ["$max_uuid"])
        out_Entity_Related {
            ... on Species {
                name @output(out_name: "related_species")
            }
        }
    }
}
'''

        self.assertEquals(expected_output, pretty_print_graphql(bad_query))
