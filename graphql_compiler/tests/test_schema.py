# Copyright 2017-present Kensho Technologies, LLC.
"""Tests that vet the test schema against the schema data in the package."""
from datetime import date, datetime
from decimal import Decimal
import unittest

from graphql.type import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString
from graphql.utils.schema_printer import print_schema
import pytz
import six

from .. import schema
from .test_helpers import get_schema


class SchemaTests(unittest.TestCase):
    def test_directives_match(self):
        # Directives don't currently implement an equality operator.
        # Instead, we will construct a fake schema, then print it and compare the directives'
        # string representation, which is standardized GraphQL and has to contain all their info.
        def _get_directives_in_string_form(directives):
            """Return a set of directives in their string form, from the native directive type."""
            fake_query_type = GraphQLObjectType('Query',
                                                fields={'foo': GraphQLField(GraphQLString)})
            fake_schema = GraphQLSchema(fake_query_type, directives=directives)

            schema_lines = [
                line.strip()
                for line in print_schema(fake_schema).split('\n')
            ]

            return {
                line
                for line in schema_lines
                if line.startswith('directive')
            }

        test_directives = _get_directives_in_string_form(get_schema().get_directives())
        actual_directives = _get_directives_in_string_form(schema.DIRECTIVES)
        self.assertEqual(test_directives, actual_directives)

    def test_decimal_serialization_and_parsing(self):
        test_data = {
            '0': Decimal(0),
            '123': Decimal(123),
            '-234': Decimal(-234),
            '-12345678.01234567': Decimal('-12345678.01234567'),
            '12345678.01234567': Decimal('12345678.01234567'),
            'Infinity': Decimal('Infinity'),
            '-Infinity': Decimal('-Infinity'),
        }

        for serialized_decimal, decimal_obj in six.iteritems(test_data):
            self.assertEqual(serialized_decimal, schema.GraphQLDecimal.serialize(decimal_obj))
            self.assertEqual(decimal_obj, schema.GraphQLDecimal.parse_value(serialized_decimal))

    def test_date_serialization_and_parsing(self):
        test_data = {
            '2017-01-01': date(2017, 1, 1),
            '2008-02-29': date(2008, 2, 29),
            '1991-12-31': date(1991, 12, 31),
        }

        for iso_date, date_obj in six.iteritems(test_data):
            self.assertEqual(iso_date, schema.GraphQLDate.serialize(date_obj))
            self.assertEqual(date_obj, schema.GraphQLDate.parse_value(iso_date))

    def test_datetime_serialization_and_parsing(self):
        eastern_us_tz = pytz.timezone('US/Eastern')
        central_eu_tz = pytz.timezone('Europe/Amsterdam')

        test_data = {
            # Timezone offsets.
            # N.B.: See the link below to understand why we use localize() to set the time zone.
            # http://stackoverflow.com/questions/26264897/time-zone-field-in-isoformat
            '2017-01-01T00:00:00+00:00': datetime(2017, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            '2017-01-01T00:00:00+01:00': central_eu_tz.localize(datetime(2017, 1, 1, 0, 0, 0)),
            '2017-01-01T00:00:00-05:00': eastern_us_tz.localize(datetime(2017, 1, 1, 0, 0, 0)),

            # Leap day.
            '2008-02-29T22:34:56+00:00': datetime(2008, 2, 29, 22, 34, 56, tzinfo=pytz.utc),

            # High numbers in all positions, except year and timezone.
            '1991-12-31T23:59:59+00:00': datetime(1991, 12, 31, 23, 59, 59, tzinfo=pytz.utc),
        }

        # Special case: a "Z" suffix == "00:00" timezone
        self.assertEqual(datetime(2017, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
                         schema.GraphQLDateTime.parse_value('2017-01-01T00:00:00Z'))

        for iso_datetime, datetime_obj in six.iteritems(test_data):
            self.assertEqual(iso_datetime, schema.GraphQLDateTime.serialize(datetime_obj))
            self.assertEqual(datetime_obj, schema.GraphQLDateTime.parse_value(iso_datetime))
