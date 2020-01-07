# Copyright 2018-present Kensho Technologies, LLC.
from glob import glob
from os import path
from typing import Callable

from pyorient import OrientDB
from pyorient.constants import DB_TYPE_GRAPH
from pyorient.ogm import Config, Graph

ORIENTDB_SERVER = "localhost"
ORIENTDB_PORT = 2424
ORIENTDB_USER = "root"
ORIENTDB_PASSWORD = "root"  # nosec


def get_orientdb_url(database_name: str) -> str:
    """Return an OrientDB path for the specified database on the ORIENTDB_SERVER."""
    template = "memory://{}/{}"
    return template.format(ORIENTDB_SERVER, database_name)


def get_test_orientdb_graph(
    graph_name: str,
    load_schema_func: Callable[[OrientDB], None],
    generate_data_func: Callable[[OrientDB], None],
) -> OrientDB:
    """Generate the test database and return the pyorient client."""
    url = get_orientdb_url(graph_name)
    config = Config.from_url(url, ORIENTDB_USER, ORIENTDB_PASSWORD, initial_drop=True)
    Graph(config, strict=True)

    client = OrientDB("localhost", ORIENTDB_PORT)
    client.connect(ORIENTDB_USER, ORIENTDB_PASSWORD)
    client.db_open(graph_name, ORIENTDB_USER, ORIENTDB_PASSWORD, db_type=DB_TYPE_GRAPH)

    load_schema_func(client)
    generate_data_func(client)

    return client


def load_schema(client: OrientDB) -> None:
    """Read the schema file and apply the specified SQL updates to the client."""
    project_root = path.dirname(path.dirname(path.abspath(__file__)))
    file_path = path.join(project_root, "test_data_tools/schema.sql")
    sql_files = glob(file_path)
    if len(sql_files) > 1:
        raise AssertionError(
            u"Multiple schema files found. Expected single `schema.sql` "
            u"in graphql-compiler/graphql_compiler/tests/test_data_tools/"
        )
    if len(sql_files) == 0 or sql_files[0] != file_path:
        raise AssertionError(
            u"Schema file not found. Expected graphql-compiler/graphql_compiler/"
            u"tests/test_data_tools/schema.sql"
        )

    with open(file_path, "r") as update_file:
        for line in update_file:
            sanitized = line.strip()
            if len(sanitized) == 0 or sanitized[0] == "#":
                # comment or empty line, ignore
                continue

            client.command(sanitized)
