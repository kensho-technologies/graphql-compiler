# Copyright 2018-present Kensho Technologies, LLC.
from pyorient import OrientDB
from pyorient.constants import DB_TYPE_GRAPH
from pyorient.ogm import Config, Graph

from .data_tool import generate_data
from .schema import load_schema


ORIENTDB_SERVER = "localhost"
ORIENTDB_PORT = 2424
ORIENTDB_USER = "root"
ORIENTDB_PASSWORD = "root"


def get_orientdb_url(database_name):
    """Return an OrientDB path for the specified database on the ORIENTDB_SERVER."""
    template = 'memory://{}/{}'
    return template.format(ORIENTDB_SERVER, database_name)


def get_test_graph(graph_name):
    """Generate the test database and return the pyorient client."""
    url = get_orientdb_url(graph_name)
    config = Config.from_url(url, ORIENTDB_USER, ORIENTDB_PASSWORD, initial_drop=True)
    Graph(config, strict=True)

    client = OrientDB('localhost', ORIENTDB_PORT)
    client.connect(ORIENTDB_USER, ORIENTDB_PASSWORD)
    client.db_open(graph_name, ORIENTDB_USER, ORIENTDB_PASSWORD, db_type=DB_TYPE_GRAPH)

    load_schema(client)
    generate_data(client)

    return client
