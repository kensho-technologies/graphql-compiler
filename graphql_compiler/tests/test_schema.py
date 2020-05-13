# Copyright 2017-present Kensho Technologies, LLC.
"""Tests that vet the test schema against the schema data in the package."""
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
import re
import unittest

from graphql.type import GraphQLField, GraphQLInt, GraphQLObjectType, GraphQLSchema, GraphQLString
from graphql.utilities.schema_printer import print_schema
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
            fake_query_type = GraphQLObjectType(
                "Query", fields={"foo": GraphQLField(GraphQLString)}
            )
            fake_schema = GraphQLSchema(fake_query_type, directives=directives)

            # Split schema on double line breaks where the following character is not a space.
            # It is not possible to simply split on double line breaks because print_schema puts a
            # double line break between GraphQLArguments. The not space character is retained and
            # reattached to the rest of the line.
            split_schema_lines = [
                line.strip() for line in re.split("\n\n([^ ])", print_schema(fake_schema))
            ]

            # Reattach the delimiter's character to the rest of the line. The first line does
            # not have a separated character from regular expression splitting.
            schema_lines = [split_schema_lines[0]] + [
                delimiter_character + line
                for delimiter_character, line in zip(
                    split_schema_lines[1::2], split_schema_lines[2::2]
                )
            ]

            return {line for line in schema_lines if line.startswith("directive")}

        test_directives = _get_directives_in_string_form(get_schema().directives)
        actual_directives = _get_directives_in_string_form(schema.DIRECTIVES)
        self.assertEqual(test_directives, actual_directives)

    def test_decimal_serialization_and_parsing(self):
        test_data = {
            "0": Decimal(0),
            "123": Decimal(123),
            "-234": Decimal(-234),
            "-12345678.01234567": Decimal("-12345678.01234567"),
            "12345678.01234567": Decimal("12345678.01234567"),
            "Infinity": Decimal("Infinity"),
            "-Infinity": Decimal("-Infinity"),
        }

        for serialized_decimal, decimal_obj in six.iteritems(test_data):
            self.assertEqual(serialized_decimal, schema.GraphQLDecimal.serialize(decimal_obj))
            self.assertEqual(decimal_obj, schema.GraphQLDecimal.parse_value(serialized_decimal))

    def test_date_serialization_and_parsing(self):
        test_data = {
            "2017-01-01": date(2017, 1, 1),
            "2008-02-29": date(2008, 2, 29),
            "1991-12-31": date(1991, 12, 31),
        }

        for iso_date, date_obj in six.iteritems(test_data):
            self.assertEqual(iso_date, schema.GraphQLDate.serialize(date_obj))
            self.assertEqual(date_obj, schema.GraphQLDate.parse_value(iso_date))

    def test_datetime_serialization_and_parsing(self):
        test_data = {
            # Basic.
            "2017-01-01T00:00:00": datetime(2017, 1, 1, 0, 0, 0),
            # Leap day.
            "2008-02-29T22:34:56": datetime(2008, 2, 29, 22, 34, 56),
            # High numbers in all positions, except year and timezone.
            "1991-12-31T23:59:59": datetime(1991, 12, 31, 23, 59, 59),
        }

        for iso_datetime, datetime_obj in six.iteritems(test_data):
            self.assertEqual(iso_datetime, schema.GraphQLDateTime.serialize(datetime_obj))
            self.assertEqual(datetime_obj, schema.GraphQLDateTime.parse_value(iso_datetime))

        invalid_parsing_inputs = {
            # Non-string.
            datetime(2017, 1, 1, 0, 0, 0),
            # Including utc offset.
            "2017-01-01T00:00:00+01:00",
            # Zero utc offset.
            "2017-01-01T00:00:00+00:00",
            # Alternate format that indicates zero utc offset.
            "2017-01-01T00:00:00+00:00Z",
        }

        for parsing_input in invalid_parsing_inputs:
            with self.assertRaises(ValueError):
                schema.GraphQLDateTime.parse_value(parsing_input)

        central_eu_tz = pytz.timezone("Europe/Amsterdam")
        invalid_serialization_inputs = {
            # With UTC timezone.
            datetime(2017, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            # With non-UTC timezone.
            # N.B.: See the link below to understand why we use localize() to set the time zone.
            # http://stackoverflow.com/questions/26264897/time-zone-field-in-isoformat
            central_eu_tz.localize(datetime(2017, 1, 1, 0, 0, 0)),
            # Date instead of datetime.
            date(2017, 1, 1),
        }

        for serialization_input in invalid_serialization_inputs:
            with self.assertRaises(ValueError):
                schema.GraphQLDateTime.parse_value(serialization_input)

    def test_meta_fields_from_constant(self):
        fields = schema.EXTENDED_META_FIELD_DEFINITIONS.copy()
        fields.update(
            OrderedDict((("foo", GraphQLField(GraphQLString)), ("bar", GraphQLField(GraphQLInt)),))
        )
        graphql_type = GraphQLObjectType("MyType", fields)
        custom_schema = GraphQLSchema(graphql_type, directives=schema.DIRECTIVES)

        # Ensure that stringifying and parsing this schema works just fine.
        printed_schema = print_schema(custom_schema)
        expected_type_definition = """\
type MyType {
    _x_count: Int
    foo: String
    bar: Int
}""".replace(
            "    ", "  "
        )  # 2 space indentation instead of 4 spaces
        self.assertIn(expected_type_definition, printed_schema)
