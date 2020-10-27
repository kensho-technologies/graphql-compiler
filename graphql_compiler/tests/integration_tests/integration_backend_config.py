# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple

from six.moves.urllib.parse import quote_plus

from .. import test_backend


DEFAULT_ROOT_PASSWORD = "root"  # nosec

SQL_BACKENDS = {
    test_backend.POSTGRES,
    test_backend.MYSQL,
    test_backend.MARIADB,
    test_backend.MSSQL,
    test_backend.SQLITE,
}

# sqlite does not require that a DB be created/dropped for testing
EXPLICIT_DB_BACKENDS = {
    test_backend.POSTGRES,
    test_backend.MYSQL,
    test_backend.MARIADB,
    test_backend.MSSQL,
}

MATCH_BACKENDS = {
    test_backend.ORIENTDB,
}

# Split Neo4j and RedisGraph because RedisGraph doesn't support all Neo4j features.
NEO4J_BACKENDS = {
    test_backend.NEO4J,
}

REDISGRAPH_BACKENDS = {
    test_backend.REDISGRAPH,
}

pyodbc_parameter_string = "DRIVER={driver};SERVER={server};UID={uid};PWD={pwd}".format(  # nosec
    driver="{ODBC Driver 17 for SQL SERVER}",
    server="127.0.0.1,1434",  # Do not change to 'localhost'.
    # You won't be able to connect with the db.
    uid="SA",  # System Administrator.
    pwd="Root-secure1",
)

# delimeters must be URL escaped
escaped_pyodbc_parameter_string = quote_plus(pyodbc_parameter_string)

SQL_BACKEND_TO_CONNECTION_STRING = {
    # HACK(bojanserafimov): Entries are commented-out because MSSQL is the only one whose scheme
    #                       initialization is properly configured, with a hierarchy of multiple
    #                       databases and schemas. I'm keeping the code to remember the connection
    #                       string formats.
    #
    test_backend.POSTGRES: "postgresql://postgres:{password}@localhost:5433".format(
        password=DEFAULT_ROOT_PASSWORD
    ),
    # test_backend.MYSQL:
    #     'mysql://root:{password}@127.0.0.1:3307'.format(password=DEFAULT_ROOT_PASSWORD),
    # test_backend.MARIADB:
    #     'mysql://root:{password}@127.0.0.1:3308'.format(password=DEFAULT_ROOT_PASSWORD),
    test_backend.MSSQL: "mssql+pyodbc:///?odbc_connect={}".format(escaped_pyodbc_parameter_string),
    # test_backend.SQLITE:
    #     'sqlite:///:memory:',
}

SqlTestBackend = namedtuple(
    "SqlTestBackend",
    (
        "engine",
        "base_connection_string",
    ),
)
