# Copyright 2020-present Kensho Technologies, LLC.
from os import path

from graphql_compiler.tests.integration_tests.data.integration_data import (
    _load_sql_files_to_orient_client,
)


def generate_orient_snapshot_data(client):
    """Create OrientDB test DB from the SQL commands file for snapshot testing."""
    project_root = path.dirname(path.abspath(__file__))
    sql_files = [path.join(project_root, "orientdb_snapshot_data.sql")]

    _load_sql_files_to_orient_client(client, sql_files)
