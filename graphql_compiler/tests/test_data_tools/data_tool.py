# Copyright 2018-present Kensho Technologies, LLC.
import datetime
from decimal import Decimal
from glob import glob
from os import path

from funcy import retry
import six
from sqlalchemy import create_engine, text
from sqlalchemy.schema import CreateSchema

from ..integration_tests.integration_backend_config import (
    EXPLICIT_DB_BACKENDS, SQL_BACKEND_TO_CONNECTION_STRING, SqlTestBackend
)
from ..test_helpers import get_sqlalchemy_schema_info


def generate_orient_snapshot_data(client):
    """Create OrientDB test DB from the SQL commands file for snapshot testing."""
    project_root = path.dirname(path.abspath(__file__))
    sql_files = glob(path.join(project_root, 'snapshot_data/*.sql'))
    _load_sql_files_to_orient_client(client, sql_files)


def generate_orient_integration_data(client):
    """Create OrientDB test DB from the SQL commands file for snapshot testing."""
    project_root = path.dirname(path.abspath(__file__))
    sql_files = glob(path.join(project_root, 'integration_data/*.sql'))
    _load_sql_files_to_orient_client(client, sql_files)


def generate_neo4j_integration_data(client):
    """Create Neo4j test DB from the SQL commands file for integration testing."""
    project_root = path.dirname(path.abspath(__file__))
    neo4j_files = glob(path.join(project_root, 'integration_data/create_neo4j_integration.cypher'))
    _load_neo4j_files_to_neo4j_client(client, neo4j_files)


def _load_neo4j_files_to_neo4j_client(client, neo4j_files):
    """Load list of supplied Cypher files into the supplied Neo4j client."""
    for filepath in neo4j_files:
        with open(filepath) as f:
            with client.driver.session() as session:
                for command in f.readlines():
                    sanitized_command = command.strip()
                    if len(sanitized_command) == 0 or sanitized_command[0] == '#':
                        # comment or empty line, ignore
                        continue
                    session.run(sanitized_command)


def generate_redisgraph_integration_data(client):
    """Create Redisgraph test DB from the SQL commands file for integration testing."""
    project_root = path.dirname(path.abspath(__file__))
    cypher_files = glob(path.join(project_root,
                                  'integration_data/create_redisgraph_integration.cypher'))
    _load_cypher_files_to_redisgraph_client(client, cypher_files)


def _load_cypher_files_to_redisgraph_client(client, cypher_files):
    """Load list of supplied Cypher files into the supplied RedisGraph client."""
    for filepath in cypher_files:
        with open(filepath) as f:
            for command in f.readlines():
                sanitized_command = command.strip()
                if len(sanitized_command) == 0 or sanitized_command[0] == '#':
                    # comment or empty line, ignore
                    continue
                client.query(sanitized_command)


def _load_sql_files_to_orient_client(client, sql_files):
    """Load list of supplied SQL files into the supplied OrientDB client."""
    for filepath in sql_files:
        with open(filepath) as f:
            for command in f.readlines():
                sanitized_command = command.strip()
                if len(sanitized_command) == 0 or sanitized_command[0] == '#':
                    # comment or empty line, ignore
                    continue

                client.command(sanitized_command)


@retry(tries=1, timeout=1)  # pylint: disable=no-value-for-parameter
def init_sql_integration_test_backends():
    """Connect to and open transaction on each SQL DB under test."""
    sql_test_backends = {}
    for backend_name, base_connection_string in six.iteritems(SQL_BACKEND_TO_CONNECTION_STRING):
        engine = create_engine(base_connection_string)
        # safely create the test DATABASE for all SQL backends except sqlite
        # sqlite's in-memory database does not need to be explicitly created/dropped.
        if backend_name in EXPLICIT_DB_BACKENDS:
            # Drop databases if they exist
            engine.execution_options(isolation_level='AUTOCOMMIT').execute(
                text('DROP DATABASE IF EXISTS db_1;'))
            engine.execution_options(isolation_level='AUTOCOMMIT').execute(
                text('DROP DATABASE IF EXISTS db_2;'))

            # create the test databases
            engine.execution_options(isolation_level='AUTOCOMMIT').execute(
                text('CREATE DATABASE db_1;'))
            engine.execution_options(isolation_level='AUTOCOMMIT').execute(
                text('CREATE DATABASE db_2;'))

            # create the test schemas in db_1
            db_1_engine = create_engine(base_connection_string + u'/db_1')
            db_1_engine.execution_options(isolation_level='AUTOCOMMIT').execute(
                CreateSchema('schema_1'))
            db_1_engine.execution_options(isolation_level='AUTOCOMMIT').execute(
                CreateSchema('schema_2'))

            # create the test schemas in db_2
            db_2_engine = create_engine(base_connection_string + u'/db_2')
            db_2_engine.execution_options(isolation_level='AUTOCOMMIT').execute(
                CreateSchema('schema_1'))
            db_2_engine.execution_options(isolation_level='AUTOCOMMIT').execute(
                CreateSchema('schema_2'))

        sql_test_backend = SqlTestBackend(engine, base_connection_string)
        sql_test_backends[backend_name] = sql_test_backend
    return sql_test_backends


def tear_down_integration_test_backends(sql_test_backends):
    """Rollback backends' transactions to wipe test data and to close the active connections."""
    for backend_name, sql_test_backend in six.iteritems(sql_test_backends):
        if backend_name not in EXPLICIT_DB_BACKENDS:
            continue
        # explicitly release engine resources, specifically to disconnect from active DB
        # some backends including Postgres do no not allow an in use DB to be dropped
        sql_test_backend.engine.dispose()
        # connect to base server, not explicit DB, so DB can be dropped
        engine = create_engine(sql_test_backend.base_connection_string)
        # set execution options to AUTOCOMMIT so that the DB drop is not performed in a transaction
        # as this is not allowed on some SQL backends
        engine.execution_options(isolation_level='AUTOCOMMIT').execute(
            text('DROP DATABASE IF EXISTS db_1;'))
        engine.execution_options(isolation_level='AUTOCOMMIT').execute(
            text('DROP DATABASE IF EXISTS db_2;'))


def generate_sql_integration_data(sql_test_backends):
    """Populate test data for SQL backends for integration testing."""
    sql_schema_info = get_sqlalchemy_schema_info()
    animal_rows = (
        {
            'uuid': 'cfc6e625-8594-0927-468f-f53d864a7a51',
            'name': 'Animal 1',
            'net_worth': Decimal('100'),
            'birthday': datetime.date(1900, 1, 1),
        },
        {
            'uuid': 'cfc6e625-8594-0927-468f-f53d864a7a52',
            'name': 'Animal 2',
            'net_worth': Decimal('200'),
            'birthday': datetime.date(1950, 2, 2),
        },
        {
            'uuid': 'cfc6e625-8594-0927-468f-f53d864a7a53',
            'name': 'Animal 3',
            'net_worth': Decimal('300'),
            'birthday': datetime.date(1975, 3, 3),
        },
        {
            'uuid': 'cfc6e625-8594-0927-468f-f53d864a7a54',
            'name': 'Animal 4',
            'net_worth': Decimal('400'),
            'birthday': datetime.date(2000, 4, 4),
        },
    )
    table_values = [
        (sql_schema_info.vertex_name_to_table['Animal'], animal_rows),
    ]
    for sql_test_backend in six.itervalues(sql_test_backends):
        for table, insert_values in table_values:
            table.delete(bind=sql_test_backend.engine)
            table.create(bind=sql_test_backend.engine)
            for insert_value in insert_values:
                sql_test_backend.engine.execute(table.insert().values(**insert_value))
    return sql_schema_info
