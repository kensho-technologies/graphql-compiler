# Copyright 2018-present Kensho Technologies, LLC.
from glob import glob
from os import path


def load_schema(client):
    """Read the schema file and apply the specified SQL updates to the client."""
    project_root = path.dirname(path.dirname(path.abspath(__file__)))
    file_path = path.join(project_root, 'test_data_tools/schema.sql')
    sql_files = glob(file_path)
    if len(sql_files) > 1:
        raise AssertionError(u'Multiple schema files found. Expected single `schema.sql` '
                             u'in graphql-compiler/graphql_compiler/tests/test_data_tools/')
    if len(sql_files) == 0 or sql_files[0] != file_path:
        raise AssertionError(u'Schema file not found. Expected graphql-compiler/graphql_compiler/'
                             u'tests/test_data_tools/schema.sql')

    with open(file_path, 'r') as update_file:
        for line in update_file:
            sanitized = line.strip()
            if len(sanitized) == 0 or sanitized[0] == '#':
                # comment or empty line, ignore
                continue

            client.command(sanitized)
