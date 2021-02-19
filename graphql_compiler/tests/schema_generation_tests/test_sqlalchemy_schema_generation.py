# Copyright 2019-present Kensho Technologies, LLC.
from typing import Dict
import unittest

from graphql.type import GraphQLInt, GraphQLObjectType, GraphQLString
import pytest
from sqlalchemy import (
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    MetaData,
    PrimaryKeyConstraint,
    Table,
)
from sqlalchemy.dialects.mssql import TINYINT, dialect
from sqlalchemy.types import TIMESTAMP, DateTime, Integer, LargeBinary, String

from ... import get_sqlalchemy_schema_info
from ...schema import GraphQLDateTime
from ...schema_generation.exceptions import InvalidSQLEdgeError, MissingPrimaryKeyError
from ...schema_generation.schema_graph import IndexDefinition
from ...schema_generation.sqlalchemy import (
    SQLAlchemySchemaInfo,
    get_graphql_schema_from_schema_graph,
    get_join_descriptors_from_edge_descriptors,
)
from ...schema_generation.sqlalchemy.edge_descriptors import (
    CompositeEdgeDescriptor,
    DirectEdgeDescriptor,
    DirectJoinDescriptor,
    generate_direct_edge_descriptors_from_foreign_keys,
)
from ...schema_generation.sqlalchemy.scalar_type_mapper import try_get_graphql_scalar_type
from ...schema_generation.sqlalchemy.schema_graph_builder import get_sqlalchemy_schema_graph


def _get_test_vertex_name_to_table():
    """Return a dict mapping the name of each VertexType to the underlying SQLAlchemy Table."""
    metadata = MetaData()
    table1 = Table(
        "Table1",
        metadata,
        Column("column_with_supported_type", String(), primary_key=True),
        Column("column_with_non_supported_type", LargeBinary()),
        Column("column_with_mssql_type", TINYINT()),
        Column("source_column", Integer(), ForeignKey("Table2.destination_column")),
        Column("unique_column", Integer(), unique=True),
    )

    table2 = Table(
        "Table2",
        metadata,
        Column("destination_column", Integer(), primary_key=True),
    )

    table3 = Table(
        "Table3",
        metadata,
        Column("primary_key_column1", Integer()),
        Column("primary_key_column2", Integer()),
        PrimaryKeyConstraint("primary_key_column1", "primary_key_column2"),
    )

    table4 = Table(
        "Table4",
        metadata,
        Column("primary_key_column_with_unsupported_type", LargeBinary()),
        PrimaryKeyConstraint("primary_key_column_with_unsupported_type"),
    )

    return {
        "Table1": table1,
        "ArbitraryObjectName": table2,
        "TableWithMultiplePrimaryKeyColumns": table3,
        "TableWithNonSupportedPrimaryKeyType": table4,
    }


def _get_test_direct_edges():
    """Return a dict mapping direct edge names to DirectEdgeDescriptor objects."""
    return {
        "test_edge": DirectEdgeDescriptor(
            "Table1", "source_column", "ArbitraryObjectName", "destination_column"
        )
    }


@pytest.mark.filterwarnings("ignore: Ignoring column .* with unsupported SQL datatype.*")
class SQLAlchemySchemaInfoGenerationTests(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        vertex_name_to_table = _get_test_vertex_name_to_table()
        direct_edges = _get_test_direct_edges()
        self.schema_graph = get_sqlalchemy_schema_graph(vertex_name_to_table, direct_edges)

        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(
            self.schema_graph, class_to_field_type_overrides={}, hidden_classes=set()
        )
        join_descriptors = get_join_descriptors_from_edge_descriptors(direct_edges)

        self.schema_info = SQLAlchemySchemaInfo(
            graphql_schema, type_equivalence_hints, dialect, vertex_name_to_table, join_descriptors
        )

    def test_table_vertex_representation(self) -> None:
        self.assertIsInstance(self.schema_info.schema.get_type("Table1"), GraphQLObjectType)

    def test_table_vertex_representation_with_non_default_name(self) -> None:
        self.assertIsInstance(
            self.schema_info.schema.get_type("ArbitraryObjectName"), GraphQLObjectType
        )

    def test_represent_supported_fields(self) -> None:
        table1_graphql_object = self.schema_info.schema.get_type("Table1")
        self.assertEqual(
            table1_graphql_object.fields["column_with_supported_type"].type, GraphQLString
        )

    def test_ignored_fields_not_supported(self) -> None:
        table1_graphql_object = self.schema_info.schema.get_type("Table1")
        self.assertTrue("column_with_non_supported_type" not in table1_graphql_object.fields)

    def test_warn_when_type_is_not_supported(self) -> None:
        with pytest.warns(Warning):
            try_get_graphql_scalar_type("binary", LargeBinary())

    def test_support_sql_tz_naive_datetime_types(self) -> None:
        column_name = "tz_naive_datetime"
        tz_naive_types = (DateTime(timezone=False), TIMESTAMP(timezone=False))
        for sql_type in tz_naive_types:
            self.assertEqual(GraphQLDateTime, try_get_graphql_scalar_type(column_name, sql_type))

    def test_do_not_support_sql_tz_aware_datetime_types(self) -> None:
        column_name = "tz_aware_datetime"
        tz_aware_types = (DateTime(timezone=True), TIMESTAMP(timezone=True))
        for sql_type in tz_aware_types:
            with self.assertWarns(Warning):
                graphql_type = try_get_graphql_scalar_type(column_name, sql_type)
            self.assertIsNone(graphql_type)

    def test_mssql_scalar_type_representation(self) -> None:
        table1_graphql_object = self.schema_info.schema.get_type("Table1")
        self.assertEqual(table1_graphql_object.fields["column_with_mssql_type"].type, GraphQLInt)

    def test_direct_sql_edge_representation(self) -> None:
        table1_graphql_object = self.schema_info.schema.get_type("Table1")
        arbitrarily_named_graphql_object = self.schema_info.schema.get_type("ArbitraryObjectName")
        self.assertEqual(
            table1_graphql_object.fields["out_test_edge"].type.of_type.name, "ArbitraryObjectName"
        )
        self.assertEqual(
            arbitrarily_named_graphql_object.fields["in_test_edge"].type.of_type.name, "Table1"
        )

    def test_get_join_descriptors(self) -> None:
        expected_join_descriptors = {
            "Table1": {
                "out_test_edge": DirectJoinDescriptor("source_column", "destination_column")
            },
            "ArbitraryObjectName": {
                "in_test_edge": DirectJoinDescriptor("destination_column", "source_column")
            },
        }
        self.assertEqual(expected_join_descriptors, self.schema_info.join_descriptors)

    def test_basic_index_generation_from_primary_key(self) -> None:
        indexes = self.schema_graph.get_all_indexes_for_class("Table1")
        self.assertIn(
            IndexDefinition(
                name=None,
                base_classname="Table1",
                fields=frozenset({"column_with_supported_type"}),
                unique=True,
                ordered=False,
                ignore_nulls=False,
            ),
            indexes,
        )

    def test_index_generation_from_multi_column_primary_key(self) -> None:
        indexes = self.schema_graph.get_all_indexes_for_class("TableWithMultiplePrimaryKeyColumns")
        self.assertEqual(
            {
                IndexDefinition(
                    name=None,
                    base_classname="TableWithMultiplePrimaryKeyColumns",
                    fields=frozenset({"primary_key_column1", "primary_key_column2"}),
                    unique=True,
                    ordered=False,
                    ignore_nulls=False,
                ),
            },
            indexes,
        )

    def test_index_generation_from_primary_key_with_an_unsupported_column_type(self) -> None:
        indexes = self.schema_graph.get_all_indexes_for_class("TableWithNonSupportedPrimaryKeyType")
        self.assertEqual(frozenset(), indexes)

    def test_index_generation_from_unique_constraint(self) -> None:
        indexes = self.schema_graph.get_all_indexes_for_class("Table1")
        self.assertIn(
            IndexDefinition(
                name=None,
                base_classname="Table1",
                fields=frozenset({"unique_column"}),
                unique=True,
                ordered=False,
                ignore_nulls=True,
            ),
            indexes,
        )

    def test_composite_edge(self) -> None:
        edges = {
            "composite_edge": CompositeEdgeDescriptor(
                "Table1",
                "TableWithMultiplePrimaryKeyColumns",
                {
                    ("source_column", "primary_key_column1"),
                    ("unique_column", "primary_key_column2"),
                },
            )
        }
        schema_info = get_sqlalchemy_schema_info(_get_test_vertex_name_to_table(), edges, dialect())
        self.assertTrue("out_composite_edge" in schema_info.join_descriptors["Table1"])
        self.assertTrue(
            "in_composite_edge"
            in schema_info.join_descriptors["TableWithMultiplePrimaryKeyColumns"]
        )


@pytest.mark.filterwarnings("ignore: Ignored .* edges implied by composite foreign keys.*")
class SQLAlchemyForeignKeyEdgeGenerationTests(unittest.TestCase):
    def test_edge_generation_from_foreign_keys(self) -> None:
        metadata = MetaData()

        table1 = Table(
            "Table1",
            metadata,
            Column("primary_key_column", Integer(), primary_key=True),
            Column("foreign_key_column", Integer(), ForeignKey("Table2.primary_key_column")),
        )

        table2 = Table("Table2", metadata, Column("primary_key_column", Integer, primary_key=True))

        vertex_name_to_table = {
            "TableWithForeignKey": table1,
            "TableWithReferencedPrimaryKey": table2,
        }

        direct_edge_descriptors = generate_direct_edge_descriptors_from_foreign_keys(
            vertex_name_to_table
        )

        self.assertEqual(
            direct_edge_descriptors,
            {
                DirectEdgeDescriptor(
                    from_vertex="TableWithForeignKey",
                    from_column="foreign_key_column",
                    to_vertex="TableWithReferencedPrimaryKey",
                    to_column="primary_key_column",
                ),
            },
        )

    def test_warning_for_ignored_foreign_keys(self) -> None:
        metadata = MetaData()

        table1 = Table(
            "Table1",
            metadata,
            Column("primary_key_column", Integer(), primary_key=True),
            Column("foreign_key_column1", Integer()),
            Column("foreign_key_column2", Integer()),
            ForeignKeyConstraint(
                ("foreign_key_column1", "foreign_key_column2"),
                ("Table2.primary_key_column1", "Table2.primary_key_column2"),
            ),
        )

        table2 = Table(
            "Table2",
            metadata,
            Column("primary_key_column1", Integer, primary_key=True),
            Column("primary_key_column2", Integer, primary_key=True),
        )

        vertex_name_to_table = {
            "TableWithForeignKey": table1,
            "TableWithReferencedPrimaryKey": table2,
        }

        with pytest.warns(Warning):
            direct_edge_descriptors = generate_direct_edge_descriptors_from_foreign_keys(
                vertex_name_to_table
            )

        self.assertEqual(direct_edge_descriptors, set())


class SQLAlchemySchemaInfoGenerationErrorTests(unittest.TestCase):
    def setUp(self):
        self.vertex_name_to_table = _get_test_vertex_name_to_table()

    def test_reference_to_non_existent_source_vertex(self) -> None:
        direct_edges = {
            "invalid_source_vertex": DirectEdgeDescriptor(
                "InvalidVertexName", "source_column", "ArbitraryObjectName", "destination_column"
            )
        }
        with self.assertRaises(InvalidSQLEdgeError):
            get_sqlalchemy_schema_info(self.vertex_name_to_table, direct_edges, dialect())

    def test_reference_to_non_existent_destination_vertex(self) -> None:
        direct_edges = {
            "invalid_source_vertex": DirectEdgeDescriptor(
                "Table1", "source_column", "InvalidVertexName", "destination_column"
            )
        }
        with self.assertRaises(InvalidSQLEdgeError):
            get_sqlalchemy_schema_info(self.vertex_name_to_table, direct_edges, dialect())

    def test_reference_to_non_existent_source_column(self) -> None:
        direct_edges = {
            "invalid_source_vertex": DirectEdgeDescriptor(
                "Table1", "invalid_column_name", "ArbitraryObjectName", "destination_column"
            )
        }
        with self.assertRaises(InvalidSQLEdgeError):
            get_sqlalchemy_schema_info(self.vertex_name_to_table, direct_edges, dialect())

    def test_reference_to_non_existent_destination_column(self) -> None:
        direct_edges = {
            "invalid_destination_column": DirectEdgeDescriptor(
                "Table1", "source_column", "ArbitraryObjectName", "invalid_column_name"
            )
        }
        with self.assertRaises(InvalidSQLEdgeError):
            get_sqlalchemy_schema_info(self.vertex_name_to_table, direct_edges, dialect())

    def test_missing_primary_key(self) -> None:
        table_without_primary_key = Table(
            "TableWithoutPrimaryKey",
            MetaData(),
            Column("arbitrary_column", String()),
        )
        faulty_vertex_name_to_table = {table_without_primary_key.name: table_without_primary_key}
        with self.assertRaises(MissingPrimaryKeyError):
            get_sqlalchemy_schema_info(faulty_vertex_name_to_table, {}, dialect())

    def test_missing_multiple_primary_keys(self) -> None:
        metadata: MetaData = MetaData()
        table_without_primary_key: Table = Table(
            "TableWithoutPrimaryKey",
            metadata,
            Column("arbitrary_column", String()),
        )
        second_table_without_primary_key: Table = Table(
            "SecondTableWithoutPrimaryKey",
            metadata,
            Column("second_arbitrary_column", String()),
        )
        faulty_vertex_name_to_table: Dict[str, Table] = {
            table_without_primary_key.name: table_without_primary_key,
            second_table_without_primary_key.name: second_table_without_primary_key,
        }
        with self.assertRaises(MissingPrimaryKeyError) as missing_primary_key_error_info:
            get_sqlalchemy_schema_info(faulty_vertex_name_to_table, {}, dialect())
        exception_message: str = missing_primary_key_error_info.exception.args[0]
        for table_name in faulty_vertex_name_to_table:
            self.assertIn(table_name, exception_message)
