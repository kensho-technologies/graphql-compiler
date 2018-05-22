# Copyright 2017-present Kensho Technologies, LLC.
from datetime import date, datetime
import unittest

import arrow
from graphql import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import pytz
import six

from ..exceptions import GraphQLInvalidArgumentError
from ..query_formatting.gremlin_formatting import _safe_gremlin_argument
from ..query_formatting.match_formatting import _safe_match_argument
from ..schema import GraphQLDate, GraphQLDateTime


REPRESENTATIVE_DATA_FOR_EACH_TYPE = {
    # Not including GraphQLID since it can be a string or an int,
    # and is implicitly coerced to a string by the GraphQL library.
    GraphQLBoolean: True,
    GraphQLFloat: 3.14159,
    GraphQLInt: 42,
    GraphQLString: 'foobar',

    GraphQLDate: date(2017, 3, 22),
    GraphQLDateTime: datetime(2017, 3, 22, 9, 54, 35, tzinfo=pytz.utc),

    GraphQLList(GraphQLString): ['foo', 'bar', 'baz'],
    GraphQLList(GraphQLInt): [1, 2, 3, 4, 5],
    GraphQLList(GraphQLDate): [date(2017, 1, 22), date(2017, 1, 23), date(2017, 1, 24)],
    GraphQLList(GraphQLDateTime): [
        datetime(2017, 1, 22, 9, 54, 35, tzinfo=pytz.utc),
        arrow.get(2017, 1, 23, 9, 54, 35, tzinfo=pytz.utc),
        arrow.get(datetime(2017, 1, 24, 9, 54, 35, tzinfo=pytz.utc)),
    ]
}


class SafeMatchFormattingTests(unittest.TestCase):
    def test_safe_match_argument_for_strings(self):
        test_data = {
            u'': u'""',
            u'foobar': u'"foobar"',

            u'\'leading-single-quote': u'"\'leading-single-quote"',
            u'mid-single-\'-quote': u'"mid-single-\'-quote"',
            u'trailing-single-quote\'': u'"trailing-single-quote\'"',
            u'unicode-single-quote: \u0027': u'"unicode-single-quote: \'"',

            u'"leading-double-quote': u'"\\"leading-double-quote"',
            u'mid-double-"-quote': u'"mid-double-\\"-quote"',
            u'trailing-double-quote"': u'"trailing-double-quote\\""',
            u'unicode-double-quote: \u0022': u'"unicode-double-quote: \\""',

            u'unicode-snowman: \u2603': u'"unicode-snowman: \\u2603"',
            u'backslashes: \\': u'"backslashes: \\\\"',
            u'tab-and-newline: \t\n': u'"tab-and-newline: \\t\\n"',

            # There's no opportunity for injection here, since double-quoted strings
            # are not interpolated in MATCH / SQL as they are in Gremlin / Groovy.
            u'injection: ${ -> (2 + 2 == 4)}': u'"injection: ${ -> (2 + 2 == 4)}"',
        }

        for input_data, expected_value in six.iteritems(test_data):
            unicode_string = input_data
            bytes_string = input_data.encode('utf-8')

            # String type
            self.assertEqual(expected_value, _safe_match_argument(GraphQLString, unicode_string))
            self.assertEqual(expected_value, _safe_match_argument(GraphQLString, bytes_string))

            # ID type -- IDs can be strings
            self.assertEqual(expected_value, _safe_match_argument(GraphQLID, unicode_string))
            self.assertEqual(expected_value, _safe_match_argument(GraphQLID, bytes_string))

    def test_incorrect_graphql_type_causes_errors(self):
        for correct_graphql_type, value in six.iteritems(REPRESENTATIVE_DATA_FOR_EACH_TYPE):
            for other_graphql_type in six.iterkeys(REPRESENTATIVE_DATA_FOR_EACH_TYPE):
                if correct_graphql_type.is_same_type(other_graphql_type):
                    # No error -- GraphQL type is correct.
                    _safe_match_argument(correct_graphql_type, value)
                else:
                    # Error -- incorrect GraphQL type specified.
                    with self.assertRaises(GraphQLInvalidArgumentError):
                        _safe_match_argument(other_graphql_type, value)

    def test_nested_lists_are_disallowed(self):
        value = [[1, 2, 3], [4, 5, 6]]
        graphql_type = GraphQLList(GraphQLList(GraphQLInt))
        with self.assertRaises(GraphQLInvalidArgumentError):
            _safe_match_argument(graphql_type, value)


class SafeGremlinFormattingTests(unittest.TestCase):
    def test_safe_gremlin_argument_for_strings(self):
        test_data = {
            u'': u"''",                                                       # noqa
            u'foobar': u"'foobar'",                                           # noqa

            u'\'leading-single-quote': u"'\\'leading-single-quote'",          # noqa
            u'mid-single-\'-quote': u"'mid-single-\\'-quote'",                # noqa
            u'trailing-single-quote\'': u"'trailing-single-quote\\''",        # noqa
            u'unicode-single-quote: \u0027': u"'unicode-single-quote: \\''",  # noqa

            u'"leading-double-quote': u'\'"leading-double-quote\'',
            u'mid-double-"-quote': u'\'mid-double-"-quote\'',
            u'trailing-double-quote"': u'\'trailing-double-quote"\'',
            u'unicode-double-quote: \u0022': u'\'unicode-double-quote: "\'',

            u'unicode-snowman: \u2603': u"'unicode-snowman: \\u2603'",        # noqa
            u'backslashes: \\': u"'backslashes: \\\\'",                       # noqa
            u'tab-and-newline: \t\n': u"'tab-and-newline: \\t\\n'",           # noqa

            # The injection is unsuccessful, since the output is a single-quoted string literal.
            # No additional escaping of dollar signs is required, since single-quoted strings
            # are not interpolated -- only double-quoted strings are interpolated.
            u'injection: ${ -> (2 + 2 == 4)}': u"'injection: ${ -> (2 + 2 == 4)}'",  # noqa
        }

        for input_data, expected_value in six.iteritems(test_data):
            unicode_string = input_data
            bytes_string = input_data.encode('utf-8')

            # String type
            self.assertEqual(expected_value, _safe_gremlin_argument(GraphQLString, unicode_string))
            self.assertEqual(expected_value, _safe_gremlin_argument(GraphQLString, bytes_string))

            # ID type -- IDs can be strings
            self.assertEqual(expected_value, _safe_gremlin_argument(GraphQLID, unicode_string))
            self.assertEqual(expected_value, _safe_gremlin_argument(GraphQLID, bytes_string))

    def test_incorrect_graphql_type_causes_errors(self):
        for correct_graphql_type, value in six.iteritems(REPRESENTATIVE_DATA_FOR_EACH_TYPE):
            for other_graphql_type in six.iterkeys(REPRESENTATIVE_DATA_FOR_EACH_TYPE):
                if correct_graphql_type.is_same_type(other_graphql_type):
                    # No error -- GraphQL type is correct.
                    _safe_gremlin_argument(correct_graphql_type, value)
                else:
                    # Error -- incorrect GraphQL type specified.
                    with self.assertRaises(GraphQLInvalidArgumentError):
                        _safe_gremlin_argument(other_graphql_type, value)

    def test_nested_lists_are_serialized_correctly(self):
        value = [[1, 2, 3], [4, 5, 6]]
        graphql_type = GraphQLList(GraphQLList(GraphQLInt))

        expected_output = u'[[1,2,3],[4,5,6]]'
        self.assertEqual(expected_output, _safe_gremlin_argument(graphql_type, value))
