# Copyright 2018-present Kensho Technologies, LLC.
from decimal import Decimal
from unittest import TestCase

from graphql.type import GraphQLID
from graphql.utils.schema_printer import print_schema
from parameterized import parameterized
import pytest

from graphql_compiler.tests import test_backend
from graphql_compiler.tests.test_helpers import generate_schema, generate_schema_graph

from ..test_helpers import SCHEMA_TEXT, compare_ignoring_whitespace, get_schema
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
@pytest.mark.slow
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
                cls.schema, graphql_query, parameters, engine, cls.sql_metadata)
        elif backend_name in MATCH_BACKENDS:
            results = compile_and_run_match_query(
                cls.schema, graphql_query, parameters, cls.graph_client)
        else:
            raise AssertionError(u'Unknown test backend {}.'.format(backend_name))
        return results

    @all_backends
    @integration_fixtures
    def test_simple_output(self, backend_name):
        graphql_query = '''
        {
            Animal {
                name @output(out_name: "animal_name")
                uuid @output(out_name: "animal_uuid")
            }
        }
        '''
        expected_results = [
            {'animal_name': 'Animal 1', 'animal_uuid': 'cfc6e625-8594-0927-468f-f53d864a7a51'},
            {'animal_name': 'Animal 2', 'animal_uuid': 'cfc6e625-8594-0927-468f-f53d864a7a52'},
            {'animal_name': 'Animal 3', 'animal_uuid': 'cfc6e625-8594-0927-468f-f53d864a7a53'},
            {'animal_name': 'Animal 4', 'animal_uuid': 'cfc6e625-8594-0927-468f-f53d864a7a54'},
        ]
        self.assertResultsEqual(graphql_query, {}, backend_name, expected_results)

    @all_backends
    @integration_fixtures
    def test_simple_filter(self, backend_name):
        graphql_query = '''
        {
            Animal {
                name @output(out_name: "animal_name")
                net_worth @output(out_name: "animal_net_worth")
                          @filter(op_name: "=", value: ["$net_worth"])
            }
        }
        '''
        parameters = {
            'net_worth': Decimal('100'),
        }
        expected_results = [
            {'animal_name': 'Animal 1', 'animal_net_worth': Decimal('100')},
        ]

        self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    @all_backends
    @integration_fixtures
    def test_two_filters(self, backend_name):
        graphql_query = '''
            {
                Animal {
                    name @output(out_name: "animal_name")
                    net_worth @output(out_name: "animal_net_worth")
                              @filter(op_name: ">=", value: ["$lower_bound_exclusive"])
                              @filter(op_name: "in_collection", value: ["$net_worths"])
                }
            }
            '''
        parameters = {
            'lower_bound_exclusive': Decimal('200'),
            'net_worths': [Decimal('300'), Decimal('400')],
        }
        expected_results = [
            {'animal_name': 'Animal 3', 'animal_net_worth': Decimal('300')},
            {'animal_name': 'Animal 4', 'animal_net_worth': Decimal('400')},
        ]

        self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    @all_backends
    @integration_fixtures
    def test_has_substring_precedence(self, backend_name):
        graphql_query = '''
        {
            Animal {
                name @output(out_name: "animal_name")
                     @filter(op_name: "has_substring", value: ["$wide_substring"])
                     @filter(op_name: "has_substring", value: ["$narrow_substring"])
            }
        }
        '''
        parameters = {
            # matches all animal names
            'wide_substring': 'Animal',
            # narrows set to just ['Animal 3']
            'narrow_substring': '3',
        }
        expected_results = [
            {'animal_name': 'Animal 3'},
        ]
        self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    @integration_fixtures
    def test_snapshot_graphql_schema_from_orientdb_schema(self):
        class_to_field_type_overrides = {
            'UniquelyIdentifiable': {'uuid': GraphQLID}
        }
        schema, _ = generate_schema(self.graph_client,
                                    class_to_field_type_overrides=class_to_field_type_overrides)
        compare_ignoring_whitespace(self, SCHEMA_TEXT, print_schema(schema), None)

    @integration_fixtures
    def test_override_field_types(self):
        class_to_field_type_overrides = {
            'UniquelyIdentifiable': {'uuid': GraphQLID}
        }
        schema, _ = generate_schema(self.graph_client,
                                    class_to_field_type_overrides=class_to_field_type_overrides)
        # Since Animal implements the UniquelyIdentifiable interface and since we we overrode
        # UniquelyIdentifiable's uuid field to be of type GraphQLID when we generated the schema,
        # then Animal's uuid field should also be of type GrapqhQLID.
        self.assertEqual(schema.get_type('Animal').fields['uuid'].type, GraphQLID)

    @integration_fixtures
    def test_include_admissible_non_graph_class(self):
        schema, _ = generate_schema(self.graph_client)
        # Included abstract non-vertex classes whose non-abstract subclasses are all vertexes.
        self.assertIsNotNone(schema.get_type('UniquelyIdentifiable'))

    @integration_fixtures
    def test_selectively_hide_classes(self):
        schema, _ = generate_schema(self.graph_client, hidden_classes={'Animal'})
        self.assertNotIn('Animal', schema.get_type_map())

    @integration_fixtures
    def test_parsed_schema_element_custom_fields(self):
        schema_graph = generate_schema_graph(self.graph_client)
        parent_of_edge = schema_graph.get_element_by_class_name('Animal_ParentOf')
        expected_custom_class_fields = {
            'human_name_in': 'Parent',
            'human_name_out': 'Child'
        }
        self.assertEqual(expected_custom_class_fields, parent_of_edge.class_fields)
# pylint: enable=no-member
