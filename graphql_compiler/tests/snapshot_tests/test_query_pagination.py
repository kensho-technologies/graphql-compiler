# Copyright 2019-present Kensho Technologies, LLC.
import unittest
import datetime

import pytest

from ...ast_manipulation import safe_parse_graphql
from ...cost_estimation.cardinality_estimator import estimate_query_result_cardinality
from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import QueryStringWithParameters, paginate_query
from ...query_pagination.pagination_planning import (
    PaginationPlan, VertexPartition, try_get_pagination_plan
)
from ...query_pagination.parameter_generator import generate_parameters_for_vertex_partition
from ...schema.schema_info import QueryPlanningSchemaInfo
from ...schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from ..test_helpers import compare_graphql, generate_schema_graph


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class QueryPaginationTests(unittest.TestCase):
    """Test the query pagination module."""

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_pagination_planning_basic(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {'Animal': 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields)

        # Check that the correct plan is generated when it's obvious (page the root)
        query = '''{
            Animal {
                name @output(out_name: "animal_name")
            }
        }'''
        number_of_pages = 10
        query_ast = safe_parse_graphql(query)
        pagination_plan = try_get_pagination_plan(schema_info, query_ast, number_of_pages)
        expected_plan = PaginationPlan([
            VertexPartition(('Animal',), 'uuid', number_of_pages)
        ])
        self.assertEqual(expected_plan, pagination_plan)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_parameter_value_generation_int(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
        pagination_keys['Species'] = 'limbs'  # Force pagination on int field
        uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {'Species': 1000}
        statistics = LocalStatistics(class_counts, field_quantiles={
            ('Species', 'limbs'): [i for i in range(101)],
        })
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields)

        query = '''{
            Species {
                name @output(out_name: "species_name")
            }
        }'''
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartition(['Species'], 'limbs', 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition)

        expected_parameters = [26, 51, 76]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_parameter_value_generation_with_existing_filters(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
        pagination_keys['Species'] = 'limbs'  # Force pagination on int field
        uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {'Species': 1000}
        statistics = LocalStatistics(class_counts, field_quantiles={
            ('Species', 'limbs'): [i for i in range(101)],
        })
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields)

        query = '''{
            Species {
                limbs @filter(op_name: "<", value: ["$num_limbs"])
                name @output(out_name: "species_name")
            }
        }'''
        args = {
            'num_limbs': 50
        }
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartition(['Species'], 'limbs', 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition)

        expected_parameters = [14, 26, 38]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_parameter_value_generation_datetime(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
        pagination_keys['Event'] = 'event_date'  # Force pagination on datetime field
        uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {'Event': 1000}
        statistics = LocalStatistics(class_counts, field_quantiles={
            ('Event', 'event_date'): [
                datetime.datetime(2000 + i, 1, 1) for i in range(101)
            ],
        })
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields)

        query = '''{
            Event {
                name @output(out_name: "event_name")
            }
        }'''
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartition(['Event'], 'event_date', 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition)

        expected_parameters = [
            datetime.datetime(2026, 1, 1, 0, 0),
            datetime.datetime(2051, 1, 1, 0, 0),
            datetime.datetime(2076, 1, 1, 0, 0),
        ]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_parameter_value_generation_uuid(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {'Animal': 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields)

        query = '''{
            Animal {
                name @output(out_name: "animal_name")
            }
        }'''
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartition(['Animal'], 'uuid', 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition)

        expected_parameters = [
            '40000000-0000-0000-0000-000000000000',
            '80000000-0000-0000-0000-000000000000',
            'c0000000-0000-0000-0000-000000000000',
        ]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_no_pagination(self):
        """Ensure pagination is not done when not needed."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
        original_query = '''{
            Animal {
                name @output(out_name: "animal")
            }
        }'''
        parameters = {}

        count_data = {
            'Animal': 4,
        }

        statistics = LocalStatistics(count_data)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields)

        first, remainder = paginate_query(schema_info, original_query, parameters, 10)

        # No pagination necessary
        expected_query_list = (
            QueryStringWithParameters(original_query, parameters),
            None,
        )
        compare_graphql(self, original_query, first.query_string)
        self.assertEqual(parameters, first.parameters)
        self.assertIsNone(remainder)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_pagination_end_to_end_basic(self):
        """Ensure a basic pagination query is handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
        test_data = '''{
            Animal {
                name @output(out_name: "animal")
            }
        }'''
        parameters = {}

        count_data = {
            'Animal': 4,
        }

        statistics = LocalStatistics(count_data)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields)

        first, remainder = paginate_query(
            schema_info, test_data, parameters, 1
        )

        expected_page_query = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: "<", value: ["$__paged_param_0"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '__paged_param_0': '40000000-0000-0000-0000-000000000000',
            },
        )
        expected_remainder_query = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_0"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '__paged_param_0': '40000000-0000-0000-0000-000000000000',
            },
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_page_query.query_string, first.query_string)
        self.assertEqual(expected_page_query.parameters, first.parameters)
        compare_graphql(self, expected_remainder_query.query_string, remainder.query_string)
        self.assertEqual(expected_remainder_query.parameters, remainder.parameters)

        # Check that the first page is estimated to fit into a page
        first_page_cardinality_estimate = estimate_query_result_cardinality(
            schema_info, first.query_string, first.parameters)
        self.assertAlmostEqual(1, first_page_cardinality_estimate)

        # Get the second page
        second, remainder = paginate_query(
            schema_info, remainder.query_string, remainder.parameters, 1)

        expected_second_query = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_0"])
                         @filter(op_name: "<", value: ["$__paged_param_1"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '__paged_param_0': '40000000-0000-0000-0000-000000000000',
                '__paged_param_1': '80000000-0000-0000-0000-000000000000',
            },
        )
        expected_remainder_query = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_0"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '__paged_param_0': '80000000-0000-0000-0000-000000000000',
            },
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_second_query.query_string, second.query_string)
        self.assertEqual(expected_second_query.parameters, second.parameters)
        compare_graphql(self, expected_remainder_query.query_string, remainder.query_string)
        self.assertEqual(expected_remainder_query.parameters, remainder.parameters)

        # Check that the second page is estimated to fit into a page
        second_page_cardinality_estimate = estimate_query_result_cardinality(
            schema_info, second.query_string, second.parameters)
        self.assertAlmostEqual(1, second_page_cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_pagination_datetime(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
        pagination_keys['Event'] = 'event_date'  # Force pagination on datetime field
        uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {'Event': 1000}
        statistics = LocalStatistics(class_counts, field_quantiles={
            ('Event', 'event_date'): [
                datetime.datetime(2000 + i, 1, 1) for i in range(101)
            ],
        })
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields)

        query = '''{
            Event {
                name @output(out_name: "event_name")
            }
        }'''
        args = {}

        first, remainder = paginate_query(schema_info, query, args, 600)

        expected_page_query = QueryStringWithParameters(
            '''{
                Event {
                    event_date @filter(op_name: "<", value: ["$__paged_param_0"])
                    name @output(out_name: "event_name")
                }
            }''',
            {
                '__paged_param_0': datetime.datetime(2051, 1, 1, 0, 0),
            },
        )
        expected_remainder_query = QueryStringWithParameters(
            '''{
                Event {
                    event_date @filter(op_name: ">=", value: ["$__paged_param_0"])
                    name @output(out_name: "event_name")
                }
            }''',
            {
                '__paged_param_0': datetime.datetime(2051, 1, 1, 0, 0),
            },
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_page_query.query_string, first.query_string)
        self.assertEqual(expected_page_query.parameters, first.parameters)
        compare_graphql(self, expected_remainder_query.query_string, remainder.query_string)
        self.assertEqual(expected_remainder_query.parameters, remainder.parameters)
