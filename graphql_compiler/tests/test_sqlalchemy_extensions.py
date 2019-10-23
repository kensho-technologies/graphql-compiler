# Copyright 2019-present Kensho Technologies, LLC.
import unittest
import sqlalchemy
import sqlalchemy.dialects.mssql as mssql

from ..compiler.sqlalchemy_extensions import print_sqlalchemy_query_string
from .test_helpers import get_sqlalchemy_schema_info

class CommonIrLoweringTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.sql_schema_info = get_sqlalchemy_schema_info()

    def test_print_query_mssql_basic(self):
        query = sqlalchemy.select([self.sql_schema_info.vertex_name_to_table['Animal'].c.name])
        text = print_sqlalchemy_query_string(query, mssql.dialect())
        import pdb; pdb.set_trace()
        print(1)
        pass
