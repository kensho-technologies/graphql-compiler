# Copyright 2017-present Kensho Technologies, LLC.
import datetime
from decimal import Decimal
import unittest

from graphql import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import pytz

from .. import graphql_to_gremlin, graphql_to_match
from ..compiler import compile_graphql_to_gremlin, compile_graphql_to_match
from ..exceptions import GraphQLInvalidArgumentError
from ..query_formatting import insert_arguments_into_query
from ..query_formatting.common import validate_argument_type
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
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

    def test_argument_types(self):
        test_cases = (
            (GraphQLString, ('asdf',), (4, 5.4, True)),
            (GraphQLID, ('13d72846-1777-6c3a-5743-5d9ced3032ed', 'asf'), (4, 4.4, True)),
            (GraphQLFloat, (4.1, 4.0), ('4.3', 5)),
            (GraphQLInt, (3, 4), (4.0, 4.1, True, False, '4')),
            (GraphQLBoolean, (True, False,), ('True', 0, 1, 0.4)),
            (GraphQLDecimal, (Decimal(4), 0.4, 4), (True, 'sdfsdf')),
            (
                GraphQLDate, (
                    datetime.date(2007, 12, 6),
                    datetime.date(2008, 12, 6),
                    datetime.date(2009, 12, 6),
                ), (
                    '2007-12-06',
                    datetime.datetime(2007, 12, 6, 16, 29, 43, 79043),
                )
            ),
            (
                GraphQLDateTime, (
                    datetime.datetime(2007, 12, 6, 16, 29, 43, 79043),
                    datetime.datetime(2008, 12, 6, 16, 29, 43, 79043, tzinfo=pytz.utc),
                    datetime.datetime(2009, 12, 6, 16, 29, 43, 79043,
                                      tzinfo=pytz.timezone('US/Eastern')),
                    datetime.datetime(2007, 12, 6),
                ), (
                    '2007-12-06 16:29:43',
                    datetime.date(2007, 12, 6),
                )
            ),
            (GraphQLList(GraphQLInt), ([], [1], [3, 5]), (4, ['a'], [1, 'a'], [True])),
            (GraphQLList(GraphQLString), ([], ['a']), (1, 'a', ['a', 4])),
        )
        for graphql_type, valid_values, invalid_values in test_cases:
            for valid_value in valid_values:
                validate_argument_type(graphql_type, valid_value)
            for invalid_value in invalid_values:
                with self.assertRaises(GraphQLInvalidArgumentError):
                    validate_argument_type(graphql_type, invalid_value)
