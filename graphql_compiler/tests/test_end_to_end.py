# Copyright 2017-present Kensho Technologies, LLC.
import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple, cast
import unittest

from graphql import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
    GraphQLString,
)
import six

from .. import graphql_to_gremlin, graphql_to_match
from ..compiler import compile_graphql_to_gremlin, compile_graphql_to_match
from ..exceptions import GraphQLInvalidArgumentError
from ..query_formatting import insert_arguments_into_query
from ..query_formatting.common import (
    deserialize_argument,
    deserialize_multiple_arguments,
    validate_argument_type,
)
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal, GraphQLSchemaFieldType
from ..schema.schema_info import CommonSchemaInfo
from ..typedefs import QueryArgumentGraphQLType
from .test_helpers import compare_gremlin, compare_match, get_schema


EXAMPLE_GRAPHQL_QUERY = """{
    Animal @filter(op_name: "name_or_alias", value: ["$wanted_name"]) {
        name @output(out_name: "name")
        net_worth @filter(op_name: ">=", value: ["$min_worth"])
    }
}"""


class QueryFormattingTests(unittest.TestCase):
    def test_correct_arguments(self) -> None:
        wanted_name = "Top Cat"
        min_worth = Decimal("123456789.0123456")
        expected_match = """
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
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (
                ((it.name == 'Top Cat') || it.alias.contains('Top Cat')) &&
                (it.net_worth >= 123456789.0123456G)
            )}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        """
        arguments = {
            "wanted_name": wanted_name,
            "min_worth": min_worth,
        }
        schema = get_schema()
        common_schema_info = CommonSchemaInfo(schema, None)

        actual_match = insert_arguments_into_query(
            compile_graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY), arguments
        )
        compare_match(self, expected_match, actual_match, parameterized=False)

        actual_match = graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY, arguments).query
        compare_match(self, expected_match, actual_match, parameterized=False)

        actual_gremlin = insert_arguments_into_query(
            compile_graphql_to_gremlin(common_schema_info, EXAMPLE_GRAPHQL_QUERY), arguments
        )
        compare_gremlin(self, expected_gremlin, actual_gremlin)

        actual_gremlin = graphql_to_gremlin(
            common_schema_info, EXAMPLE_GRAPHQL_QUERY, arguments
        ).query
        compare_gremlin(self, expected_gremlin, actual_gremlin)

    def test_missing_argument(self) -> None:
        schema = get_schema()
        common_schema_info = CommonSchemaInfo(schema, None)

        compiled_match_result = compile_graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(
            common_schema_info, EXAMPLE_GRAPHQL_QUERY
        )

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_match_result, {})

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY, {})

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_gremlin_result, {})

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_gremlin(common_schema_info, EXAMPLE_GRAPHQL_QUERY, {})

    def test_surplus_argument(self) -> None:
        schema = get_schema()
        common_schema_info = CommonSchemaInfo(schema, None)

        compiled_match_result = compile_graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(
            common_schema_info, EXAMPLE_GRAPHQL_QUERY
        )
        arguments = {"wanted_name": "Top Cat", "foobar": 123}

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_match_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_gremlin_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_gremlin(common_schema_info, EXAMPLE_GRAPHQL_QUERY, arguments)

    def test_misnamed_argument(self) -> None:
        schema = get_schema()
        common_schema_info = CommonSchemaInfo(schema, None)

        compiled_match_result = compile_graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(
            common_schema_info, EXAMPLE_GRAPHQL_QUERY
        )
        arguments = {"foobar": 123}

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_match_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_gremlin_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_gremlin(common_schema_info, EXAMPLE_GRAPHQL_QUERY, {})

    def test_wrong_argument_type(self) -> None:
        schema = get_schema()
        common_schema_info = CommonSchemaInfo(schema, None)

        compiled_match_result = compile_graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(
            common_schema_info, EXAMPLE_GRAPHQL_QUERY
        )

        wrong_argument_types: List[Dict[str, Any]] = [
            {"wanted_name": 123},
            {"wanted_name": ["abc", "def", "ghi"]},
            {"wanted_name": ["abc"]},
            {"wanted_name": None},
            {"wanted_name": [1, 2, 3]},
        ]

        for arguments in wrong_argument_types:
            with self.assertRaises(GraphQLInvalidArgumentError):
                insert_arguments_into_query(compiled_match_result, arguments)

            with self.assertRaises(GraphQLInvalidArgumentError):
                graphql_to_match(common_schema_info, EXAMPLE_GRAPHQL_QUERY, arguments)

            with self.assertRaises(GraphQLInvalidArgumentError):
                insert_arguments_into_query(compiled_gremlin_result, arguments)

            with self.assertRaises(GraphQLInvalidArgumentError):
                graphql_to_gremlin(common_schema_info, EXAMPLE_GRAPHQL_QUERY, {})

    def test_argument_types(self) -> None:
        valid_values_type = Tuple[Any, ...]
        invalid_values_type = Tuple[Any, ...]
        test_case_type = Tuple[GraphQLSchemaFieldType, valid_values_type, invalid_values_type]

        test_cases: Tuple[test_case_type, ...] = (
            (GraphQLString, ("asdf",), (4, 5.4, True)),
            (GraphQLID, ("13d72846-1777-6c3a-5743-5d9ced3032ed", "asf"), (4, 4.4, True)),
            (GraphQLFloat, (4.1, 4.0), ("4.3", 5)),
            (GraphQLInt, (3, 4), (4.0, 4.1, True, False, "4")),
            (
                GraphQLBoolean,
                (
                    True,
                    False,
                ),
                ("True", 0, 1, 0.4),
            ),
            (GraphQLDecimal, (Decimal(4), 0.4, 4), (True, "sdfsdf")),
            (
                GraphQLDate,
                (
                    datetime.date(2007, 12, 6),
                    datetime.date(2008, 12, 6),
                    datetime.date(2009, 12, 6),
                ),
                (
                    "2007-12-06",
                    datetime.datetime(2007, 12, 6, 16, 29, 43, 79043),
                ),
            ),
            (
                GraphQLDateTime,
                (
                    datetime.datetime(2007, 12, 6, 16, 29, 43, 79043),
                    datetime.datetime(2007, 12, 6),
                ),
                (
                    "2007-12-06T16:29:43",
                    datetime.date(2007, 12, 6),
                    datetime.datetime(2008, 12, 6, 16, 29, 43, 79043, tzinfo=datetime.timezone.utc),
                    datetime.datetime(
                        2009,
                        12,
                        6,
                        16,
                        29,
                        43,
                        79043,
                        tzinfo=datetime.timezone(datetime.timedelta(hours=-4), name="US/Eastern"),
                    ),
                ),
            ),
            (GraphQLList(GraphQLInt), ([], [1], [3, 5]), (4, ["a"], [1, "a"], [True])),
            (GraphQLList(GraphQLString), ([], ["a"]), (1, "a", ["a", 4])),
        )
        arbitrary_argument_name = "arbitrary_name"
        for graphql_type, valid_values, invalid_values in test_cases:
            for valid_value in valid_values:
                validate_argument_type(arbitrary_argument_name, graphql_type, valid_value)
            for invalid_value in invalid_values:
                with self.assertRaises(GraphQLInvalidArgumentError):
                    validate_argument_type(arbitrary_argument_name, graphql_type, invalid_value)

    def test_non_null_types_pass_validation(self) -> None:
        type_and_value: List[Tuple[QueryArgumentGraphQLType, Any]] = [
            (GraphQLString, "abc"),  # self-consistency check
            (GraphQLNonNull(GraphQLString), "abc"),
            (GraphQLList(GraphQLString), ["a", "b", "c"]),  # self-consistency check
            (GraphQLList(GraphQLNonNull(GraphQLString)), ["a", "b", "c"]),
            (GraphQLNonNull(GraphQLList(GraphQLString)), ["a", "b", "c"]),
            (GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLString))), ["a", "b", "c"]),
        ]

        arbitrary_argument_name = "arbitrary_name"
        for graphql_type, value in type_and_value:
            validate_argument_type(arbitrary_argument_name, graphql_type, value)

    def test_date_deserialization(self) -> None:
        # Invalid month
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("birthday", GraphQLDate, "2014-14-01")

        # Invalid day
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("birthday", GraphQLDate, "2014-02-31")

        # Valid date
        value = deserialize_argument("birthday", GraphQLDate, "2014-02-05")
        self.assertEqual(datetime.date(2014, 2, 5), value)

    def test_datetime_deserialization(self) -> None:
        # No time provided, but still acceptable with zero time components.
        value = deserialize_argument("birth_time", GraphQLDateTime, "2014-02-05")
        self.assertEqual(datetime.datetime(2014, 2, 5), value)

        # Time component with excess precision is truncated (not rounded!) down to microseconds.
        # This example has 7 decimal places, whereas Python supports a maximum of 6.
        value = deserialize_argument("birth_time", GraphQLDateTime, "2000-02-29T13:02:27.0018349")
        self.assertEqual(datetime.datetime(2000, 2, 29, 13, 2, 27, 1834), value)

        # Allow dates to be implicitly converted into datetimes, since this is a lossless,
        # widening conversion.
        value = deserialize_argument("birth_time", GraphQLDateTime, datetime.date(2000, 2, 29))
        self.assertEqual(datetime.datetime(2000, 2, 29), value)

        # With timezone
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("birth_time", GraphQLDateTime, "2014-02-05T03:20:55+00:00")

        # With alternate timezone format
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("birth_time", GraphQLDateTime, "2014-02-05T03:20:55Z")

        # Valid datetime
        value = deserialize_argument("birth_time", GraphQLDateTime, "2014-02-05T03:20:55")
        self.assertEqual(datetime.datetime(2014, 2, 5, 3, 20, 55), value)

    def test_float_deserialization(self) -> None:
        # Invalid string
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("amount", GraphQLFloat, "sdg")

        # Bool
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("amount", GraphQLFloat, True)

        # Valid string
        self.assertEqual(float(5), deserialize_argument("amount", GraphQLFloat, "5"))

        # Valid string with decimals
        self.assertEqual(float(5.1), deserialize_argument("amount", GraphQLFloat, "5.1"))

        # Valid int
        self.assertEqual(float(5), deserialize_argument("amount", GraphQLFloat, 5))

        # Valid float
        self.assertEqual(float(5), deserialize_argument("amount", GraphQLFloat, float(5)))

        # Valid float with comma
        self.assertEqual(float(5.1), deserialize_argument("amount", GraphQLFloat, float(5.1)))

    def test_id_deserialization(self) -> None:
        # Float
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("amount", GraphQLID, 5.3)

        # Int
        self.assertEqual("5", deserialize_argument("amount", GraphQLID, 5))

        # String
        self.assertEqual("5", deserialize_argument("amount", GraphQLID, "5"))

    def test_int_deserialization(self) -> None:
        # Int
        self.assertEqual(5, deserialize_argument("amount", GraphQLInt, 5))

        if six.PY3:
            # Long
            self.assertEqual(
                50000000000000000000000000000000000000000,
                deserialize_argument(
                    "amount", GraphQLInt, 50000000000000000000000000000000000000000
                ),
            )

            # Long string
            self.assertEqual(
                50000000000000000000000000000000000000000,
                deserialize_argument(
                    "amount", GraphQLInt, "50000000000000000000000000000000000000000"
                ),
            )

    def test_multiple_argument_deserialization(self) -> None:
        serialized_arguments = {
            "amount": 5,
            "birthday": "2014-02-05",
        }
        expected_types = {
            "amount": GraphQLInt,
            "birthday": GraphQLDate,
        }
        expected_deserialization = {
            "amount": 5,
            "birthday": datetime.date(2014, 2, 5),
        }
        self.assertEqual(
            expected_deserialization,
            deserialize_multiple_arguments(serialized_arguments, expected_types),
        )

    def test_invalid_directive_comparison(self) -> None:
        # This test will fail if the directive types in deserialize_argument are compared by
        # their python object reference instead of by their names.
        #
        # Note that parsed_graphql_datetime_type has a different python object reference than
        # GraphQLDateTime, but refers conceptually to the same GraphQL type.
        parsed_graphql_datetime_type = get_schema().get_type("DateTime")
        value = deserialize_argument(
            "birth_time",
            cast(GraphQLScalarType, parsed_graphql_datetime_type),
            "2014-02-05T03:20:55",
        )
        self.assertEqual(datetime.datetime(2014, 2, 5, 3, 20, 55), value)

    def test_deserialize_lists(self) -> None:
        # Non-collection
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("numbers", GraphQLList(GraphQLInt), 1)

        # Tuple
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("numbers", GraphQLList(GraphQLInt), (1, 2))

        # Second element is of unexpected kind.
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("numbers", GraphQLList(GraphQLInt), (1, 1.2, 3))

        # Second element is "unparseable".
        with self.assertRaises(GraphQLInvalidArgumentError):
            deserialize_argument("numbers", GraphQLList(GraphQLInt), (1, "asda", 3))

        # Basic
        self.assertEqual(
            [1.2, 2.3], deserialize_argument("numbers", GraphQLList(GraphQLFloat), [1.2, 2.3])
        )

        # With empty list
        self.assertEqual([], deserialize_argument("numbers", GraphQLList(GraphQLFloat), []))

        # With list with one element
        self.assertEqual([1.2], deserialize_argument("numbers", GraphQLList(GraphQLFloat), [1.2]))

        # With outer null wrapper.
        self.assertEqual(
            [1.2, 2.3],
            deserialize_argument("numbers", GraphQLNonNull(GraphQLList(GraphQLFloat)), [1.2, 2.3]),
        )

        # With inner null wrapper.
        self.assertEqual(
            [1.2, 2.3],
            deserialize_argument("numbers", GraphQLList(GraphQLNonNull(GraphQLFloat)), [1.2, 2.3]),
        )

        # With outer and inner null wrapper.
        self.assertEqual(
            [1.2, 2.3],
            deserialize_argument(
                "numbers", GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLFloat))), [1.2, 2.3]
            ),
        )

        # With custom scalar type
        self.assertEqual(
            [datetime.date(2014, 2, 5)],
            deserialize_argument("dates", GraphQLList(GraphQLDate), ["2014-02-05"]),
        )
