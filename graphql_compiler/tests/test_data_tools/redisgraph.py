# Copyright 2019-present Kensho Technologies, LLC.

import redis
from redisgraph import Node, Edge, Graph

REDISGRAPH_SERVER = 'localhost'
REDISGRAPH_PORT = 6379


def get_test_redisgraph_graph(graph_name, generate_data_func):
    """Generate the test database and return the Redisgraph client."""
    redis_client = redis.Redis(host=REDISGRAPH_SERVER, port=REDISGRAPH_PORT) # note this is a Redis client, not Redisgraph
    graph_client = Graph(graph_name, redis_client) # connect to the graph itself
    generate_data_func(graph_client)
    return graph_client
