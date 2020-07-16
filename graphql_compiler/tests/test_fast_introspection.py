# Copyright 2020-present Kensho Technologies, LLC.
import unittest

from graphql import GraphQLError, GraphQLSchema, get_introspection_query, graphql_sync

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
        execution_result = try_fast_introspection(schema, introspection_query)
        self.assertIsNotNone(execution_result)
        if execution_result:
            self.assertEqual(graphql_sync(schema, introspection_query), execution_result)

    def test_fast_introspection_validate_schema(self) -> None:
        execution_result = try_fast_introspection(GraphQLSchema(), introspection_query)
        self.assertIsNotNone(execution_result)
        if execution_result:
            self.assertIsNone(execution_result.data)
            self.assertEqual(
                execution_result.errors,
                [GraphQLError('Query root type must be provided.')]
            )
