# Copyright 2018-present Kensho Technologies, LLC.
from typing import Callable

from pyorient import OrientDB
from pyorient.constants import DB_TYPE_GRAPH
from pyorient.ogm import Config, Graph


ORIENTDB_SERVER = "localhost"
ORIENTDB_PORT = 2425
ORIENTDB_USER = "root"
ORIENTDB_PASSWORD = "root"  # nosec


def get_orientdb_url(database_name: str) -> str:
    """Return an OrientDB path for the specified database on the ORIENTDB_SERVER."""
    template = "memory://{}:{}/{}"
    return template.format(ORIENTDB_SERVER, ORIENTDB_PORT, database_name)


def get_test_orientdb_graph(
    graph_name: str,
    load_schema_func: Callable[[OrientDB], None],
    generate_data_func: Callable[[OrientDB], None],
) -> OrientDB:
    """Generate the test database and return the pyorient client."""
    url = get_orientdb_url(graph_name)
    config = Config.from_url(url, ORIENTDB_USER, ORIENTDB_PASSWORD, initial_drop=True)
    Graph(config, strict=True)

    client = OrientDB(host="localhost", port=ORIENTDB_PORT)
    client.connect(ORIENTDB_USER, ORIENTDB_PASSWORD)
    client.db_open(graph_name, ORIENTDB_USER, ORIENTDB_PASSWORD, db_type=DB_TYPE_GRAPH)

    load_schema_func(client)
    generate_data_func(client)

    return client
