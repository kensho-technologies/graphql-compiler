# Copyright 2019-present Kensho Technologies, LLC.
from typing import Callable

from neo4j import GraphDatabase


NEO4J_SERVER = "localhost"
NEO4J_PORT = 7688
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "root"  # nosec


class Neo4jClient(object):
    def __init__(self, graph_name: str) -> None:
        """Set up Neo4JClient using the default test credentials."""
        url = get_neo4j_url(graph_name)
        self.driver = GraphDatabase.driver(url, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_neo4j_url(database_name: str) -> str:
    """Return an Neo4j path for the specified database on the NEO4J_SERVER."""
    template = "bolt://{}:{}/{}"
    return template.format(NEO4J_SERVER, NEO4J_PORT, database_name)


def get_test_neo4j_graph(
    graph_name: str, generate_data_func: Callable[[Neo4jClient], None]
) -> Neo4jClient:
    """Generate the test database and return the Neo4j client."""
    client = Neo4jClient(graph_name)
    generate_data_func(client)
    return client
