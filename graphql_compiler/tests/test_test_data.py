# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from .test_helpers import get_sql_schema_info


class QueryFormattingTests(unittest.TestCase):
    def test_sql_schema_info(self) -> None:
        # Test that validation passes
        get_sql_schema_info()
