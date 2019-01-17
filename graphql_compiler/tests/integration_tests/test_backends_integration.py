# Copyright 2018-present Kensho Technologies, LLC.
from unittest import TestCase

from parameterized import parameterized
import pytest

from graphql_compiler.tests import test_backend

from ..test_helpers import get_schema
from .integration_backend_config import MATCH_BACKENDS, SQL_BACKENDS
from .integration_test_helpers import (
    compile_and_run_match_query, compile_and_run_sql_query, sort_db_results
)


# Store the test parametrization for running against all backends. Individual tests can customize
# the list of backends to test against with the full @parametrized.expand([...]) decorator.
all_backends = parameterized.expand([
    test_backend.ORIENTDB,
    test_backend.POSTGRES,
    test_backend.MARIADB,
    test_backend.MYSQL,
    test_backend.SQLITE,
    test_backend.MSSQL,
])

# Store the typical fixtures required for an integration tests.
# Individual tests can supply the full @pytest.mark.usefixtures to override if necessary.
integration_fixtures = pytest.mark.usefixtures(
    'integration_graph_client',
    'sql_integration_data',
)


# The following test class uses several fixtures adding members that pylint
# does not recognize
# pylint: disable=no-member
class IntegrationTests(TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        cls.maxDiff = None
        cls.schema = get_schema()

    def assertResultsEqual(self, graphql_query, parameters, backend_name, expected_results):
        """Assert that two lists of DB results are equal, independent of order."""
        backend_results = self.compile_and_run_query(graphql_query, parameters, backend_name)
        try:
            self.assertListEqual(sort_db_results(expected_results),
                                 sort_db_results(backend_results))
        except AssertionError as error:
            # intercept and modify error message to indicate which backend(s) failed
            args = [u'Failure for backend "{}": {}'.format(backend_name, error.args[0])]
            args.extend(error.args[1:])
            error.args = tuple(args)
            raise

    @classmethod
    def compile_and_run_query(cls, graphql_query, parameters, backend_name):
        """Compiles and runs the graphql query with the supplied parameters against all backends.

        Args:
            graphql_query: str, GraphQL query string to run against every backend.
            parameters: Dict[str, Any], input parameters to the query.
            backend_name: str, the name of the test backend to get results from.

        Returns:
            List[Dict[str, Any]], backend results as a list of dictionaries.
        """
        if backend_name in SQL_BACKENDS:
            engine = cls.sql_backend_name_to_engine[backend_name]
            results = compile_and_run_sql_query(
                cls.schema, graphql_query, parameters, engine)
        elif backend_name in MATCH_BACKENDS:
            results = compile_and_run_match_query(
                cls.schema, graphql_query, parameters, cls.graph_client)
        else:
            raise AssertionError(u'Unknown test backend {}.'.format(backend_name))
        return results

    @all_backends
    @integration_fixtures
    def test_backends(self, backend_name):
        graphql_query = '''
        {
            Animal {
                name @output(out_name: "animal_name")
            }
        }
        '''
        expected_results = [
            {'animal_name': 'Animal 1'},
            {'animal_name': 'Animal 2'},
            {'animal_name': 'Animal 3'},
            {'animal_name': 'Animal 4'},
        ]
        self.assertResultsEqual(graphql_query, {}, backend_name, expected_results)

# pylint: enable=no-member
