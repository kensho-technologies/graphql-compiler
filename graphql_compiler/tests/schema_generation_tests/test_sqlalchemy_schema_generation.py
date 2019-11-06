# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.type import GraphQLInt, GraphQLObjectType, GraphQLString
import pytest
from sqlalchemy import Column, MetaData, Table
from sqlalchemy.dialects.mssql import TINYINT, dialect
from sqlalchemy.types import Integer, LargeBinary, String

from ... import get_sqlalchemy_schema_info_from_specified_metadata
from ...schema_generation.exceptions import InvalidSQLEdgeError, MissingPrimaryKeyError
from ...schema_generation.sqlalchemy.edge_descriptors import (
    DirectEdgeDescriptor, DirectJoinDescriptor
)
from ...schema_generation.sqlalchemy.scalar_type_mapper import try_get_graphql_scalar_type


def _get_test_vertex_name_to_table():
    """Return a dict mapping the name of each VertexType to the underlying SQLAlchemy Table."""
    metadata1 = MetaData()
    basic_table = Table(
        'BasicTable',
        metadata1,
        Column('column_with_supported_type', String(), primary_key=True),
        Column('column_with_non_supported_type', LargeBinary()),
        Column('column_with_mssql_type', TINYINT()),
        Column('source_column', Integer()),
    )

    # We use a different metadata object to test there is no dependency on the metadata object.
    metadata2 = MetaData()
    table_with_arbitrary_name = Table(
        'TableWithArbitraryName',
        metadata2,
        Column('destination_column', Integer(), primary_key=True),
    )

    return {'BasicTable': basic_table, 'ArbitraryObjectName': table_with_arbitrary_name}


def _get_test_direct_edges():
    """Return a dict mapping direct edge names to DirectEdgeDescriptor objects."""
    return {
        'test_edge': DirectEdgeDescriptor(
            'BasicTable',
            'source_column',
            'ArbitraryObjectName',
            'destination_column'
        )
    }


@pytest.mark.filterwarnings('ignore: Ignoring column .* with unsupported SQL datatype.*')
class SQLAlchemySchemaInfoGenerationTests(unittest.TestCase):
    def setUp(self):
        vertex_name_to_table = _get_test_vertex_name_to_table()
        direct_edges = _get_test_direct_edges()
        self.schema_info = get_sqlalchemy_schema_info_from_specified_metadata(
            vertex_name_to_table, direct_edges, dialect())

    def test_table_vertex_representation(self):
        self.assertIsInstance(self.schema_info.schema.get_type('BasicTable'), GraphQLObjectType)

    def test_table_vertex_representation_with_non_default_name(self):
        self.assertIsInstance(
            self.schema_info.schema.get_type('ArbitraryObjectName'), GraphQLObjectType)

    def test_represent_supported_fields(self):
        table1_graphql_object = self.schema_info.schema.get_type('BasicTable')
        self.assertEqual(
            table1_graphql_object.fields['column_with_supported_type'].type, GraphQLString)

    def test_ignored_fields_not_supported(self):
        table1_graphql_object = self.schema_info.schema.get_type('BasicTable')
        self.assertTrue('column_with_non_supported_type' not in table1_graphql_object.fields)

    def test_warn_when_type_is_not_supported(self):
        with pytest.warns(Warning):
            try_get_graphql_scalar_type('binary', LargeBinary)

    def test_mssql_scalar_type_representation(self):
        table1_graphql_object = self.schema_info.schema.get_type('BasicTable')
        self.assertEqual(
            table1_graphql_object.fields['column_with_mssql_type'].type, GraphQLInt)

    def test_direct_sql_edge_representation(self):
        table1_graphql_object = self.schema_info.schema.get_type('BasicTable')
        arbitrarily_named_graphql_object = self.schema_info.schema.get_type('ArbitraryObjectName')
        self.assertEqual(
            table1_graphql_object.fields['out_test_edge'].type.of_type.name, 'ArbitraryObjectName')
        self.assertEqual(
            arbitrarily_named_graphql_object.fields['in_test_edge'].type.of_type.name, 'BasicTable')

    def test_get_join_descriptors(self):
        expected_join_descriptors = {
            'BasicTable': {
                'out_test_edge': DirectJoinDescriptor('source_column', 'destination_column')
            },
            'ArbitraryObjectName': {
                'in_test_edge': DirectJoinDescriptor('destination_column', 'source_column')
            }
        }
        self.assertEqual(expected_join_descriptors, self.schema_info.join_descriptors)


class SQLAlchemySchemaInfoGenerationErrorTests(unittest.TestCase):
    def setUp(self):
        self.vertex_name_to_table = _get_test_vertex_name_to_table()

    def test_reference_to_non_existent_source_vertex(self):
        direct_edges = {
            'invalid_source_vertex': DirectEdgeDescriptor(
                'InvalidVertexName',
                'source_column',
                'ArbitraryObjectName',
                'destination_column'
            )
        }
        with self.assertRaises(InvalidSQLEdgeError):
            get_sqlalchemy_schema_info_from_specified_metadata(
                self.vertex_name_to_table, direct_edges, dialect())

    def test_reference_to_non_existent_destination_vertex(self):
        direct_edges = {
            'invalid_source_vertex': DirectEdgeDescriptor(
                'BasicTable',
                'source_column',
                'InvalidVertexName',
                'destination_column'
            )
        }
        with self.assertRaises(InvalidSQLEdgeError):
            get_sqlalchemy_schema_info_from_specified_metadata(
                self.vertex_name_to_table, direct_edges, dialect())

    def test_reference_to_non_existent_source_column(self):
        direct_edges = {
            'invalid_source_vertex': DirectEdgeDescriptor(
                'BasicTable',
                'invalid_column_name',
                'ArbitraryObjectName',
                'destination_column'
            )
        }
        with self.assertRaises(InvalidSQLEdgeError):
            get_sqlalchemy_schema_info_from_specified_metadata(
                self.vertex_name_to_table, direct_edges, dialect())

    def test_reference_to_non_existent_destination_column(self):
        direct_edges = {
            'invalid_destination_column': DirectEdgeDescriptor(
                'BasicTable',
                'source_column',
                'ArbitraryObjectName',
                'invalid_column_name'
            )
        }
        with self.assertRaises(InvalidSQLEdgeError):
            get_sqlalchemy_schema_info_from_specified_metadata(
                self.vertex_name_to_table, direct_edges, dialect())

    def test_missing_primary_key(self):
        table_without_primary_key = Table(
            'TableWithoutPrimaryKey',
            MetaData(),
            Column('arbitrary_column', String()),
        )
        faulty_vertex_name_to_table = {
            table_without_primary_key.name: table_without_primary_key
        }
        with self.assertRaises(MissingPrimaryKeyError):
            get_sqlalchemy_schema_info_from_specified_metadata(
                faulty_vertex_name_to_table, {}, dialect())
