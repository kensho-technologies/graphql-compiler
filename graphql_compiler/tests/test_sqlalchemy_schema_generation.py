# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.type import GraphQLBoolean, GraphQLFloat, GraphQLInt, GraphQLString
from sqlalchemy import Column, Date, DateTime, MetaData, Numeric, String, Table
from sqlalchemy.types import (
    ARRAY, BLOB, CHAR, CLOB, JSON, NCHAR, NVARCHAR, REAL, TIMESTAMP, VARBINARY, BigInteger, Binary,
    Boolean, Enum, Float, Integer, Interval, LargeBinary, NullType, PickleType, SmallInteger, Text,
    Time, Unicode, UnicodeText
)

from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from ..schema_generation.schema_graph import VertexType
from ..schema_generation.sqlalchemy.schema_graph_builder import (
    get_schema_graph_from_sql_alchemy_metadata
)


SUPPORTED_SQL_TYPE_TUPLES = (
    ('string', String(), GraphQLString),
    ('text', Text(), GraphQLString),
    ('unicode', Unicode(), GraphQLString),
    ('unicode_text', UnicodeText(), GraphQLString),
    ('integer', Integer(), GraphQLInt),
    ('small_integer', SmallInteger(), GraphQLInt),
    ('big_integer', BigInteger(), GraphQLInt),
    ('numeric', Numeric(), GraphQLDecimal),
    ('float', Float(), GraphQLFloat),
    ('date_time', DateTime(), GraphQLDateTime),
    ('date', Date(), GraphQLDate),
    ('boolean', Boolean(), GraphQLBoolean),
    ('enum', Enum(), GraphQLString),
    ('real', REAL(), GraphQLFloat),
    ('timestamp', TIMESTAMP(), GraphQLDateTime),
    ('clob', CLOB(), GraphQLString),
    ('nvarchar', NVARCHAR(), GraphQLString),
    ('char', CHAR(), GraphQLString),
    ('nchar', NCHAR(), GraphQLString)
)

NON_SUPPORTED_SQL_TYPE_TUPLES = (
    ('time', Time()),
    ('binary', Binary()),
    ('large_binary', LargeBinary()),
    ('pickle_type', PickleType()),
    ('interval', Interval()),
    ('array', ARRAY(String)),
    ('json', JSON()),
    ('null_type', NullType()),
    ('blob', BLOB()),
    ('varbinary', VARBINARY())
)


def _get_sql_metadata():
    """Return a Metadata object for test usage."""
    metadata = MetaData()

    # Table A contains columns with all supported builtin types
    Table(
        'A',
        metadata,
        *(Column(name, type_) for name, type_, _ in SUPPORTED_SQL_TYPE_TUPLES)
    )

    # Table A contains columns with all builtin types currently not supported
    Table(
        'B',
        metadata,
        *(Column(name, type_) for name, type_ in NON_SUPPORTED_SQL_TYPE_TUPLES)
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
        for name, _, graphql_type in SUPPORTED_SQL_TYPE_TUPLES:
            self.assertEqual(a_vertex.properties[name].type, graphql_type)

    def test_ignored_properties_not_supported(self):
        b_vertex = self.schema_graph.get_element_by_class_name('B')
        self.assertEqual(b_vertex.properties, {})
