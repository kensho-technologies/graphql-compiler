import pytest
import time

from .test_data_tools.graph import get_test_graph


@pytest.fixture(scope='session')
def init_graph():
    """Return a client for an initialized db, with all test data imported."""
    graph_name = 'animals'

    # Try to set up the database for the test up to 5 times before giving up.
    set_up_successfully = False
    for _ in range(5):
        try:
            graph_client = get_test_graph(graph_name)
            set_up_successfully = True
        except:
            time.sleep(1)

    if not set_up_successfully:
        raise AssertionError(u'Failed to set up database without raising an exception!')

    return graph_client


@pytest.fixture(scope='class')
def test_db(request, init_graph):
    """Get a client for an initialized db, with all test data imported."""
    request.cls.graph_client = init_graph
