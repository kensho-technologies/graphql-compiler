# Copyright 2018-present Kensho Technologies, LLC.
import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest import TestCase

from graphql.type import (
    GraphQLID,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
)
from graphql.utilities import print_schema
from parameterized import parameterized
import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table

from ...compiler.compiler_frontend import OutputMetadata
from ...post_processing.sql_post_processing import post_process_mssql_folds
from ...schema.schema_info import CommonSchemaInfo
from ...schema_generation.orientdb.schema_properties import ORIENTDB_BASE_VERTEX_CLASS_NAME
from ...schema_generation.sqlalchemy.sqlalchemy_reflector import (
    fast_sql_server_reflect,
    get_first_column_in_table,
)
from ...tests import test_backend
from ..test_helpers import (
    SCHEMA_TEXT,
    compare_schema_texts_order_independently,
    generate_schema,
    generate_schema_graph,
    get_schema,
)
from .integration_backend_config import (
    MATCH_BACKENDS,
    NEO4J_BACKENDS,
    REDISGRAPH_BACKENDS,
    SQL_BACKENDS,
)
from .integration_test_helpers import (
    compile_and_run_match_query,
    compile_and_run_neo4j_query,
    compile_and_run_redisgraph_query,
    compile_and_run_sql_query,
    sort_db_results,
)


all_backends_list = [
    test_backend.ORIENTDB,
    test_backend.MSSQL,
    test_backend.NEO4J,
    test_backend.REDISGRAPH,
    test_backend.POSTGRES,
]


# Store the typical fixtures required for an integration tests.
# Individual tests can supply the full @pytest.mark.usefixtures to override if necessary.
integration_fixtures = pytest.mark.usefixtures(
    "integration_neo4j_client",
    "integration_orientdb_client",
    "integration_redisgraph_client",
    "sql_integration_data",
)


def use_all_backends(except_backends: Tuple[str, ...] = ()) -> Callable:
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
        backend for backend in all_backends_list if backend not in except_backends
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
    def setUpClass(cls) -> None:
        """Initialize the test schema once for all tests, and disable max diff limits."""
        cls.maxDiff = None
        cls.schema = get_schema()  # type: ignore  # we are adding an attribute to the object

    def assertResultsEqual(
        self,
        graphql_query: str,
        parameters: Dict[str, Any],
        backend_name: str,
        expected_results: List[Dict[str, Any]],
    ) -> None:
        """Assert that two lists of DB results are equal, independent of order."""
        backend_results, output_metadata = self.compile_and_run_query(
            graphql_query, parameters, backend_name
        )
        if backend_name == test_backend.MSSQL:
            if output_metadata is None:
                raise AssertionError(
                    f"No output metadata found to postprocess {test_backend.MSSQL} results."
                )
            post_process_mssql_folds(backend_results, output_metadata)
        try:
            self.assertListEqual(
                sort_db_results(expected_results), sort_db_results(backend_results)
            )
        except AssertionError as error:
            # intercept and modify error message to indicate which backend(s) failed
            args = [f'Failure for backend "{backend_name}": {error.args[0]}']
            args.extend(error.args[1:])
            error.args = tuple(args)
            raise

    @classmethod
    def compile_and_run_query(
        cls,
        graphql_query: str,
        parameters: Dict[str, Any],
        backend_name: str,
    ) -> Any:
        """Compiles and runs the graphql query with the supplied parameters against all backends.

        Args:
            graphql_query: str, GraphQL query string to run against every backend.
            parameters: Dict[str, Any], input parameters to the query.
            backend_name: str, the name of the test backend to get results from.

        Returns:
            List[Dict[str, Any]], backend results as a list of dictionaries.
        """
        # Mypy doesn't like our decorator magic, we have to manually ignore the type checks
        # on all the properties that we magically added via the integration testing decorator.
        common_schema_info = CommonSchemaInfo(cls.schema, None)  # type: ignore
        output_metadata: Optional[Dict[str, OutputMetadata]] = None
        if backend_name in SQL_BACKENDS:
            engine = cls.sql_backend_name_to_engine[backend_name]  # type: ignore
            results, output_metadata = compile_and_run_sql_query(
                cls.sql_schema_info[backend_name], graphql_query, parameters, engine  # type: ignore
            )
        elif backend_name in MATCH_BACKENDS:
            results = compile_and_run_match_query(
                common_schema_info, graphql_query, parameters, cls.orientdb_client  # type: ignore
            )
        elif backend_name in NEO4J_BACKENDS:
            results = compile_and_run_neo4j_query(
                common_schema_info, graphql_query, parameters, cls.neo4j_client  # type: ignore
            )
        elif backend_name in REDISGRAPH_BACKENDS:
            results = compile_and_run_redisgraph_query(
                common_schema_info, graphql_query, parameters, cls.redisgraph_client  # type: ignore
            )
        else:
            raise AssertionError(f"Unknown test backend {backend_name}.")
        return results, output_metadata

    @use_all_backends()
    @integration_fixtures
    def test_simple_output(self, backend_name: str) -> None:
        graphql_query = """
        {
            Animal {
                name @output(out_name: "animal_name")
                uuid @output(out_name: "animal_uuid")
            }
        }
        """
        expected_results = [
            {"animal_name": "Animal 1", "animal_uuid": "cfc6e625-8594-0927-468f-f53d864a7a51"},
            {"animal_name": "Animal 2", "animal_uuid": "cfc6e625-8594-0927-468f-f53d864a7a52"},
            {"animal_name": "Animal 3", "animal_uuid": "cfc6e625-8594-0927-468f-f53d864a7a53"},
            {"animal_name": "Animal 4", "animal_uuid": "cfc6e625-8594-0927-468f-f53d864a7a54"},
        ]
        self.assertResultsEqual(graphql_query, {}, backend_name, expected_results)

    # Cypher doesn't support Decimals (both Neo4j [1] and RedisGraph [2])
    # [0] https://oss.redislabs.com/redisgraph/cypher_support/#types
    # [1] https://neo4j.com/docs/cypher-manual/current/syntax/values/
    # [2] https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf
    @use_all_backends(except_backends=(test_backend.NEO4J, test_backend.REDISGRAPH))
    @integration_fixtures
    def test_simple_filter(self, backend_name: str) -> None:
        graphql_query = """
        {
            Animal {
                name @output(out_name: "animal_name")
                net_worth @output(out_name: "animal_net_worth")
                          @filter(op_name: "=", value: ["$net_worth"])
            }
        }
        """
        parameters = {
            "net_worth": Decimal("100"),
        }
        expected_results = [
            {"animal_name": "Animal 1", "animal_net_worth": Decimal("100")},
        ]

        self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    @integration_fixtures
    def test_edge_from_superclass_with_preferred_location_not_at_root(self) -> None:
        graphql_query = """{
            Animal {
                name @output(out_name: "animal_name")
                out_Entity_Related {
                    name @output(out_name: "related_animal_name")
                    alias @filter(op_name: "contains", value: ["$name"])
                }
            }
        }"""
        parameters = {
            "name": "Species 2",
        }
        expected_results: List[Dict[str, Any]] = []

        self.assertResultsEqual(graphql_query, parameters, test_backend.ORIENTDB, expected_results)

    # Redisgraph doesn't support lists so in_collection doesn't make sense. [0]
    # Cypher doesn't support Decimals (both Neo4j [1] and RedisGraph [2])
    # [0] https://oss.redislabs.com/redisgraph/cypher_support/#types
    # [1] https://neo4j.com/docs/cypher-manual/current/syntax/values/
    # [2] https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf
    @use_all_backends(except_backends=(test_backend.REDISGRAPH, test_backend.NEO4J))
    @integration_fixtures
    def test_two_filters(self, backend_name: str) -> None:
        graphql_query = """
            {
                Animal {
                    name @output(out_name: "animal_name")
                    net_worth @output(out_name: "animal_net_worth")
                              @filter(op_name: ">=", value: ["$lower_bound_exclusive"])
                              @filter(op_name: "in_collection", value: ["$net_worths"])
                }
            }
            """
        parameters = {
            "lower_bound_exclusive": Decimal("200"),
            "net_worths": [Decimal("300"), Decimal("400")],
        }
        expected_results = [
            {"animal_name": "Animal 3", "animal_net_worth": Decimal("300")},
            {"animal_name": "Animal 4", "animal_net_worth": Decimal("400")},
        ]

        self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    # RedisGraph doesn't support string function CONTAINS
    # https://oss.redislabs.com/redisgraph/cypher_support/#string-operators
    @use_all_backends(except_backends=(test_backend.REDISGRAPH,))
    @integration_fixtures
    def test_has_substring_precedence(self, backend_name: str) -> None:
        graphql_query = """
        {
            Animal {
                name @output(out_name: "animal_name")
                     @filter(op_name: "has_substring", value: ["$wide_substring"])
                     @filter(op_name: "has_substring", value: ["$narrow_substring"])
            }
        }
        """
        parameters = {
            # matches all animal names
            "wide_substring": "Animal",
            # narrows set to just ['Animal 3']
            "narrow_substring": "3",
        }
        expected_results = [
            {"animal_name": "Animal 3"},
        ]
        self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    @integration_fixtures
    def test_recurse(self) -> None:
        parameters = {
            "starting_animal_name": "Animal 1",
        }

        # (query, expected_results) pairs. All of them running with the same parameters.
        # The queries are ran in the order specified here.
        queries: List[Tuple[str, List[Dict[str, Any]]]] = [
            # Query 1: Just the root
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                             @output(out_name: "root_name")
                    }
                }""",
                [{"root_name": "Animal 1"}],
            ),
            # Query 2: Immediate children
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                        out_Animal_ParentOf {
                            name @output(out_name: "descendant_name")
                        }
                    }
                }""",
                [
                    {"descendant_name": "Animal 1"},
                    {"descendant_name": "Animal 2"},
                    {"descendant_name": "Animal 3"},
                ],
            ),
            # Query 3: Grandchildren
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                        out_Animal_ParentOf {
                            out_Animal_ParentOf {
                                name @output(out_name: "descendant_name")
                            }
                        }
                    }
                }""",
                [
                    {"descendant_name": "Animal 1"},
                    {"descendant_name": "Animal 2"},
                    {"descendant_name": "Animal 3"},
                    {"descendant_name": "Animal 4"},
                ],
            ),
            # Query 4: Grand-grandchildren
            (
                """
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
                }""",
                [
                    {"descendant_name": "Animal 1"},
                    {"descendant_name": "Animal 2"},
                    {"descendant_name": "Animal 3"},
                    {"descendant_name": "Animal 4"},
                ],
            ),
            # Query 5: Recurse depth 1
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                        out_Animal_ParentOf @recurse(depth: 1){
                            name @output(out_name: "descendant_name")
                        }
                    }
                }""",
                [
                    {"descendant_name": "Animal 1"},  # depth 0 match
                    {"descendant_name": "Animal 1"},  # depth 1 match
                    {"descendant_name": "Animal 2"},  # depth 1 match
                    {"descendant_name": "Animal 3"},  # depth 1 match
                ],
            ),
            # Query 6: Recurse depth 2
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                        out_Animal_ParentOf @recurse(depth: 2){
                            name @output(out_name: "descendant_name")
                        }
                    }
                }""",
                [
                    {"descendant_name": "Animal 1"},  # depth 0 match
                    {"descendant_name": "Animal 1"},  # depth 1 match
                    {"descendant_name": "Animal 2"},  # depth 1 match
                    {"descendant_name": "Animal 3"},  # depth 1 match
                    {"descendant_name": "Animal 1"},  # depth 2 match
                    {"descendant_name": "Animal 2"},  # depth 2 match
                    {"descendant_name": "Animal 3"},  # depth 2 match
                    {"descendant_name": "Animal 4"},  # depth 2 match
                ],
            ),
            # Query 7: Recurse depth 3
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                        out_Animal_ParentOf @recurse(depth: 3){
                            name @output(out_name: "descendant_name")
                        }
                    }
                }""",
                [
                    {"descendant_name": "Animal 1"},  # depth 0 match
                    {"descendant_name": "Animal 1"},  # depth 1 match
                    {"descendant_name": "Animal 2"},  # depth 1 match
                    {"descendant_name": "Animal 3"},  # depth 1 match
                    {"descendant_name": "Animal 1"},  # depth 2 match
                    {"descendant_name": "Animal 2"},  # depth 2 match
                    {"descendant_name": "Animal 3"},  # depth 2 match
                    {"descendant_name": "Animal 4"},  # depth 2 match
                    {"descendant_name": "Animal 1"},  # depth 3 match
                    {"descendant_name": "Animal 2"},  # depth 3 match
                    {"descendant_name": "Animal 3"},  # depth 3 match
                    {"descendant_name": "Animal 4"},  # depth 3 match
                ],
            ),
            # Query 8: Skip depth 0
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                        out_Animal_ParentOf {
                            out_Animal_ParentOf @recurse(depth: 2) {
                                name @output(out_name: "descendant_name")
                            }
                        }
                    }
                }""",
                [
                    {"descendant_name": "Animal 1"},  # depth 0 match
                    {"descendant_name": "Animal 2"},  # depth 0 match
                    {"descendant_name": "Animal 3"},  # depth 0 match
                    {"descendant_name": "Animal 1"},  # depth 1 match
                    {"descendant_name": "Animal 2"},  # depth 1 match
                    {"descendant_name": "Animal 3"},  # depth 1 match
                    {"descendant_name": "Animal 4"},  # depth 1 match
                    {"descendant_name": "Animal 1"},  # depth 2 match
                    {"descendant_name": "Animal 2"},  # depth 2 match
                    {"descendant_name": "Animal 3"},  # depth 2 match
                    {"descendant_name": "Animal 4"},  # depth 2 match
                ],
            ),
            # Query 9: Output child name
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                        out_Animal_ParentOf {
                            name @output(out_name: "child_name")
                            out_Animal_ParentOf @recurse(depth: 2) {
                                name @output(out_name: "descendant_name")
                            }
                        }
                    }
                }""",
                [
                    {"child_name": "Animal 1", "descendant_name": "Animal 1"},  # depth 0 match
                    {"child_name": "Animal 2", "descendant_name": "Animal 2"},  # depth 0 match
                    {"child_name": "Animal 3", "descendant_name": "Animal 3"},  # depth 0 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 1"},  # depth 1 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 2"},  # depth 1 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 3"},  # depth 1 match
                    {"child_name": "Animal 3", "descendant_name": "Animal 4"},  # depth 1 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 1"},  # depth 2 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 2"},  # depth 2 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 3"},  # depth 2 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 4"},  # depth 2 match
                ],
            ),
            # Query 10: Recurse within optional scope. Animal_1 has no grandchildren from its
            #           child Animal_2, but since we use an @optional edge, Animal_2 should
            #           still appear in the result as a child of Animal_1. Here we are testing
            #           that the use of @recurse does not interfere with @optional semantics.
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                        out_Animal_ParentOf {
                            name @output(out_name: "child_name")
                            out_Animal_ParentOf @optional {
                                out_Animal_ParentOf @recurse(depth: 1){
                                    name @output(out_name: "descendant_name")
                                }
                            }
                        }
                    }
                }""",
                [
                    {"child_name": "Animal 1", "descendant_name": "Animal 1"},  # depth 0 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 2"},  # depth 0 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 3"},  # depth 0 match
                    {"child_name": "Animal 2", "descendant_name": None},  # depth 0 match
                    {"child_name": "Animal 3", "descendant_name": "Animal 4"},  # depth 0 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 1"},  # depth 1 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 2"},  # depth 1 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 3"},  # depth 1 match
                    {"child_name": "Animal 1", "descendant_name": "Animal 4"},  # depth 1 match
                ],
            ),
            # Query 11: Same as query 10, but with additional traversal inside the @recurse.
            (
                """
                {
                    Animal {
                        name @filter(op_name: "=", value: ["$starting_animal_name"])
                        out_Animal_ParentOf {
                            name @output(out_name: "child")
                            out_Animal_ParentOf @optional {
                                out_Animal_ParentOf @recurse(depth: 1){
                                    name @output(out_name: "descendant")
                                    out_Animal_ParentOf {
                                         name @output(out_name: "tiny_child")
                                    }
                                }
                            }
                        }
                    }
                }""",
                [
                    {"child": "Animal 1", "descendant": "Animal 1", "tiny_child": "Animal 1"},
                    {"child": "Animal 1", "descendant": "Animal 1", "tiny_child": "Animal 2"},
                    {"child": "Animal 1", "descendant": "Animal 1", "tiny_child": "Animal 3"},
                    {"child": "Animal 1", "descendant": "Animal 3", "tiny_child": "Animal 4"},
                    {"child": "Animal 2", "descendant": None, "tiny_child": None},
                    {"child": "Animal 1", "descendant": "Animal 1", "tiny_child": "Animal 1"},
                    {"child": "Animal 1", "descendant": "Animal 1", "tiny_child": "Animal 2"},
                    {"child": "Animal 1", "descendant": "Animal 1", "tiny_child": "Animal 3"},
                    {"child": "Animal 1", "descendant": "Animal 3", "tiny_child": "Animal 4"},
                ],
            ),
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

    @integration_fixtures
    def test_recurse_duplication_regression(self) -> None:
        # Regression test for the following bug:
        # https://github.com/kensho-technologies/graphql-compiler/pull/887

        parameters: Dict[str, Any] = {}
        # (query, expected_results) pairs. All of them running with the same parameters.
        #
        # The queries are ran in the order specified here. The last query checks that a
        # many-to-one traversal before recursion does not cause duplicate results to appear.
        # The preceding queries help justify the expected result of the last query in
        # a more readable way, and guard against changes in the test data:
        # - If the test data changes and breaks the last test, the preceding tests
        #   will point out that this is not a bug in recursion, but a change in data.
        # - If the test data changes, the last test passes, but it no longer serves as
        #   a good regression test for this bug, the preceding tests will fail.
        queries: List[Tuple[str, List[Dict[str, Any]]]] = [
            # Query 1: Get all parents
            (
                """
                {
                    Animal {
                        name @output(out_name: "animal")
                        in_Animal_ParentOf {
                            name @output(out_name: "father")
                        }
                    }
                }""",
                [
                    {"animal": "Animal 1", "father": "Animal 1"},
                    {"animal": "Animal 2", "father": "Animal 1"},
                    {"animal": "Animal 3", "father": "Animal 1"},
                    {"animal": "Animal 4", "father": "Animal 3"},
                ],
            ),
            # Query 2: Get all grandparents
            (
                """
                {
                    Animal {
                        name @output(out_name: "animal")
                        in_Animal_ParentOf {
                            in_Animal_ParentOf {
                                name @output(out_name: "grandfather")
                            }
                        }
                    }
                }""",
                [
                    {"animal": "Animal 1", "grandfather": "Animal 1"},
                    {"animal": "Animal 2", "grandfather": "Animal 1"},
                    {"animal": "Animal 3", "grandfather": "Animal 1"},
                    {"animal": "Animal 4", "grandfather": "Animal 1"},
                ],
            ),
            # Query 3: Use recursion to get self, parent and grandparent
            (
                """
                {
                    Animal {
                        name @output(out_name: "animal")
                        in_Animal_ParentOf @recurse(depth: 2) {
                            name @output(out_name: "ancestor")
                        }
                    }
                }""",
                [
                    {"animal": "Animal 1", "ancestor": "Animal 1"},  # self
                    {"animal": "Animal 1", "ancestor": "Animal 1"},  # parent
                    {"animal": "Animal 1", "ancestor": "Animal 1"},  # grandparent
                    {"animal": "Animal 2", "ancestor": "Animal 2"},  # self
                    {"animal": "Animal 2", "ancestor": "Animal 1"},  # parent
                    {"animal": "Animal 2", "ancestor": "Animal 1"},  # grandparent
                    {"animal": "Animal 3", "ancestor": "Animal 3"},  # self
                    {"animal": "Animal 3", "ancestor": "Animal 1"},  # parent
                    {"animal": "Animal 3", "ancestor": "Animal 1"},  # grandparent
                    {"animal": "Animal 4", "ancestor": "Animal 4"},  # self
                    {"animal": "Animal 4", "ancestor": "Animal 3"},  # parent
                    {"animal": "Animal 4", "ancestor": "Animal 1"},  # grandparent
                ],
            ),
            # Query 4: Unfold recursion to omit self
            (
                """
                {
                    Animal {
                        name @output(out_name: "animal")
                        in_Animal_ParentOf {
                            in_Animal_ParentOf @recurse(depth: 1) {
                                name @output(out_name: "ancestor")
                            }
                        }
                    }
                }""",
                [
                    {"animal": "Animal 1", "ancestor": "Animal 1"},  # parent
                    {"animal": "Animal 1", "ancestor": "Animal 1"},  # grandparent
                    {"animal": "Animal 2", "ancestor": "Animal 1"},  # parent
                    {"animal": "Animal 2", "ancestor": "Animal 1"},  # grandparent
                    {"animal": "Animal 3", "ancestor": "Animal 1"},  # parent
                    {"animal": "Animal 3", "ancestor": "Animal 1"},  # grandparent
                    {"animal": "Animal 4", "ancestor": "Animal 1"},  # parent
                    {"animal": "Animal 4", "ancestor": "Animal 3"},  # grandparent
                ],
            ),
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

    @use_all_backends(except_backends=(test_backend.REDISGRAPH,))  # Not implemented yet
    @integration_fixtures
    def test_fold_basic(self, backend_name: str) -> None:
        # (query, args, expected_results, excluded_backends) tuples.
        # Note: excluded_backends is distinct from `@use_all_backends(expect_backends=(...)) because
        # some backends such as MSSQL have most, but not all, fold functionality implemented.
        # excluded_backends can be use to bypass a subset of the fold tests.
        # The queries are run in the order specified here.
        queries: List[Tuple[str, Dict[str, Any], List[Dict[str, Any]], List[str]]] = [
            # Query 1: Unfolded children of Animal 1
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        name @output(out_name: "descendant_name")
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 1",
                },
                [
                    {"descendant_name": "Animal 1"},
                    {"descendant_name": "Animal 2"},
                    {"descendant_name": "Animal 3"},
                ],
                [],
            ),
            # Query 2: Folded children of Animal 1
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @fold {
                        name @output(out_name: "child_names")
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 1",
                },
                [
                    {"child_names": ["Animal 1", "Animal 2", "Animal 3"]},
                ],
                [],
            ),
            # Query 3: Folded children's net worths of Animal 1
            # (to ensure folded non string values are outputted properly)
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @fold {
                        net_worth @output(out_name: "child_net_worths")
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 1",
                },
                [
                    {"child_net_worths": [Decimal("100"), Decimal("200"), Decimal("300")]},
                ],
                [],
            ),
            # Query 4: Unfolded children of Animal 4
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        name @output(out_name: "descendant_name")
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 4",
                },
                [],
                [],
            ),
            # Query 5: Folded children of Animal 4
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @fold {
                        name @output(out_name: "child_names")
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 4",
                },
                [
                    {"child_names": []},
                ],
                [],
            ),
            # Query 5: Multiple outputs in a fold scope.
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @fold {
                        name @output(out_name: "child_names")
                        uuid @output(out_name: "child_uuids")
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 1",
                },
                [
                    {
                        "child_names": ["Animal 1", "Animal 2", "Animal 3"],
                        "child_uuids": [
                            "cfc6e625-8594-0927-468f-f53d864a7a51",
                            "cfc6e625-8594-0927-468f-f53d864a7a52",
                            "cfc6e625-8594-0927-468f-f53d864a7a53",
                        ],
                    },
                ],
                [test_backend.MSSQL],
            ),
            # Query 6: Traversal in a fold scope.
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @fold {
                        out_Animal_ParentOf {
                            name @output(out_name: "grandchild_names")
                        }
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 1",
                },
                [
                    {
                        "grandchild_names": ["Animal 1", "Animal 2", "Animal 3", "Animal 4"],
                    },
                ],
                [],
            ),
            # Query 7: _x_count.
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf @fold {
                        name @output(out_name: "child_names")
                        _x_count @output(out_name: "child_count")
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 1",
                },
                [
                    {
                        "child_names": ["Animal 1", "Animal 2", "Animal 3"],
                        "child_count": 3,
                    },
                ],
                [test_backend.MSSQL, test_backend.NEO4J],
            ),
        ]

        for graphql_query, parameters, expected_results, excluded_backends in queries:
            if backend_name in excluded_backends:
                continue
            self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    @use_all_backends(
        except_backends=(test_backend.REDISGRAPH,)  # TODO(bojanserafimov): Resolve syntax error
    )
    @integration_fixtures
    def test_optional_basic(self, backend_name: str) -> None:
        # (query, args, expected_results) tuples.
        # The queries are ran in the order specified here.
        queries: List[Tuple[str, Dict[str, Any], List[Dict[str, Any]]]] = [
            # Query 1: Children of Animal 1
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        name @output(out_name: "child_name")
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 1",
                },
                [
                    {"child_name": "Animal 1"},
                    {"child_name": "Animal 2"},
                    {"child_name": "Animal 3"},
                ],
            ),
            # Query 2: Grandchildren of Animal 1
            (
                """
            {
                Animal {
                    name @filter(op_name: "=", value: ["$starting_animal_name"])
                    out_Animal_ParentOf {
                        out_Animal_ParentOf {
                            name @output(out_name: "grandchild_name")
                        }
                    }
                }
            }""",
                {
                    "starting_animal_name": "Animal 1",
                },
                [
                    {"grandchild_name": "Animal 1"},
                    {"grandchild_name": "Animal 2"},
                    {"grandchild_name": "Animal 3"},
                    {"grandchild_name": "Animal 4"},
                ],
            ),
            # Query 3: Unfolded children of Animal 1 and their children
            (
                """
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
            }""",
                {
                    "starting_animal_name": "Animal 1",
                },
                [
                    {"child_name": "Animal 1", "grandchild_name": "Animal 1"},
                    {"child_name": "Animal 1", "grandchild_name": "Animal 2"},
                    {"child_name": "Animal 1", "grandchild_name": "Animal 3"},
                    {"child_name": "Animal 2", "grandchild_name": None},
                    {"child_name": "Animal 3", "grandchild_name": "Animal 4"},
                ],
            ),
        ]

        for graphql_query, parameters, expected_results in queries:
            self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    # RedisGraph doesn't support temporal types, so Date types aren't supported.
    @use_all_backends(except_backends=(test_backend.REDISGRAPH,))
    @integration_fixtures
    def test_filter_on_date(self, backend_name: str) -> None:
        graphql_query = """
        {
            Animal {
                name @output(out_name: "animal_name")
                birthday @filter(op_name: "=", value: ["$birthday"])
            }
        }
        """
        parameters = {
            "birthday": datetime.date(1975, 3, 3),
        }
        expected_results = [
            {"animal_name": "Animal 3"},
        ]
        self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    # RedisGraph doesn't support temporal types, so DateTime types aren't supported.
    @use_all_backends(except_backends=(test_backend.REDISGRAPH,))
    @integration_fixtures
    def test_filter_on_datetime(self, backend_name: str) -> None:
        graphql_query = """
        {
            BirthEvent {
                uuid @output(out_name: "uuid")
                event_date @filter(op_name: "=", value: ["$event_date"])
            }
        }
        """
        parameters = {
            "event_date": datetime.datetime(2000, 1, 1, 1, 1, 1),
        }
        expected_results = [
            {"uuid": "cfc6e625-8594-0927-468f-f53d864a7a55"},
        ]
        self.assertResultsEqual(graphql_query, parameters, backend_name, expected_results)

    @integration_fixtures
    def test_snapshot_graphql_schema_from_orientdb_schema(self):
        class_to_field_type_overrides: Dict[str, Dict[str, GraphQLScalarType]] = {
            "UniquelyIdentifiable": {"uuid": GraphQLID}
        }
        schema, _ = generate_schema(
            self.orientdb_client,
            class_to_field_type_overrides=class_to_field_type_overrides,
            hidden_classes={ORIENTDB_BASE_VERTEX_CLASS_NAME},
        )
        compare_schema_texts_order_independently(self, SCHEMA_TEXT, print_schema(schema))

    @integration_fixtures
    def test_override_field_types(self) -> None:
        class_to_field_type_overrides: Dict[
            str, Dict[str, Union[GraphQLList[Any], GraphQLNonNull[Any], GraphQLScalarType]]
        ] = {"UniquelyIdentifiable": {"uuid": GraphQLID}}
        schema, _ = generate_schema(
            self.orientdb_client,  # type: ignore  # from fixture
            class_to_field_type_overrides=class_to_field_type_overrides,
        )
        # Since Animal implements the UniquelyIdentifiable interface and since we we overrode
        # UniquelyIdentifiable's uuid field to be of type GraphQLID when we generated the schema,
        # then Animal's uuid field should also be of type GraphQLID.
        animal_type = schema.get_type("Animal")
        if animal_type and isinstance(animal_type, GraphQLObjectType):
            self.assertEqual(animal_type.fields["uuid"].type, GraphQLID)
        else:
            raise AssertionError(
                f'Expected "Animal" to be of type GraphQLObjectType, but was '
                f"of type {type(animal_type)}"
            )

    @integration_fixtures
    def test_include_admissible_non_graph_class(self) -> None:
        schema, _ = generate_schema(self.orientdb_client)  # type: ignore  # from fixture
        # Included abstract non-vertex classes whose non-abstract subclasses are all vertexes.
        self.assertIsNotNone(schema.get_type("UniquelyIdentifiable"))

    @integration_fixtures
    def test_selectively_hide_classes(self) -> None:
        schema, _ = generate_schema(
            self.orientdb_client,  # type: ignore  # from fixture
            hidden_classes={"Animal"},
        )
        self.assertNotIn("Animal", schema.type_map)

    @integration_fixtures
    def test_parsed_schema_element_custom_fields(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        parent_of_edge = schema_graph.get_element_by_class_name("Animal_ParentOf")
        expected_custom_class_fields = {"human_name_in": "Parent", "human_name_out": "Child"}
        self.assertEqual(expected_custom_class_fields, parent_of_edge.class_fields)

    @integration_fixtures
    def test_sqlalchemy_fast_reflect(self) -> None:
        engine = self.sql_backend_name_to_engine[test_backend.MSSQL]  # type: ignore  # from fixture

        table_without_primary_key = Table(
            "TableWithoutPrimaryKey",
            MetaData(),
            Column("column_with_no_primary_key", Integer()),
            schema="db_1.schema_1",
        )
        table_with_many_primary_keys = Table(
            "TableWithManyPrimaryKeyColumns",
            MetaData(),
            Column("primary_key_column1", Integer(), primary_key=True),
            Column("primary_key_column2", Integer(), primary_key=True),
            schema="db_1.schema_1",
        )

        table_without_primary_key.create(bind=engine)
        table_with_many_primary_keys.create(bind=engine)

        metadata = MetaData()
        fast_sql_server_reflect(
            engine, metadata, "db_1.schema_1", primary_key_selector=get_first_column_in_table
        )

        # Test expected tables are included.
        self.assertIn("db_1.schema_1.Animal", metadata.tables)
        self.assertIn("db_1.schema_1.Species", metadata.tables)
        self.assertNotIn("db_1.schema_2.FeedingEvent", metadata.tables)

        # Test column types are correctly reflected.
        self.assertIsInstance(metadata.tables["db_1.schema_1.Animal"].columns["color"].type, String)

        # Test explicit primary key reflection.
        explicit_primary_key_columns = set(
            column.name
            for column in metadata.tables[table_with_many_primary_keys.fullname].primary_key
        )
        self.assertEqual(
            {"primary_key_column1", "primary_key_column2"}, explicit_primary_key_columns
        )

        # Test primary key patching.
        patched_primary_key_column = set(
            column.name
            for column in metadata.tables[table_without_primary_key.fullname].primary_key
        )
        self.assertEqual({"column_with_no_primary_key"}, patched_primary_key_column)

        # The linting error is sqlalchemy-pylint bug
        # https://github.com/sqlalchemy/sqlalchemy/issues/4656
        # pylint: disable=no-value-for-parameter
        table_without_primary_key.delete(bind=engine)
        table_with_many_primary_keys.delete(bind=engine)
        # pylint: enable=no-value-for-parameter


# pylint: enable=no-member
