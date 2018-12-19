# Copyright 2018-present Kensho Technologies, LLC.
from glob import glob
from os import path


def generate_snapshot_data(client):
    """Create test DB from the SQL commands file for snapshot testing."""
    project_root = path.dirname(path.abspath(__file__))
    sql_files = glob(path.join(project_root, 'snapshot_data/*.sql'))
    _load_sql_files(client, sql_files)


def generate_integration_data(client):
    """Create test DB from the SQL commands file for snapshot testing."""
    project_root = path.dirname(path.abspath(__file__))
    sql_files = glob(path.join(project_root, 'integration_data/*.sql'))
    _load_sql_files(client, sql_files)


def _load_sql_files(client, sql_files):
    for filepath in sql_files:
        with open(filepath) as f:
            for command in f.readlines():
                sanitized_command = command.strip()
                if len(sanitized_command) == 0 or sanitized_command[0] == '#':
                    # comment or empty line, ignore
                    continue

                client.command(sanitized_command)
