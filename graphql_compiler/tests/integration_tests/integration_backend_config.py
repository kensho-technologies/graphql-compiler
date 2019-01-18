# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple

from .. import test_backend


DEFAULT_ROOT_PASSWORD = u'root'
MSSQL_ROOT_PASSWORD = u'Root-secure1'  # mssql has stricter root password restrictions

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

SQL_BACKEND_TO_CONNECTION_STRING = {
    test_backend.POSTGRES:
        u'postgresql://postgres:{password}@localhost:5432'.format(password=DEFAULT_ROOT_PASSWORD),
    test_backend.MYSQL:
        u'mysql://root:{password}@127.0.0.1:3306'.format(password=DEFAULT_ROOT_PASSWORD),
    test_backend.MARIADB:
        u'mysql://root:{password}@127.0.0.1:3307'.format(password=DEFAULT_ROOT_PASSWORD),
    test_backend.MSSQL:
        u'mssql+pymssql://SA:{password}@localhost:1433'.format(password=MSSQL_ROOT_PASSWORD),
    test_backend.SQLITE:
        u'sqlite:///:memory:',
}

SqlTestBackend = namedtuple('SqlTestBackend', (
    'engine',
    'base_connection_string',
))
