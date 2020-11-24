# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import sqlalchemy
import sqlalchemy.dialects.mssql as mssql
import sqlalchemy.dialects.postgresql as postgresql

from ..compiler.sqlalchemy_extensions import print_sqlalchemy_query_string
from .test_helpers import compare_sql, get_sqlalchemy_schema_info


class CommonIrLoweringTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.sql_schema_info = get_sqlalchemy_schema_info()

    def test_print_query_mssql_basic(self) -> None:
        query = sqlalchemy.select([self.sql_schema_info.vertex_name_to_table["Animal"].c.name])

        text = print_sqlalchemy_query_string(query, mssql.dialect())
        expected_text = """
            SELECT db_1.schema_1.[Animal].name
            FROM db_1.schema_1.[Animal]
        """
        compare_sql(self, expected_text, text)

        text = print_sqlalchemy_query_string(query, postgresql.dialect())
        expected_text = """
            SELECT "db_1.schema_1"."Animal".name
            FROM "db_1.schema_1"."Animal"
        """
        compare_sql(self, expected_text, text)

    def test_print_query_mssql_string_argument(self) -> None:
        animal = self.sql_schema_info.vertex_name_to_table["Animal"].alias()
        query = sqlalchemy.select([animal.c.name]).where(
            animal.c.name == sqlalchemy.bindparam("name", expanding=False)
        )

        text = print_sqlalchemy_query_string(query, mssql.dialect())
        expected_text = """
             SELECT [Animal_1].name
             FROM db_1.schema_1.[Animal] AS [Animal_1]
             WHERE [Animal_1].name = :name
        """
        compare_sql(self, expected_text, text)

        text = print_sqlalchemy_query_string(query, postgresql.dialect())
        expected_text = """
             SELECT "Animal_1".name
             FROM "db_1.schema_1"."Animal" AS "Animal_1"
             WHERE "Animal_1".name = :name
        """
        compare_sql(self, expected_text, text)

    def test_print_query_mssql_list_argument(self) -> None:
        animal = self.sql_schema_info.vertex_name_to_table["Animal"].alias()
        query = sqlalchemy.select([animal.c.name]).where(
            animal.c.name.in_(sqlalchemy.bindparam("names", expanding=True))
        )

        text = print_sqlalchemy_query_string(query, mssql.dialect())
        expected_text = """
             SELECT [Animal_1].name
             FROM db_1.schema_1.[Animal] AS [Animal_1]
             WHERE [Animal_1].name IN :names
        """
        compare_sql(self, expected_text, text)

        text = print_sqlalchemy_query_string(query, postgresql.dialect())
        expected_text = """
             SELECT "Animal_1".name
             FROM "db_1.schema_1"."Animal" AS "Animal_1"
             WHERE "Animal_1".name IN :names
        """
        compare_sql(self, expected_text, text)
