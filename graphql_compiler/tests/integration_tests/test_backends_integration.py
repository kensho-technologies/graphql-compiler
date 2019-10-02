# Copyright 2018-present Kensho Technologies, LLC.
import datetime
from decimal import Decimal
from unittest import TestCase

from graphql.type import GraphQLID
from graphql.utils.schema_printer import print_schema
from parameterized import parameterized
import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table

from ...schema_generation.orientdb.schema_properties import ORIENTDB_BASE_VERTEX_CLASS_NAME
from ...schema_generation.sqlalchemy.sqlalchemy_reflector import (
    fast_sql_server_reflect, get_first_column_in_table
)
from ...tests import test_backend
from ...tests.test_helpers import generate_schema, generate_schema_graph
from ..test_helpers import SCHEMA_TEXT, compare_ignoring_whitespace, get_schema
from .integration_backend_config import (
    MATCH_BACKENDS, NEO4J_BACKENDS, REDISGRAPH_BACKENDS, SQL_BACKENDS
)
from .integration_test_helpers import (
    compile_and_run_match_query, compile_and_run_neo4j_query, compile_and_run_redisgraph_query,
    compile_and_run_sql_query, sort_db_results
)


all_backends_list = [
    test_backend.ORIENTDB,
    test_backend.MSSQL,
    test_backend.NEO4J,
    test_backend.REDISGRAPH,
]


# Store the typical fixtures required for an integration tests.
# Individual tests can supply the full @pytest.mark.usefixtures to override if necessary.
integration_fixtures = pytest.mark.usefixtures(
    'integration_neo4j_client',
    'integration_orientdb_client',
    'integration_redisgraph_client',
    'sql_integration_data',
)


def use_all_backends(except_backends=()):
    """Decorate test functions to make them use specific backends.

    By default, tests decorated with this function use all backends. However, some backends don't
    support certain features, so it's useful to exclude certain backends for individual tests.

    Args:
        except_backends: Tuple[str], optional argument. Tuple of backend strings from
                         test_backend.py to exclude in testing.

    Returns:
        function that expands tests for each non-excluded backend.
    """
    non_excluded_backends = [
        backend for backend in all_backends_list
        if backend not in except_backends
    ]
    # parameterized.expand() takes in a list of test parameters (in this case, backend strings
    # specifying which backends to use for the test) and auto-generates a test function for each
    # backend. For more information see https://github.com/wolever/parameterized
    return parameterized.expand(non_excluded_backends)


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
                cls.sql_schema_info, graphql_query, parameters, engine)
        elif backend_name in MATCH_BACKENDS:
            results = compile_and_run_match_query(
                cls.schema, graphql_query, parameters, cls.orientdb_client)
        elif backend_name in NEO4J_BACKENDS:
            results = compile_and_run_neo4j_query(
                cls.schema, graphql_query, parameters, cls.neo4j_client)
        elif backend_name in REDISGRAPH_BACKENDS:
            results = compile_and_run_redisgraph_query(
                cls.schema, graphql_query, parameters, cls.redisgraph_client)
        else:
            raise AssertionError(u'Unknown test backend {}.'.format(backend_name))
        return results

    @use_all_backends()
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

    # Cypher doesn't support Decimals (both Neo4j [1] and RedisGraph [2])
    # [0] https://oss.redislabs.com/redisgraph/cypher_support/#types
    # [1] https://neo4j.com/docs/cypher-manual/current/syntax/values/
    # [2] https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf
    @use_all_backends(except_backends=(test_backend.NEO4J, test_backend.REDISGRAPH))
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

    @integration_fixtures
    def test_edge_from_superclass_with_preferred_location_not_at_root(self):
        graphql_query = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Entity_Related {
                    name @output(out_name: "related_animal_name")
                    alias @filter(op_name: "contains", value: ["$name"])
                }
            }
        }'''
        parameters = {
            'name': 'Species 2',
        }
        expected_results = []

        self.assertResultsEqual(graphql_query, parameters, test_backend.ORIENTDB, expected_results)

    # Redisgraph doesn't support lists so in_collection doesn't make sense. [0]
    # Cypher doesn't support Decimals (both Neo4j [1] and RedisGraph [2])
    # [0] https://oss.redislabs.com/redisgraph/cypher_support/#types
    # [1] https://neo4j.com/docs/cypher-manual/current/syntax/values/
    # [2] https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf
    @use_all_backends(except_backends=(test_backend.REDISGRAPH, test_backend.NEO4J))
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

    # RedisGraph doesn't support string function CONTAINS
    # https://oss.redislabs.com/redisgraph/cypher_support/#string-operators
    @use_all_backends(except_backends=(test_backend.REDISGRAPH))
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
    def test_recurse(self):
        parameters = {
            'starting_animal_name': 'Animal 1',
        }

        # (query, expected_results) pairs. All of them running with the same parameters.
        # The queries are ran in the order specified here.
        queries = [
            # Query 1: Just the root
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                         @output(out_name: "root_name")
                }
            }''', [
                {'root_name': 'Animal 1'}
            ]),
            # Query 2: Immediate children
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        name @output(out_name: "descendant_name")
                    }
                }
            }''', [
                {'descendant_name': 'Animal 1'},
                {'descendant_name': 'Animal 2'},
                {'descendant_name': 'Animal 3'},
            ]),
            # Query 3: Grandchildren
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        out_Animal_ParentOf {
                            name @output(out_name: "descendant_name")
                        }
                    }
                }
            }''', [
                {'descendant_name': 'Animal 1'},
                {'descendant_name': 'Animal 2'},
                {'descendant_name': 'Animal 3'},
                {'descendant_name': 'Animal 4'},
            ]),
            # Query 4: Grand-grandchildren
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        out_Animal_ParentOf {
                            out_Animal_ParentOf {
                                name @output(out_name: "descendant_name")
                            }
                        }
                    }
                }
            }''', [
                {'descendant_name': 'Animal 1'},
                {'descendant_name': 'Animal 2'},
                {'descendant_name': 'Animal 3'},
                {'descendant_name': 'Animal 4'},
            ]),
            # Query 5: Recurse depth 1
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @recurse(depth: 1){
                        name @output(out_name: "descendant_name")
                    }
                }
            }''', [
                {'descendant_name': 'Animal 1'},  # depth 0 match
                {'descendant_name': 'Animal 1'},  # depth 1 match
                {'descendant_name': 'Animal 2'},  # depth 1 match
                {'descendant_name': 'Animal 3'},  # depth 1 match
            ]),
            # Query 6: Recurse depth 2
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @recurse(depth: 2){
                        name @output(out_name: "descendant_name")
                    }
                }
            }''', [
                {'descendant_name': 'Animal 1'},  # depth 0 match
                {'descendant_name': 'Animal 1'},  # depth 1 match
                {'descendant_name': 'Animal 2'},  # depth 1 match
                {'descendant_name': 'Animal 3'},  # depth 1 match
                {'descendant_name': 'Animal 1'},  # depth 2 match
                {'descendant_name': 'Animal 2'},  # depth 2 match
                {'descendant_name': 'Animal 3'},  # depth 2 match
                {'descendant_name': 'Animal 4'},  # depth 2 match
            ]),
            # Query 7: Recurse depth 3
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @recurse(depth: 3){
                        name @output(out_name: "descendant_name")
                    }
                }
            }''', [
                {'descendant_name': 'Animal 1'},  # depth 0 match
                {'descendant_name': 'Animal 1'},  # depth 1 match
                {'descendant_name': 'Animal 2'},  # depth 1 match
                {'descendant_name': 'Animal 3'},  # depth 1 match
                {'descendant_name': 'Animal 1'},  # depth 2 match
                {'descendant_name': 'Animal 2'},  # depth 2 match
                {'descendant_name': 'Animal 3'},  # depth 2 match
                {'descendant_name': 'Animal 4'},  # depth 2 match
                {'descendant_name': 'Animal 1'},  # depth 3 match
                {'descendant_name': 'Animal 2'},  # depth 3 match
                {'descendant_name': 'Animal 3'},  # depth 3 match
                {'descendant_name': 'Animal 4'},  # depth 3 match
            ]),
        ]

        # TODO(bojanserafimov): Only testing in MSSQL because none of our backends agree on recurse
        #                       semantics when multiple paths to the same output are inolved:
        #                       - Our Match backend would represent each result once, even though it
        #                         was reached multiple times by different paths.
        #                       - Our SQL backend would duplicate the output row once for each path
        #                       - Our Neo4j backend would find all different paths that use each
        #                         edge at most once, and duplicate the result for each one.
        for graphql_query, expected_results in queries:
            self.assertResultsEqual(graphql_query, parameters, test_backend.MSSQL, expected_results)

    @use_all_backends(except_backends=(
        test_backend.MSSQL,  # Not implemented yet
        test_backend.REDISGRAPH,  # Not implemented yet
    ))
    @integration_fixtures
    def test_fold_basic(self, backend_name):
        # (query, args, expected_results) tuples.
        # The queries are ran in the order specified here.
        queries = [
            # Query 1: Unfolded children of Animal 1
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        name @output(out_name: "descendant_name")
                    }
                }
            }''', {
                'starting_animal_name': 'Animal 1',
            }, [
                {'descendant_name': 'Animal 1'},
                {'descendant_name': 'Animal 2'},
                {'descendant_name': 'Animal 3'},
            ]),
            # Query 2: Folded children of Animal 1
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @fold {
                        name @output(out_name: "child_names")
                    }
                }
            }''', {
                'starting_animal_name': 'Animal 1',
            }, [
                {'child_names': ['Animal 1', 'Animal 2', 'Animal 3']},
            ]),
            # Query 3: Unfolded children of Animal 4
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        name @output(out_name: "descendant_name")
                    }
                }
            }''', {
                'starting_animal_name': 'Animal 4',
            }, []),
            # Query 4: Folded children of Animal 4
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @fold {
                        name @output(out_name: "child_names")
                    }
                }
            }''', {
                'starting_animal_name': 'Animal 4',
            }, [
                {'child_names': []},
            ]),
        ]

        for graphql_query, parameters, expected_results in queries:
            self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    @use_all_backends(except_backends=(
        test_backend.REDISGRAPH,  # TODO(bojanserafimov): Resolve syntax error
    ))
    @integration_fixtures
    def test_optional_basic(self, backend_name):
        # (query, args, expected_results) tuples.
        # The queries are ran in the order specified here.
        queries = [
            # Query 1: Children of Animal 1
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        name @output(out_name: "child_name")
                    }
                }
            }''', {
                'starting_animal_name': 'Animal 1',
            }, [
                {'child_name': 'Animal 1'},
                {'child_name': 'Animal 2'},
                {'child_name': 'Animal 3'},
            ]),
            # Query 2: Grandchildren of Animal 1
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        out_Animal_ParentOf {
                            name @output(out_name: "grandchild_name")
                        }
                    }
                }
            }''', {
                'starting_animal_name': 'Animal 1',
            }, [
                {'grandchild_name': 'Animal 1'},
                {'grandchild_name': 'Animal 2'},
                {'grandchild_name': 'Animal 3'},
                {'grandchild_name': 'Animal 4'},
            ]),
            # Query 3: Unfolded children of Animal 1 and their children
            ('''
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        name @output(out_name: "child_name")
                        out_Animal_ParentOf @optional {
                            name @output(out_name: "grandchild_name")
                        }
                    }
                }
            }''', {
                'starting_animal_name': 'Animal 1',
            }, [
                {'child_name': 'Animal 1', 'grandchild_name': 'Animal 1'},
                {'child_name': 'Animal 1', 'grandchild_name': 'Animal 2'},
                {'child_name': 'Animal 1', 'grandchild_name': 'Animal 3'},
                {'child_name': 'Animal 2', 'grandchild_name': None},
                {'child_name': 'Animal 3', 'grandchild_name': 'Animal 4'},
            ]),
        ]

        for graphql_query, parameters, expected_results in queries:
            self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    # RedisGraph doesn't support temporal types, so Date types aren't supported.
    @use_all_backends(except_backends=(test_backend.REDISGRAPH))
    @integration_fixtures
    def test_filter_on_date(self, backend_name):
        graphql_query = '''
        {
            Animal {
                name @output(out_name: "animal_name")
                birthday @filter(op_name: "=", value: ["$birthday"])
            }
        }
        '''
        parameters = {
            'birthday': datetime.date(1975, 3, 3),
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
        schema, _ = generate_schema(self.orientdb_client,
                                    class_to_field_type_overrides=class_to_field_type_overrides,
                                    hidden_classes={ORIENTDB_BASE_VERTEX_CLASS_NAME})
        compare_ignoring_whitespace(self, SCHEMA_TEXT, print_schema(schema), None)

    @integration_fixtures
    def test_override_field_types(self):
        class_to_field_type_overrides = {
            'UniquelyIdentifiable': {'uuid': GraphQLID}
        }
        schema, _ = generate_schema(self.orientdb_client,
                                    class_to_field_type_overrides=class_to_field_type_overrides)
        # Since Animal implements the UniquelyIdentifiable interface and since we we overrode
        # UniquelyIdentifiable's uuid field to be of type GraphQLID when we generated the schema,
        # then Animal's uuid field should also be of type GrapqhQLID.
        self.assertEqual(schema.get_type('Animal').fields['uuid'].type, GraphQLID)

    @integration_fixtures
    def test_include_admissible_non_graph_class(self):
        schema, _ = generate_schema(self.orientdb_client)
        # Included abstract non-vertex classes whose non-abstract subclasses are all vertexes.
        self.assertIsNotNone(schema.get_type('UniquelyIdentifiable'))

    @integration_fixtures
    def test_selectively_hide_classes(self):
        schema, _ = generate_schema(self.orientdb_client, hidden_classes={'Animal'})
        self.assertNotIn('Animal', schema.get_type_map())

    @integration_fixtures
    def test_parsed_schema_element_custom_fields(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        parent_of_edge = schema_graph.get_element_by_class_name('Animal_ParentOf')
        expected_custom_class_fields = {
            'human_name_in': 'Parent',
            'human_name_out': 'Child'
        }
        self.assertEqual(expected_custom_class_fields, parent_of_edge.class_fields)

    @integration_fixtures
    def test_sqlalchemy_fast_reflect(self):
        engine = IntegrationTests.sql_backend_name_to_engine[test_backend.MSSQL]

        table_without_primary_key = Table(
            'TableWithoutPrimaryKey',
            MetaData(),
            Column('column_with_no_primary_key', Integer()),
            schema='db_1.schema_1'
        )
        table_with_many_primary_keys = Table(
            'TableWithManyPrimaryKeyColumns',
            MetaData(),
            Column('primary_key_column1', Integer(), primary_key=True),
            Column('primary_key_column2', Integer(), primary_key=True),
            schema='db_1.schema_1'
        )

        table_without_primary_key.create(bind=engine)
        table_with_many_primary_keys.create(bind=engine)

        metadata = MetaData()
        fast_sql_server_reflect(engine, metadata, 'db_1.schema_1',
                                primary_key_selector=get_first_column_in_table)

        # Test expected tables are included.
        self.assertIn('db_1.schema_1.Animal', metadata.tables)
        self.assertIn('db_1.schema_1.Species', metadata.tables)
        self.assertNotIn('db_1.schema_2.FeedingEvent', metadata.tables)

        # Test column types are correctly reflected.
        self.assertIsInstance(metadata.tables['db_1.schema_1.Animal'].columns['color'].type, String)

        # Test explicit primary key reflection.
        explicit_primary_key_columns = set(
            column.name
            for column in
            metadata.tables[table_with_many_primary_keys.fullname].primary_key
        )
        self.assertEqual({'primary_key_column1', 'primary_key_column2'},
                         explicit_primary_key_columns)

        # Test primary key patching.
        patched_primary_key_column = set(
            column.name
            for column in
            metadata.tables[table_without_primary_key.fullname].primary_key
        )
        self.assertEqual({'column_with_no_primary_key'}, patched_primary_key_column)

        # The linting error is sqlalchemy-pylint bug
        # https://github.com/sqlalchemy/sqlalchemy/issues/4656
        # pylint: disable=no-value-for-parameter
        table_without_primary_key.delete(bind=engine)
        table_with_many_primary_keys.delete(bind=engine)
        # pylint: enable=no-value-for-parameter

# pylint: enable=no-member
