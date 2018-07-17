# Copyright 2018-present Kensho Technologies, LLC.
import sys
import time

import pytest

from .test_data_tools.graph import get_test_graph


# Pytest fixtures depend on name redefinitions to work,
# so this check generates tons of false-positives here.
# pylint: disable=redefined-outer-name


@pytest.fixture(scope='session')
def init_graph():
    """Return a client for an initialized db, with all test data imported."""
    graph_name = 'animals'

    # Try to set up the database for the test up to 20 times before giving up.
    set_up_successfully = False
    for _ in range(20):
        try:
            graph_client = get_test_graph(graph_name)
            set_up_successfully = True
            break
        except Exception as e:  # pylint: disable=broad-except
            sys.stderr.write(u'Failed to set up test DB: {}'.format(e))
            time.sleep(1)

    if not set_up_successfully:
        raise AssertionError(u'Failed to set up database without raising an exception!')

    return graph_client


@pytest.fixture(scope='class')
def graph_client(request, init_graph):
    """Get a client for an initialized db, with all test data imported."""
    request.cls.graph_client = init_graph
