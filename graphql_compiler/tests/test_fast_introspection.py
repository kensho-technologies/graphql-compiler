# Copyright 2020-present Kensho Technologies, LLC.
import unittest

from graphql import get_introspection_query, graphql_sync

from ..fast_introspection import (
    remove_whitespace_from_query,
    try_fast_introspection,
    whitespace_free_introspection_query,
)
from .test_helpers import get_schema


introspection_query = get_introspection_query()


class FastIntrospectionTests(unittest.TestCase):
    def test_graphql_get_introspection_query(self) -> None:
        self.assertEqual(
            whitespace_free_introspection_query, remove_whitespace_from_query(introspection_query),
        )

    def test_try_fast_introspection_none(self) -> None:
        schema = get_schema()
        self.assertEqual(try_fast_introspection(schema, "not the right query"), None)

    def test_try_fast_introspection_equal_graphql_sync(self) -> None:
        schema = get_schema()
        result = try_fast_introspection(schema, introspection_query)
        self.assertIsNotNone(result)
        if result:
            self.assertEqual(graphql_sync(schema, introspection_query).data, result.data)
