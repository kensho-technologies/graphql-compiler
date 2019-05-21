# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.type import GraphQLNonNull, GraphQLString
import pytest
from sqlalchemy import Column, MetaData, Table
from sqlalchemy.types import Binary, String

from ..schema_generation.schema_graph import VertexType
from ..schema_generation.sqlalchemy.schema_graph_builder import (
    _try_get_graphql_scalar_type, get_schema_graph_from_sql_alchemy_metadata
)


def _get_sql_metadata():
    """Return a Metadata object for test usage."""
    metadata = MetaData()

    Table(
        'A',
        metadata,
        Column('supported_type', String()),
        Column('non_supported_type', Binary()),
        Column('non_nullable', String(), nullable=False)
    )

    return metadata


class SQLALchemyGraphqlSchemaGenerationTests(unittest.TestCase):
    def setUp(self):
        metadata = _get_sql_metadata()
        self.schema_graph = get_schema_graph_from_sql_alchemy_metadata(metadata)

    def test_table_vertex_representation(self):
        self.assertEqual(type(self.schema_graph.get_element_by_class_name('A')), VertexType)

    def test_represent_supported_properties(self):
        a_vertex = self.schema_graph.get_element_by_class_name('A')
        self.assertEqual(a_vertex.properties['supported_type'].type, GraphQLString)

    def test_ignored_properties_not_supported(self):
        a_vertex = self.schema_graph.get_element_by_class_name('A')
        self.assertNotIn('non_supported_type', a_vertex.properties)

    def test_warn_when_type_is_not_supported(self):
        with pytest.warns(Warning):
            _try_get_graphql_scalar_type('binary', Binary)

    def test_non_nullable(self):
        a_vertex = self.schema_graph.get_element_by_class_name('A')
        non_null_graphql_string = GraphQLNonNull(GraphQLString)
        non_null_property = a_vertex.properties['non_nullable']
        self.assertTrue(non_null_property.type.is_same_type(non_null_graphql_string))
