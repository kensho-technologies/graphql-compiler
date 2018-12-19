# Copyright 2018-present Kensho Technologies, LLC.
from glob import glob
from os import path

from funcy import retry
import six
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text

from ..integration_tests.integration_backend_config import (
    SQL_BACKEND_TO_CONNECTION_STRING, SqlTestBackend
)
from ..test_backend import TestBackend


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


@retry(tries=20, timeout=1)  # pylint: disable=no-value-for-parameter
def init_sql_integration_test_backends():
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


def tear_down_integration_test_backends(sql_test_backends):
    """Rollback backends' transactions and close the active connections."""
    for sql_test_backend in six.itervalues(sql_test_backends):
        sql_test_backend.transaction.rollback()
        sql_test_backend.connection.close()


def generate_sql_integration_data(sql_test_backends):
    """Populate test data for SQL backends for integration testing."""
    metadata = MetaData()
    animal_table = Table(
        'animal',
        metadata,
        Column('animal_id', Integer, primary_key=True),
        Column('name', String(length=12), nullable=False),
    )
    animal_rows = (
        (1, 'Animal 1'),
        (2, 'Animal 2'),
        (3, 'Animal 3'),
        (4, 'Animal 4'),
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
