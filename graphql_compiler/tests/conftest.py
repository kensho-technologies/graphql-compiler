from .test_data_tools.graph import get_test_graph

import pytest

from test_data_tools.graph import get_test_graph


@pytest.fixture(scope='session')
def init_graph():
    """Return a client for an initialized db, with all test data imported."""
    graph_name = 'animals'
    graph_client = get_test_graph(graph_name)
    return graph_client


@pytest.fixture(scope='class')
def test_db(request, init_graph):
    """Get a client for an initialized db, with all test data imported."""
    request.cls.graph_client = init_graph
