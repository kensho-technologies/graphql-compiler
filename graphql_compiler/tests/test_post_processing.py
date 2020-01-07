# Copyright 2019-present Kensho Technologies, LLC.
import datetime
from unittest import TestCase

from graphql import GraphQLList, GraphQLString

from ..compiler.compiler_frontend import OutputMetadata
from ..post_processing.sql_post_processing import post_process_mssql_folds
from .test_helpers import get_sqlalchemy_schema_info


class MssqlXmlPathTests(TestCase):
    def setUp(self) -> None:
        self.mssql_schema_info = get_sqlalchemy_schema_info(dialect="mssql")

    def test_convert_empty_string(self):
        """Test empty list is correctly decoded."""
        query_output = [{"child_names": "",}]
        graphql_query = """{
                    Animal {
                        in_Animal_ParentOf @fold{
                            name @output(out_name: "child_names")
                        }
                    }
                }"""

        expected_result = [{"child_names": []}]

        post_process_mssql_folds(self.mssql_schema_info, graphql_query, query_output)
        self.assertEqual(query_output, expected_result)

    def test_convert_basic(self):
        """Test basic XML path encoding (only pipe separations) is correctly decoded."""
        query_output = [{"child_names": "Animal 1|Animal 2||Animal 3|",}]
        graphql_query = """{
            Animal {
                in_Animal_ParentOf @fold{
                    name @output(out_name: "child_names")
                }
            }
        }"""

        expected_result = [{"child_names": ["Animal 1", "Animal 2", "", "Animal 3", "",]}]

        expected_output_metadata = {
            "child_names": OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
        }

        post_process_mssql_folds(graphql_query, query_output, expected_output_metadata)
        self.assertEqual(query_output, expected_result)

    def test_covert_none_result(self):
        """Test "~" is properly decoded to None."""
        query_output = [{"child_names": "~|Animal 1|~",}]
        graphql_query = """{
                    Animal {
                        in_Animal_ParentOf @fold{
                            name @output(out_name: "child_names")
                        }
                    }
                }"""

        expected_result = [{"child_names": [None, "Animal 1", None,]}]

        post_process_mssql_folds(self.mssql_schema_info, graphql_query, query_output)
        self.assertEqual(query_output, expected_result)

    def test_convert_caret_encodings(self):
        """Test pipe, tilde, and carets are correctly decoded."""
        query_output = [
            {
                "child_names": "name with a ^e (caret)|"
                "name with a ^d (pipe)|"
                "name with a ^n (tilde)|"
                "^emany^e^dcaret^nescaped^n^n^dname^e",
            }
        ]
        graphql_query = """{
                    Animal {
                        in_Animal_ParentOf @fold{
                            name @output(out_name: "child_names")
                        }
                    }
                }"""

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

        post_process_mssql_folds(self.mssql_schema_info, graphql_query, query_output)
        self.assertEqual(query_output, expected_result)

    def test_convert_ampersand_encodings(self):
        """Test ampersand, less than, and greater than are correctly decoded."""
        query_output = [
            {
                "child_names": "name with a &amp; (ampersand)|"
                "name with a &gt; (greater than)|"
                "name with a &lt; (less than)|"
                "&amp;many&amp;&gt;ampersand&lt;escaped&lt;&lt;&gt;name&amp;",
            }
        ]
        graphql_query = """{
                            Animal {
                                in_Animal_ParentOf @fold{
                                    name @output(out_name: "child_names")
                                }
                            }
                        }"""

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

        post_process_mssql_folds(self.mssql_schema_info, graphql_query, query_output)
        self.assertEqual(query_output, expected_result)

    def test_convert_hex_encodings(self):
        """Test HTML hex encodings are properly decoded."""
        query_output = [
            {
                "child_names": "name with a &#x06; (acknowledge)|"
                "&#x0B;many&#x06;hex&#x0F;&#x07;name&#x08;",
            }
        ]
        graphql_query = """{
                                    Animal {
                                        in_Animal_ParentOf @fold{
                                            name @output(out_name: "child_names")
                                        }
                                    }
                                }"""

        expected_result = [
            {"child_names": ["name with a \x06 (acknowledge)", "\x0Bmany\x06hex\x0F\x07name\x08",]}
        ]

        post_process_mssql_folds(self.mssql_schema_info, graphql_query, query_output)
        self.assertEqual(query_output, expected_result)

    def test_convert_basic_decimal(self):
        """Test basic XML path encoding for decimals is correctly decoded."""
        query_output = [{"child_net_worths": "500|1000|400|~",}]
        graphql_query = """{
            Animal {
                in_Animal_ParentOf @fold{
                    net_worth @output(out_name: "child_net_worths")
                }
            }
        }"""

        expected_result = [{"child_net_worths": [500, 1000, 400, None,],}]

        post_process_mssql_folds(self.mssql_schema_info, graphql_query, query_output)
        self.assertEqual(query_output, expected_result)

    def test_convert_basic_date(self):
        """Test basic XML path encoding for datetimes is correctly decoded."""
        query_output = [{"child_birthdays": "2020-01-01|2000-02-29|~"}]
        graphql_query = """{
            Animal {
                in_Animal_ParentOf @fold{
                    birthday @output(out_name: "child_birthdays")
                }
            }
        }"""

        expected_result = [
            {"child_birthdays": [datetime.date(2020, 1, 1), datetime.date(2000, 2, 29), None],}
        ]

        post_process_mssql_folds(self.mssql_schema_info, graphql_query, query_output)
        self.assertEqual(query_output, expected_result)

    def test_convert_complex(self):
        """Test multiple folds, outputs, and types are correctly decoded."""
        query_output = [
            {
                "child_birthdays": "2020-01-01|2000-02-29|~",
                "child_net_worths": "200|~|321",
                "child_names": "^ecomplex&amp;^d^nname&#x06;|~|simple name",
                "parent_birthdays": "",
                "parent_net_worths": "",
                "parent_names": "",
            }
        ]
        # Note that multiple outputs inside a fold are not yet implemented.
        graphql_query = """{
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
        }"""

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

        post_process_mssql_folds(self.mssql_schema_info, graphql_query, query_output)
        self.assertEqual(query_output, expected_result)
