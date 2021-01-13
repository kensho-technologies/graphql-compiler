# Copyright 2017-present Kensho Technologies, LLC.
"""Tests that vet the test schema against the schema data in the package."""
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import re
import unittest

from graphql import build_ast_schema, parse
from graphql.type import GraphQLField, GraphQLInt, GraphQLObjectType, GraphQLSchema, GraphQLString
from graphql.utilities import print_schema
import six

from .. import schema
from .test_helpers import compare_ignoring_whitespace, get_schema


class SchemaTests(unittest.TestCase):
    def test_directives_match(self) -> None:
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

    def test_decimal_serialization_and_parsing(self) -> None:
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

    def test_date_serialization_and_parsing(self) -> None:
        test_data = {
            "2017-01-01": date(2017, 1, 1),
            "2008-02-29": date(2008, 2, 29),
            "1991-12-31": date(1991, 12, 31),
        }

        # Ensure that all the string representations parse as expected.
        for iso_date, date_obj in test_data.items():
            self.assertEqual(iso_date, schema.GraphQLDate.serialize(date_obj))
            self.assertEqual(date_obj, schema.GraphQLDate.parse_value(iso_date))

        # Ensure that parsing is the identity function for valid date objects.
        for date_obj in test_data.values():
            self.assertEqual(date_obj, schema.GraphQLDate.parse_value(date_obj))

    def test_datetime_serialization_and_parsing(self) -> None:
        test_data = {
            # Basic.
            "2017-01-01T00:00:00": datetime(2017, 1, 1, 0, 0, 0),
            # Leap day.
            "2008-02-29T22:34:56": datetime(2008, 2, 29, 22, 34, 56),
            # High numbers in all positions, except year and timezone.
            "1991-12-31T23:59:59": datetime(1991, 12, 31, 23, 59, 59),
            # Fractional seconds.
            "2021-01-06T12:55:32.123456": datetime(2021, 1, 6, 12, 55, 32, 123456),
        }

        # Ensure that all the string representations parse as expected.
        for iso_datetime, datetime_obj in test_data.items():
            self.assertEqual(iso_datetime, schema.GraphQLDateTime.serialize(datetime_obj))
            self.assertEqual(datetime_obj, schema.GraphQLDateTime.parse_value(iso_datetime))

        # Ensure that parsing is the identity function for valid datetime objects.
        for datetime_obj in test_data.values():
            self.assertEqual(datetime_obj, schema.GraphQLDateTime.parse_value(datetime_obj))

        # Special case:
        # Date inputs support an implicit widening conversion, so we allow it
        # since there is no loss of precision.
        self.assertEqual(
            datetime(2017, 1, 12), schema.GraphQLDateTime.parse_value(date(2017, 1, 12))
        )

        central_eu_tz = timezone(timedelta(hours=1), name="Europe/Amsterdam")
        invalid_parsing_inputs = {
            # Non-string, non-datetime.
            12345,
            # Timezone-aware datetime object.
            datetime(2017, 1, 1, 0, 0, 0, tzinfo=central_eu_tz),
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

        invalid_serialization_inputs = {
            # With UTC timezone.
            datetime(2017, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            # With non-UTC timezone.
            datetime(2017, 1, 1, 1, 0, 0, tzinfo=central_eu_tz),
        }

        for serialization_input in invalid_serialization_inputs:
            with self.assertRaises(ValueError):
                schema.GraphQLDateTime.parse_value(serialization_input)

    def test_meta_fields_from_constant(self) -> None:
        fields = schema.EXTENDED_META_FIELD_DEFINITIONS.copy()
        fields.update(
            OrderedDict(
                (
                    ("foo", GraphQLField(GraphQLString)),
                    ("bar", GraphQLField(GraphQLInt)),
                )
            )
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

    def test_meta_field_in_place_insertion(self) -> None:
        self.maxDiff = None

        # This is a real schema prefix, valid for use with GraphQL compiler.
        schema_unmodified_prefix = """\
schema {
    query: RootSchemaQuery
}

directive @filter(
    \"\"\"Name of the filter operation to perform.\"\"\"
    op_name: String!

    \"\"\"List of string operands for the operator.\"\"\"
    value: [String!]
) repeatable on FIELD | INLINE_FRAGMENT

directive @tag(
    \"\"\"Name to apply to the given property field.\"\"\"
    tag_name: String!
) on FIELD

directive @output(
    \"\"\"What to designate the output field generated from this property field.\"\"\"
    out_name: String!
) on FIELD

directive @output_source on FIELD

directive @optional on FIELD

directive @recurse(
    \"\"\"
    Recurse up to this many times on this edge. A depth of 1 produces the current \
vertex and its immediate neighbors along the given edge.
    \"\"\"
    depth: Int!
) on FIELD

directive @fold on FIELD

directive @macro_edge on FIELD_DEFINITION

directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

\"\"\"
The `Date` scalar type represents day-accuracy date objects.Values are
serialized following the ISO-8601 datetime format specification, for example
"2017-03-21". The year, month and day fields must be included, and the format
followed exactly, or the behavior is undefined.
\"\"\"
scalar Date

\"\"\"
The `DateTime` scalar type represents timezone-naive second-accuracy
timestamps.Values are serialized following the ISO-8601 datetime format
specification, for example "2017-03-21T12:34:56". All of these fields must
be included, including the seconds, and the format followed
exactly, or the behavior is undefined.
\"\"\"
scalar DateTime

\"\"\"
The `Decimal` scalar type is an arbitrary-precision decimal number object useful
for representing values that should never be rounded, such as currency amounts.
Values are allowed to be transported as either a native Decimal type, if the
underlying transport allows that, or serialized as strings in decimal format,
without thousands separators and using a "." as the decimal separator: for
example, "12345678.012345".
\"\"\"
scalar Decimal
"""

        # N.B.: Make sure that any type names used here come lexicographically after "Decimal".
        #       Otherwise, due to the alphabetical order of types shown in the schema, the test
        #       may break, or the test code that generates the expected output might get complex.
        original_schema_text = (
            schema_unmodified_prefix
            + """\
interface FooInterface {
    field1: Int
}

type RealFoo implements FooInterface {
    field1: Int
    field2: String
}

type RootSchemaQuery {
    FooInterface: [FooInterface]
    RealFoo: [RealFoo]
}
"""
        )

        expected_final_schema_text = (
            schema_unmodified_prefix
            + """\
interface FooInterface {
    field1: Int
    _x_count: Int
}

type RealFoo implements FooInterface {
    field1: Int
    field2: String
    _x_count: Int
}

type RootSchemaQuery {
    FooInterface: [FooInterface]
    RealFoo: [RealFoo]
}
"""
        )

        graphql_schema = build_ast_schema(parse(original_schema_text))

        schema.insert_meta_fields_into_existing_schema(graphql_schema)

        actual_final_schema_text = print_schema(graphql_schema)
        compare_ignoring_whitespace(
            self, expected_final_schema_text, actual_final_schema_text, None
        )
