from glob import glob
from os import path


def load_schema(client):
    """Read the schema file and apply the specified SQL updates to the client."""
    project_root = path.dirname(path.dirname(path.abspath(__file__)))
    file_path = path.join(project_root, 'test_data_tools/schema.sql')
    sql_files = glob(file_path)
    if len(sql_files) == 0:
        raise AssertionError(u'No schema file found. Expected /home/shankhabiswas/graphql-compiler/'
                             u'graphql_compiler/tests/test_data_tools/schema.sql')

    with open(file_path, 'r') as update_file:
        for line in update_file:
            sanitized = line.strip()
            if len(sanitized) == 0 or sanitized[0] == '#':
                sanitized = None

            if sanitized is None:
                # comment or empty line, ignore
                continue

            client.command(sanitized)
