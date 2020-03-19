# Copyright 2018-present Kensho Technologies, LLC.

from funcy import retry
import pytest
import six

from .test_data_tools.data_tool import (
    generate_neo4j_integration_data,
    generate_orient_integration_data,
    generate_orient_snapshot_data,
    generate_redisgraph_integration_data,
    generate_sql_integration_data,
    init_sql_integration_test_backends,
    tear_down_integration_test_backends,
)
from .test_data_tools.neo4j_graph import get_test_neo4j_graph
from .test_data_tools.orientdb_graph import get_test_orientdb_graph
from .test_data_tools.redisgraph_graph import get_test_redisgraph_graph
from .test_data_tools.schema import load_schema


GRAPH_NAME = "animals"  # Name for integration test database


# Pytest fixtures depend on name redefinitions to work,
# so this check generates tons of false-positives here.
# pylint: disable=redefined-outer-name


@pytest.fixture(scope="session")
def init_snapshot_orientdb_client():
    """Return a client for an initialized db, with all test data imported."""
    return _init_orientdb_client(load_schema, generate_orient_snapshot_data)


@pytest.fixture(scope="session")
def init_integration_orientdb_client():
    """Return a client for an initialized db, with all test data imported."""
    return _init_orientdb_client(load_schema, generate_orient_integration_data)


# retry is a decorator that attempts to call the decorated function repeatedly, and it takes a
# parameter "call". Call is the function being decorated, so we don't need to specify which
# parameters the retry decorator takes. So, we can disable pylint's warning about
# missing parameters here.
@retry(20, timeout=1)  # pylint: disable=no-value-for-parameter
def _init_orientdb_client(load_schema_func, generate_data_func):
    """Set up a database and return a client that can query the database."""
    orientdb_client = get_test_orientdb_graph(GRAPH_NAME, load_schema_func, generate_data_func)
    return orientdb_client


@pytest.fixture(scope="session")
def init_integration_neo4j_client():
    """Return a client for an initialized db, with all test data imported."""
    return _init_neo4j_client(generate_neo4j_integration_data)


# We can disable pylint's warning about missing parameters here because retry is a decorator. See
# _init_orientdb_client function comment.
@retry(20, timeout=1)  # pylint: disable=no-value-for-parameter
def _init_neo4j_client(generate_data_func):
    """Set up a database and return a client that can query the database."""
    neo4j_client = get_test_neo4j_graph(GRAPH_NAME, generate_data_func)
    return neo4j_client


@pytest.fixture(scope="session")
def init_integration_redisgraph_client():
    """Return a client for an initialized db, with all test data imported."""
    return _init_redisgraph_client(generate_redisgraph_integration_data)


# We can disable pylint's warning about missing parameters here because retry is a decorator. See
# _init_orientdb_client function comment.
@retry(20, timeout=1)  # pylint: disable=no-value-for-parameter
def _init_redisgraph_client(generate_data_func):
    """Set up a database and return a client that can query the database."""
    redisgraph_client = get_test_redisgraph_graph(GRAPH_NAME, generate_data_func)
    return redisgraph_client


@pytest.fixture(scope="class")
def snapshot_orientdb_client(request, init_snapshot_orientdb_client):
    """Get a client for an initialized db, with all test data imported."""
    request.cls.orientdb_client = init_snapshot_orientdb_client


@pytest.fixture(scope="class")
def integration_orientdb_client(request, init_integration_orientdb_client):
    """Get a client for an initialized db, with all test data imported."""
    request.cls.orientdb_client = init_integration_orientdb_client


@pytest.fixture(scope="class")
def integration_neo4j_client(request, init_integration_neo4j_client):
    """Get a client for an initialized db, with all test data imported."""
    request.cls.neo4j_client = init_integration_neo4j_client


@pytest.fixture(scope="class")
def integration_redisgraph_client(request, init_integration_redisgraph_client):
    """Get a client for an initialized db, with all test data imported."""
    request.cls.redisgraph_client = init_integration_redisgraph_client


@pytest.fixture(scope="class")
def sql_integration_data(request):
    """Generate integration data for SQL backends."""
    # initialize each SQL backend
    sql_test_backends = init_sql_integration_test_backends()
    sql_schema_info = generate_sql_integration_data(sql_test_backends)
    # make sql engines accessible within the test class
    request.cls.sql_backend_name_to_engine = {
        backend_name: sql_test_backend.engine
        for backend_name, sql_test_backend in six.iteritems(sql_test_backends)
    }
    request.cls.sql_schema_info = sql_schema_info
    # yield the fixture to allow testing class to run
    yield
    # tear down the fixture after the testing class runs all tests
    # including rolling back transaction to ensure all fixture data removed.
    tear_down_integration_test_backends(sql_test_backends)


def pytest_addoption(parser):
    """Add command line options to py.test to allow for slow tests to be skipped."""
    parser.addoption("--skip-slow", action="store_true", default=False, help="Skip slow tests.")


def pytest_configure(config):
    """Initialize the pytest configuration. Executed prior to any tests."""
    config.addinivalue_line(
        # Define the "slow" pytest mark, to avoid PytestUnknownMarkWarning being generated.
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"' or --skip-slow)",
    )


def pytest_collection_modifyitems(config, items):
    """Modify py.test behavior based on command line options."""
    if not config.getoption("--skip-slow"):
        return

    # skip tests market with the @pytest.mark.slow decorator
    skip_slow = pytest.mark.skip(reason="--skip-slow command line argument supplied")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
