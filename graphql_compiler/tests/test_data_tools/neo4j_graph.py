# Copyright 2019-present Kensho Technologies, LLC.

from neo4j import GraphDatabase


NEO4J_SERVER = 'localhost'
NEO4J_PORT = 7687
NEO4J_USER = 'neo4j'
NEO4J_PASSWORD = 'root'  # nosec


class Neo4jClient(object):
    def __init__(self, graph_name):
        """Set up Neo4JClient using the default test credentials."""
        url = get_neo4j_url(graph_name)
        self.driver = GraphDatabase.driver(url, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_neo4j_url(database_name):
    """Return an Neo4j path for the specified database on the NEO4J_SERVER."""
    template = 'bolt://{}/{}'
    return template.format(NEO4J_SERVER, database_name)


def get_test_neo4j_graph(graph_name, generate_data_func):
    """Generate the test database and return the Neo4j client."""
    client = Neo4jClient(graph_name)
    generate_data_func(client)
    return client
