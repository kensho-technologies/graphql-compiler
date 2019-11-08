# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.type import GraphQLInt, GraphQLObjectType, GraphQLString
import pytest
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, Table
from sqlalchemy.dialects.mssql import TINYINT, dialect
from sqlalchemy.types import Binary, Integer, LargeBinary, String

from ... import get_sqlalchemy_schema_info_from_specified_metadata
from ...schema_generation.exceptions import InvalidSQLEdgeError, MissingPrimaryKeyError
from ...schema_generation.schema_graph import IndexDefinition
from ...schema_generation.sqlalchemy import (
    SQLAlchemySchemaInfo, get_graphql_schema_from_schema_graph,
    get_join_descriptors_from_edge_descriptors
)
from ...schema_generation.sqlalchemy.edge_descriptors import (
    DirectEdgeDescriptor, DirectJoinDescriptor
)
from ...schema_generation.sqlalchemy.scalar_type_mapper import try_get_graphql_scalar_type
from ...schema_generation.sqlalchemy.schema_graph_builder import get_sqlalchemy_schema_graph


def _get_test_vertex_name_to_table():
    """Return a dict mapping the name of each VertexType to the underlying SQLAlchemy Table."""
    metadata1 = MetaData()
    table1 = Table(
        'Table1',
        metadata1,
        Column('column_with_supported_type', String(), primary_key=True),
        Column('column_with_non_supported_type', LargeBinary()),
        Column('column_with_mssql_type', TINYINT()),
        Column('source_column', Integer()),
        Column('unique_column', Integer(), unique=True)
    )

    # We use a different metadata object to test there is no dependency on the metadata object.
    metadata2 = MetaData()
    table2 = Table(
        'Table2',
        metadata2,
        Column('destination_column', Integer(), primary_key=True),
    )

    table3 = Table(
        'Table3',
        metadata2,
        Column('primary_key_column1', Integer()),
        Column('primary_key_column2', Integer()),

        PrimaryKeyConstraint('primary_key_column1', 'primary_key_column2'),
    )

    table4 = Table(
        'Table4',
        metadata2,
        Column('primary_key_column_with_unsupported_type', Binary()),

        PrimaryKeyConstraint('primary_key_column_with_unsupported_type'),
    )

    return {
        'Table1': table1,
        'ArbitraryObjectName': table2,
        'TableWithMultiplePrimaryKeyColumns': table3,
        'TableWithNonSupportedPrimaryKeyType': table4,
    }


def _get_test_direct_edges():
    """Return a dict mapping direct edge names to DirectEdgeDescriptor objects."""
    return {
        'test_edge': DirectEdgeDescriptor(
            'Table1',
            'source_column',
            'ArbitraryObjectName',
            'destination_column'
        )
    }


@pytest.mark.filterwarnings('ignore: Ignoring column .* with unsupported SQL datatype.*')
class SQLAlchemySchemaInfoGenerationTests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        vertex_name_to_table = _get_test_vertex_name_to_table()
        direct_edges = _get_test_direct_edges()
        self.schema_graph = get_sqlalchemy_schema_graph(vertex_name_to_table, direct_edges)

        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(
            self.schema_graph, class_to_field_type_overrides={},
            hidden_classes=set()
        )
        join_descriptors = get_join_descriptors_from_edge_descriptors(direct_edges)

        self.schema_info = SQLAlchemySchemaInfo(
            graphql_schema, type_equivalence_hints, dialect, vertex_name_to_table, join_descriptors)

    def test_table_vertex_representation(self):
        self.assertIsInstance(self.schema_info.schema.get_type('Table1'), GraphQLObjectType)

    def test_table_vertex_representation_with_non_default_name(self):
        self.assertIsInstance(
            self.schema_info.schema.get_type('ArbitraryObjectName'), GraphQLObjectType)

    def test_represent_supported_fields(self):
        table1_graphql_object = self.schema_info.schema.get_type('Table1')
        self.assertEqual(
            table1_graphql_object.fields['column_with_supported_type'].type, GraphQLString)

    def test_ignored_fields_not_supported(self):
        table1_graphql_object = self.schema_info.schema.get_type('Table1')
        self.assertTrue('column_with_non_supported_type' not in table1_graphql_object.fields)

    def test_warn_when_type_is_not_supported(self):
        with pytest.warns(Warning):
            try_get_graphql_scalar_type('binary', LargeBinary)

    def test_mssql_scalar_type_representation(self):
        table1_graphql_object = self.schema_info.schema.get_type('Table1')
        self.assertEqual(
            table1_graphql_object.fields['column_with_mssql_type'].type, GraphQLInt)

    def test_direct_sql_edge_representation(self):
        table1_graphql_object = self.schema_info.schema.get_type('Table1')
        arbitrarily_named_graphql_object = self.schema_info.schema.get_type('ArbitraryObjectName')
        self.assertEqual(
            table1_graphql_object.fields['out_test_edge'].type.of_type.name, 'ArbitraryObjectName')
        self.assertEqual(
            arbitrarily_named_graphql_object.fields['in_test_edge'].type.of_type.name, 'Table1')

    def test_get_join_descriptors(self):
        expected_join_descriptors = {
            'Table1': {
                'out_test_edge': DirectJoinDescriptor('source_column', 'destination_column')
            },
            'ArbitraryObjectName': {
                'in_test_edge': DirectJoinDescriptor('destination_column', 'source_column')
            }
        }
        self.assertEqual(expected_join_descriptors, self.schema_info.join_descriptors)

    def test_basic_index_generation_from_primary_key(self):
        indexes = self.schema_graph.get_all_indexes_for_class('Table1')
        self.assertIn(
            IndexDefinition(
                name=None,
                base_classname='Table1',
                fields=frozenset({'column_with_supported_type'}),
                unique=True,
                ordered=False,
                ignore_nulls=False,
            ), indexes
        )

    def test_index_generation_from_multi_column_primary_key(self):
        indexes = self.schema_graph.get_all_indexes_for_class('TableWithMultiplePrimaryKeyColumns')
        self.assertEqual(
            {
                IndexDefinition(
                    name=None,
                    base_classname='TableWithMultiplePrimaryKeyColumns',
                    fields=frozenset({'primary_key_column1', 'primary_key_column2'}),
                    unique=True,
                    ordered=False,
                    ignore_nulls=False,
                ),
            }, indexes
        )

    def test_index_generation_from_primary_key_with_an_unsupported_column_type(self):
        indexes = self.schema_graph.get_all_indexes_for_class('TableWithNonSupportedPrimaryKeyType')
        self.assertEqual(frozenset(), indexes)

    def test_index_generation_from_unique_constraint(self):
        indexes = self.schema_graph.get_all_indexes_for_class('Table1')
        self.assertIn(
            IndexDefinition(
                name=None,
                base_classname='Table1',
                fields=frozenset({'unique_column'}),
                unique=True,
                ordered=False,
                ignore_nulls=True,
            ), indexes
        )


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
                'Table1',
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
                'Table1',
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
                'Table1',
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
