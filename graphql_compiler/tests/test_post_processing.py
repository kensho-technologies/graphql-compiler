# Copyright 2019-present Kensho Technologies, LLC.
import datetime
from unittest import TestCase

from dateutil.tz import tzoffset, tzutc
from graphql import GraphQLList, GraphQLString

from graphql_compiler import GraphQLDate, GraphQLDateTime, GraphQLDecimal

from ..compiler.compiler_frontend import OutputMetadata
from ..post_processing.sql_post_processing import post_process_mssql_folds
from .test_helpers import get_sqlalchemy_schema_info


class MssqlXmlPathTests(TestCase):
    def setUp(self) -> None:
        self.mssql_schema_info = get_sqlalchemy_schema_info(dialect="mssql")

    def test_convert_empty_string(self):
        """Test empty list is correctly decoded.

        {
            Animal {
                in_Animal_ParentOf @fold{
                    name @output(out_name: "child_names")
                }
            }
        }
        """
        query_output = [{"child_names": "",}]
        output_metadata = {
            "child_names": OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False, folded=True
            ),
        }
        expected_result = [{"child_names": []}]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_convert_basic(self):
        """Test basic XML path encoding (only pipe separations) is correctly decoded.

        {
            Animal {
                in_Animal_ParentOf @fold{
                    name @output(out_name: "child_names")
                }
            }
        }
        """
        query_output = [{"child_names": "|Animal 1|Animal 2||Animal 3|",}]
        output_metadata = {
            "child_names": OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False, folded=True
            ),
        }

        expected_result = [{"child_names": ["Animal 1", "Animal 2", "", "Animal 3", "",]}]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_covert_none_result(self):
        """Test "~" is properly decoded to None.

        {
            Animal {
                in_Animal_ParentOf @fold{
                    name @output(out_name: "child_names")
                }
            }
        }
        """
        query_output = [{"child_names": "|~|Animal 1|~",}]
        output_metadata = {
            "child_names": OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False, folded=True
            ),
        }

        expected_result = [{"child_names": [None, "Animal 1", None,]}]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_convert_caret_encodings(self):
        """Test pipe, tilde, and carets are correctly decoded.

        {
            Animal {
                in_Animal_ParentOf @fold{
                    name @output(out_name: "child_names")
                }
            }
        }
        """
        query_output = [
            {
                "child_names": "|name with a ^e (caret)|"
                "name with a ^d (pipe)|"
                "name with a ^n (tilde)|"
                "^emany^e^dcaret^nescaped^n^n^dname^e",
            }
        ]
        output_metadata = {
            "child_names": OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False, folded=True
            ),
        }

        expected_result = [
            {
                "child_names": [
                    "name with a ^ (caret)",
                    "name with a | (pipe)",
                    "name with a ~ (tilde)",
                    "^many^|caret~escaped~~|name^",
                ]
            }
        ]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_convert_ampersand_encodings(self):
        """Test ampersand, less than, and greater than are correctly decoded.

        {
            Animal {
                in_Animal_ParentOf @fold{
                    name @output(out_name: "child_names")
                }
            }
        }
        """
        query_output = [
            {
                "child_names": "|name with a &amp; (ampersand)|"
                "name with a &gt; (greater than)|"
                "name with a &lt; (less than)|"
                "&amp;many&amp;&gt;ampersand&lt;escaped&lt;&lt;&gt;name&amp;",
            }
        ]
        output_metadata = {
            "child_names": OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False, folded=True
            ),
        }

        expected_result = [
            {
                "child_names": [
                    "name with a & (ampersand)",
                    "name with a > (greater than)",
                    "name with a < (less than)",
                    "&many&>ampersand<escaped<<>name&",
                ]
            }
        ]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_convert_hex_encodings(self):
        """Test HTML hex encodings are properly decoded.

        {
            Animal {
                in_Animal_ParentOf @fold{
                    name @output(out_name: "child_names")
                }
            }
        }
        """
        query_output = [
            {
                "child_names": "|name with a &#x06; (acknowledge)|"
                "&#x0B;many&#x06;hex&#x0F;&#x07;name&#x08;",
            }
        ]
        output_metadata = {
            "child_names": OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False, folded=True
            ),
        }

        expected_result = [
            {"child_names": ["name with a \x06 (acknowledge)", "\x0Bmany\x06hex\x0F\x07name\x08",]}
        ]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_convert_basic_decimal(self):
        """Test basic XML path encoding for decimals is correctly decoded.

        {
            Animal {
                in_Animal_ParentOf @fold{
                    net_worth @output(out_name: "child_net_worths")
                }
            }
        }
        """
        query_output = [{"child_net_worths": "|500|1000|400|~",}]
        output_metadata = {
            "child_net_worths": OutputMetadata(
                type=GraphQLList(GraphQLDecimal), optional=False, folded=True
            )
        }

        expected_result = [{"child_net_worths": [500, 1000, 400, None,],}]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_convert_basic_date(self):
        """Test basic XML path encoding for dates is correctly decoded.

        {
            Animal {
                in_Animal_ParentOf @fold{
                    birthday @output(out_name: "child_birthdays")
                }
            }
        }
        """
        query_output = [{"child_birthdays": "|2020-01-01|2000-02-29|~"}]
        output_metadata = {
            "child_birthdays": OutputMetadata(
                type=GraphQLList(GraphQLDate), optional=False, folded=True
            )
        }

        expected_result = [
            {"child_birthdays": [datetime.date(2020, 1, 1), datetime.date(2000, 2, 29), None],}
        ]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_convert_basic_datetime(self):
        """Test basic XML path encoding for datetimes is correctly decoded.

        {
            Animal {
                in_Animal_ParentOf @fold{
                    datetime_field @output(out_name: "child_datetime_fields")
                }
            }
        }
        """
        query_output = [
            {"child_datetime_fields": "|2020-01-01T05:45:00+04:00|2000-02-29T13:02:27.0018349Z|~"}
        ]
        output_metadata = {
            "child_datetime_fields": OutputMetadata(
                type=GraphQLList(GraphQLDateTime), optional=False, folded=True
            )
        }

        expected_result = [
            {
                "child_datetime_fields": [
                    datetime.datetime(
                        2020, 1, 1, 5, 45, tzinfo=tzoffset(None, 14400)
                    ),  # 4 hours * 60 minutes/hour * 60 second/minutes = 14400
                    datetime.datetime(
                        2000, 2, 29, 13, 2, 27, 1835, tzinfo=tzutc()
                    ),  # with microsecond information
                    None,
                ],
            }
        ]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_convert_complex(self):
        """Test multiple folds, outputs, and types are correctly decoded.

        Note that multiple outputs inside a fold are not yet implemented.
        {
            Animal {
                in_Animal_ParentOf @fold{
                    birthday @output(out_name: "child_birthdays")
                    net_worth @output(out_name: "child_net_worths")
                    name @output(out_name: "child_names")
                }
                out_Animal_ParentOf @fold{
                    birthday @output(out_name: "parent_birthdays")
                    net_worth @output(out_name: "parent_net_worths")
                    name @output(out_name: "parent_names")
                }
            }
        }
        """
        query_output = [
            {
                "child_birthdays": "|2020-01-01|2000-02-29|~",
                "child_net_worths": "|200|~|321",
                "child_names": "|^ecomplex&amp;^d^nname&#x06;|~|simple name",
                "parent_birthdays": "",
                "parent_net_worths": "",
                "parent_names": "",
            }
        ]
        output_metadata = {
            "child_birthdays": OutputMetadata(
                type=GraphQLList(GraphQLDate), optional=False, folded=True
            ),
            "child_net_worths": OutputMetadata(
                type=GraphQLList(GraphQLDecimal), optional=False, folded=True
            ),
            "child_names": OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False, folded=True
            ),
            "parent_birthdays": OutputMetadata(
                type=GraphQLList(GraphQLDate), optional=False, folded=True
            ),
            "parent_net_worths": OutputMetadata(
                type=GraphQLList(GraphQLDecimal), optional=False, folded=True
            ),
            "parent_names": OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False, folded=True
            ),
        }

        expected_result = [
            {
                "child_birthdays": [datetime.date(2020, 1, 1), datetime.date(2000, 2, 29), None],
                "child_net_worths": [200, None, 321],
                "child_names": ["^complex&|~name\x06", None, "simple name"],
                "parent_birthdays": [],
                "parent_net_worths": [],
                "parent_names": [],
            }
        ]

        post_process_mssql_folds(query_output, output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_convert_invalid_result(self):
        """Test invalid result throws error.

                {
                    Animal {
                        in_Animal_ParentOf @fold{
                            name @output(out_name: "child_names")
                        }
                    }
                }
                """
        query_output = [{"child_names": "Animal 1|Animal 2||Animal 3|", }]
        output_metadata = {
            "child_names": OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False, folded=True
            ),
        }

        with self.assertRaises(AssertionError):
            post_process_mssql_folds(query_output, output_metadata)
