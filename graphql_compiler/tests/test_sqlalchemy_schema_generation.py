# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.type import GraphQLInt, GraphQLString
from graphql.utils.schema_printer import print_schema
import pytest
from sqlalchemy import Column, MetaData, Table
from sqlalchemy.dialects.mssql.base import TINYINT
from sqlalchemy.types import Binary, Integer, String

from graphql_compiler import get_graphql_schema_from_sqlalchemy_metadata

from ..schema_generation.schema_graph import VertexType
from ..schema_generation.sqlalchemy.scalar_type_mapper import try_get_graphql_scalar_type
from ..schema_generation.sqlalchemy.schema_graph_builder import get_sqlalchemy_schema_graph
from .test_helpers import compare_schema_texts


def _get_sql_metadata():
    """Return a Metadata object for test usage."""
    metadata = MetaData()

    Table(
        'A',
        metadata,
        Column('supported_type', String()),
        Column('non_supported_type', Binary()),
        Column('default', Integer(), default=42),
        Column('column_with_mssql_type', TINYINT),
    )

    return metadata


class SQLALchemyGraphqlSchemaGenerationTests(unittest.TestCase):
    def setUp(self):
        metadata = _get_sql_metadata()
        self.schema_graph = get_sqlalchemy_schema_graph(metadata)
        self.graphql_schema, self.type_equivalence_hints = (
            get_graphql_schema_from_sqlalchemy_metadata(metadata))

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
            try_get_graphql_scalar_type('binary', Binary)

    def test_default_value_parsing(self):
        a_vertex = self.schema_graph.get_element_by_class_name('A')
        self.assertEqual(a_vertex.properties['default'].default, 42)

    def test_sql_self_inheritance(self):
        # Tests that a class is in its own subclass/superclass set.
        self.assertEqual(self.schema_graph.get_subclass_set('A'), {'A'})
        self.assertEqual(self.schema_graph.get_superclass_set('A'), {'A'})

    def test_mssql_type_mapping(self):
        a_vertex = self.schema_graph.get_element_by_class_name('A')
        self.assertEqual(a_vertex.properties['column_with_mssql_type'].type, GraphQLInt)

    def test_sqlalchemy_graphql_schema_generation(self):
        expected_schema_text = '''
            schema {
                query: RootSchemaQuery
            }

            directive @filter(op_name: String!, value: [String!]!) on FIELD | INLINE_FRAGMENT

            directive @tag(tag_name: String!) on FIELD

            directive @output(out_name: String!) on FIELD

            directive @output_source on FIELD

            directive @optional on FIELD

            directive @recurse(depth: Int!) on FIELD

            directive @fold on FIELD

            type A {
                _x_count: Int
                column_with_mssql_type: Int
                default: Int
                supported_type: String
            }

            type RootSchemaQuery {
                A: [A]
            }
        '''
        schema_text = print_schema(self.graphql_schema)
        compare_schema_texts(self, expected_schema_text, schema_text)
        self.assertEqual({}, self.type_equivalence_hints)
