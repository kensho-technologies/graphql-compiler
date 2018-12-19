# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple
from unittest import TestCase

import pytest
import six
from graphql import GraphQLString
from sqlalchemy import (
    text,
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
)

from graphql_compiler import (
    CompilationResult,
    OutputMetadata,
    graphql_to_match,
)
from graphql_compiler.compiler import SQL_LANGUAGE
from graphql_compiler.tests.test_helpers import get_schema

DEFAULT_ROOT_PASSWORD = u'root'
MSSQL_ROOT_PASSWORD = u'Root-secure1'  # mssql has stricter root password restrictions


class TestBackend(object):
    POSTGRES = u'postgresql'
    MYSQL = u'mysql'
    MARIADB = u'mariadb'
    MSSQL = u'mssql'
    SQLITE = u'sqlite'
    ORIENTDB = u'orientdb'


SQL_BACKENDS = {
    TestBackend.POSTGRES,
    TestBackend.MYSQL,
    TestBackend.MARIADB,
    TestBackend.MSSQL,
    TestBackend.SQLITE,
}

MATCH_BACKENDS = {
    TestBackend.ORIENTDB,
}

GREMLIN_BACKENDS = {
    TestBackend.ORIENTDB,
}


SQL_BACKEND_TO_CONNECTION_STRING = {
    TestBackend.POSTGRES: u'postgresql://postgres:{password}@localhost:5432'.format(password=DEFAULT_ROOT_PASSWORD),
    TestBackend.MYSQL: u'mysql://root:{password}@127.0.0.1:3306'.format(password=DEFAULT_ROOT_PASSWORD),
    TestBackend.MARIADB: u'mysql://root:{password}@127.0.0.1:3307'.format(password=DEFAULT_ROOT_PASSWORD),
    TestBackend.MSSQL: u'mssql+pymssql://SA:{password}@localhost:1433'.format(password=MSSQL_ROOT_PASSWORD),
    TestBackend.SQLITE: u'sqlite:///:memory:',
}


SqlTestBackend = namedtuple('SqlTestBackend', (
    'connection_string',
    'engine',
    'connection',
    'transaction',
))


@pytest.fixture(scope="class")
def sql_integration_backend(request):
    sql_test_backends = initialize_sql_test_backends()
    populate_sql_test_data(sql_test_backends)
    request.cls.sql_test_backends = sql_test_backends
    yield
    for sql_test_backend in six.itervalues(request.cls.sql_test_backends):
        sql_test_backend.transaction.rollback()
        sql_test_backend.connection.close()


def initialize_sql_test_backends():
    """Connect to and open transaction on each SQL DB under test."""
    sql_test_backends = {}
    for backend_name, connection_string in six.iteritems(SQL_BACKEND_TO_CONNECTION_STRING):
        engine = create_engine(connection_string)
        # MYSQL and MARIADB do not have a default DB so a DB must be created
        if backend_name in {TestBackend.MYSQL, TestBackend.MARIADB}:
            # safely create the DB
            engine.execute(text('DROP DATABASE IF EXISTS animals; CREATE DATABASE animals'))
            # update the connection string and engine to connect to this DB specifically
            connection_string = connection_string + u'/animals'
            engine = create_engine(connection_string)
        connection = engine.connect()
        transaction = connection.begin()
        sql_test_backends[backend_name] = SqlTestBackend(
            connection_string=connection_string,
            engine=engine,
            connection=connection,
            transaction=transaction,
        )
    return sql_test_backends


def populate_sql_test_data(sql_test_backends):
    metadata = MetaData()
    animal_table = Table(
        'animal',
        metadata,
        Column('animal_id', Integer, primary_key=True),
        Column('name', String(length=12), nullable=False),
    )
    animal_rows = (
        (1, 'Boy Bear'),
        (2, 'Girl Bear'),
        (3, 'Mom Bear'),
        (4, 'Dad Bear'),
    )
    table_values = [
        (animal_table, animal_rows),
    ]
    for sql_test_backend in six.itervalues(sql_test_backends):
        metadata.drop_all(sql_test_backend.engine)
        metadata.create_all(sql_test_backend.engine)
        for table, insert_values in table_values:
            for insert_value in insert_values:
                sql_test_backend.connection.execute(table.insert(insert_value))


def _sort_db_results(results):
    sort_order = []
    if len(results) > 0:
        sort_order = sorted(six.iterkeys(results[0]))

    def sort_key(result):
        """Convert None/Not None to avoid comparisons to None to a non None type"""
        return tuple((result[col] is not None, result[col]) for col in sort_order)

    return sorted(results, key=sort_key)


def run_match_query(schema, graphql_query, parameters, graph_client):
    compilation_result = graphql_to_match(schema, graphql_query, parameters)
    query = compilation_result.query
    results = [row.oRecordData for row in graph_client.command(query)]
    return results


def run_sql_query(schema, graphql_query, parameters, sql_test_backend):
    mock_compilation_result = CompilationResult(
        query=text('SELECT name AS animal_name FROM animal'),
        language=SQL_LANGUAGE,
        input_metadata={},
        output_metadata={'animal_name': OutputMetadata(GraphQLString, False)}
    )

    def mock_sql_compilation(schema, graphql_query, parameters, compiler_metadata):
        return mock_compilation_result

    compilation_result = mock_sql_compilation(schema, graphql_query, parameters, None)
    query = compilation_result.query
    results = [
        dict(result) for result
        in sql_test_backend.connection.execute(query)
    ]
    return results


class IntegrationTests(TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        cls.maxDiff = None
        cls.schema = get_schema()

    def assertResultsEqual(self, expected_results, results):
        self.assertListEqual(_sort_db_results(expected_results), _sort_db_results(results))

    def assertAllResultsEqual(self, graphql_query, parameters, expected_results):
        backend_results = self.compile_and_run_query(graphql_query, parameters)
        for backend, results in six.iteritems(backend_results):
            self.assertResultsEqual(expected_results, results)

    @classmethod
    def compile_and_run_query(cls, graphql_query, parameters):
        backend_to_results = {}
        for backend_name in SQL_BACKENDS:
            sql_test_backend = cls.sql_test_backends[backend_name]
            results = run_sql_query(cls.schema, graphql_query, parameters, sql_test_backend)
            backend_to_results[backend_name] = results
        for backend_name in MATCH_BACKENDS:
            results = run_match_query(cls.schema, graphql_query, parameters, cls.graph_client)
            backend_to_results[backend_name] = results
        return backend_to_results

    @pytest.mark.usefixtures('integration_graph_client', 'sql_integration_backend')
    def test_backends(self):
        graphql_query = '''
        {
            Animal {
                name @output(out_name: "animal_name")
            }
        }
        '''
        expected_results = [
            {'animal_name': 'Mom Bear'},
            {'animal_name': 'Dad Bear'},
            {'animal_name':  'Boy Bear'},
            {'animal_name':  'Girl Bear'},
        ]
        self.assertAllResultsEqual(graphql_query, {}, expected_results)

