# Copyright 2018-present Kensho Technologies, LLC.
from glob import glob
from os import path


def generate_animals(client):
    """Create animal vertices from the file."""
    project_root = path.dirname(path.dirname(path.abspath(__file__)))
    sql_files = glob(path.join(project_root, 'test_data_tools/data/*.sql'))
    for filepath in sql_files:
        with open(filepath) as f:
            for command in f.readlines():
                sanitized_command = command.strip()
                if len(sanitized_command) == 0 or sanitized_command[0] == '#':
                    # comment or empty line, ignore
                    continue

                client.command(sanitized_command)
