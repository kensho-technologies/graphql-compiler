from collections import namedtuple
from urllib.parse import quote_plus

import six
from funcy import retry
from sqlalchemy import create_engine, text
from sqlalchemy.sql.ddl import CreateSchema

import graphql_compiler.tests.integration_tests.backends as test_config

SqlTestBackend = namedtuple("SqlTestBackend", ("engine", "base_connection_string",))

# sqlite does not require that a DB be created/dropped for testing
EXPLICIT_DB_BACKENDS = {
    test_config.POSTGRES,
    test_config.MYSQL,
    test_config.MARIADB,
    test_config.MSSQL,
}

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
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("DROP DATABASE IF EXISTS db_1;")
            )
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("DROP DATABASE IF EXISTS db_2;")
            )

            # create the test databases
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("CREATE DATABASE db_1;")
            )
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("CREATE DATABASE db_2;")
            )

            engine.execution_options(isolation_level="AUTOCOMMIT").execute(text("USE db_1;"))
            # create the test schemas in db_1
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(CreateSchema("schema_1"))
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(CreateSchema("schema_2"))

            engine.execution_options(isolation_level="AUTOCOMMIT").execute(text("USE db_2;"))
            # create the test schemas in db_2
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(CreateSchema("schema_1"))
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(CreateSchema("schema_2"))

            engine.execution_options(isolation_level="AUTOCOMMIT").execute(text("USE master;"))

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
        engine.execution_options(isolation_level="AUTOCOMMIT").execute(
            text("DROP DATABASE IF EXISTS db_1;")
        )
        engine.execution_options(isolation_level="AUTOCOMMIT").execute(
            text("DROP DATABASE IF EXISTS db_2;")
        )


pyodbc_parameter_string = "DRIVER={driver};SERVER={server};UID={uid};PWD={pwd}".format(  # nosec
    driver="{ODBC Driver 17 for SQL SERVER}",
    server="127.0.0.1",  # Do not change to 'localhost'. You won't be able to connect with the db.
    uid="SA",  # System Administrator.
    pwd="Root-secure1",
)

# delimeters must be URL escaped
escaped_pyodbc_parameter_string = quote_plus(pyodbc_parameter_string)


SQL_BACKEND_TO_CONNECTION_STRING = {
    # HACK(bojanserafimov): Entries are commented-out because MSSQL is the only one whose scheme
    #                       initialization is properly configured  , with a hierarchy of multiple
    #                       databases and schemas. I'm keeping the code to remember the connection
    #                       string formats.
    #
    # test_backend.POSTGRES:
    #     u'postgresql://postgres:{password}@localhost:5432'.format(password=DEFAULT_ROOT_PASSWORD),
    # test_backend.MYSQL:
    #     u'mysql://root:{password}@127.0.0.1:3306'.format(password=DEFAULT_ROOT_PASSWORD),
    # test_backend.MARIADB:
    #     u'mysql://root:{password}@127.0.0.1:3307'.format(password=DEFAULT_ROOT_PASSWORD),
    test_config.MSSQL: "mssql+pyodbc:///?odbc_connect={}".format(escaped_pyodbc_parameter_string),
    # test_backend.SQLITE:
    #     u'sqlite:///:memory:',
}
