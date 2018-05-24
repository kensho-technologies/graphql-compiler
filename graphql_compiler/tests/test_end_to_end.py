# Copyright 2017-present Kensho Technologies, LLC.
from decimal import Decimal
import unittest

from .. import graphql_to_gremlin, graphql_to_match
from ..compiler import compile_graphql_to_gremlin, compile_graphql_to_match
from ..exceptions import GraphQLInvalidArgumentError
from ..query_formatting import insert_arguments_into_query
from .test_helpers import compare_gremlin, compare_match, get_schema


EXAMPLE_GRAPHQL_QUERY = '''{
    Animal @filter(op_name: "name_or_alias", value: ["$wanted_name"]) {
        name @output(out_name: "name")
        net_worth @filter(op_name: ">=", value: ["$min_worth"])
    }
}'''


class QueryFormattingTests(unittest.TestCase):
    def test_correct_arguments(self):
        wanted_name = 'Top Cat'
        min_worth = Decimal('123456789.0123456')
        expected_match = '''
            SELECT Animal___1.name AS `name` FROM (
                MATCH {
                    class: Animal,
                    where: ((
                        ((name = "Top Cat") OR (alias CONTAINS "Top Cat")) AND
                        (net_worth >= decimal("123456789.0123456"))
                    )),
                    as: Animal___1
                } RETURN $matches
            )
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> (
                ((it.name == 'Top Cat') || it.alias.contains('Top Cat')) &&
                (it.net_worth >= 123456789.0123456G)
            )}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        '''
        arguments = {
            'wanted_name': wanted_name,
            'min_worth': min_worth,
        }
        schema = get_schema()

        actual_match = insert_arguments_into_query(
            compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY), arguments)
        compare_match(self, expected_match, actual_match, parameterized=False)

        actual_match = graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, arguments).query
        compare_match(self, expected_match, actual_match, parameterized=False)

        actual_gremlin = insert_arguments_into_query(
            compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY), arguments)
        compare_gremlin(self, expected_gremlin, actual_gremlin)

        actual_gremlin = graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, arguments).query
        compare_gremlin(self, expected_gremlin, actual_gremlin)

    def test_missing_argument(self):
        schema = get_schema()
        compiled_match_result = compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY)

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_match_result, {})

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, {})

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_gremlin_result, {})

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, {})

    def test_surplus_argument(self):
        schema = get_schema()
        compiled_match_result = compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY)
        arguments = {
            'wanted_name': 'Top Cat',
            'foobar': 123
        }

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_match_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_gremlin_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, arguments)

    def test_misnamed_argument(self):
        schema = get_schema()
        compiled_match_result = compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY)
        arguments = {
            'foobar': 123
        }

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_match_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_gremlin_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, {})

    def test_wrong_argument_type(self):
        schema = get_schema()
        compiled_match_result = compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY)

        wrong_argument_types = [
            {
                'wanted_name': 123
            }, {
                'wanted_name': ['abc', 'def', 'ghi']
            }, {
                'wanted_name': ['abc']
            }, {
                'wanted_name': None
            }, {
                'wanted_name': [1, 2, 3]
            }
        ]

        for arguments in wrong_argument_types:
            with self.assertRaises(GraphQLInvalidArgumentError):
                insert_arguments_into_query(compiled_match_result, arguments)

            with self.assertRaises(GraphQLInvalidArgumentError):
                graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, arguments)

            with self.assertRaises(GraphQLInvalidArgumentError):
                insert_arguments_into_query(compiled_gremlin_result, arguments)

            with self.assertRaises(GraphQLInvalidArgumentError):
                graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, {})
