# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql_compiler.tests.test_backend import TestBackend


DEFAULT_ROOT_PASSWORD = u'root'
MSSQL_ROOT_PASSWORD = u'Root-secure1'  # mssql has stricter root password restrictions

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

SQL_BACKEND_TO_CONNECTION_STRING = {
    TestBackend.POSTGRES:
        u'postgresql://postgres:{password}@localhost:5432'.format(password=DEFAULT_ROOT_PASSWORD),
    TestBackend.MYSQL:
        u'mysql://root:{password}@127.0.0.1:3306'.format(password=DEFAULT_ROOT_PASSWORD),
    TestBackend.MARIADB:
        u'mysql://root:{password}@127.0.0.1:3307'.format(password=DEFAULT_ROOT_PASSWORD),
    TestBackend.MSSQL:
        u'mssql+pymssql://SA:{password}@localhost:1433'.format(password=MSSQL_ROOT_PASSWORD),
    TestBackend.SQLITE:
        u'sqlite:///:memory:',
}

SqlTestBackend = namedtuple('SqlTestBackend', (
    'connection_string',
    'engine',
    'connection',
    'transaction',
))
