# Copyright 2019-present Kensho Technologies, LLC.
import datetime
from typing import Any, Dict, Tuple
import unittest

import pytest

from ...cost_estimation.interval import Interval
from ...compiler.compiler_frontend import graphql_to_ir
from ...ast_manipulation import safe_parse_graphql
from ...cost_estimation import analysis
from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import QueryStringWithParameters, paginate_query
from ...query_pagination.pagination_planning import (
    InsufficientQuantiles,
    PaginationAdvisory,
    PaginationPlan,
    VertexPartitionPlan,
    get_pagination_plan,
)
from ...schema.schema_info import QueryPlanningSchemaInfo
from ...schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from ..test_helpers import generate_schema_graph


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class CostEstimationAnalysisTests(unittest.TestCase):
    """Test the cost estimation module using standard input data when possible."""

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_get_field_value_intervals(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        graphql_query_string = """{
            Animal {
                name @output(out_name: "animal_name")
                uuid @filter(op_name: ">", value: ["$uuid_min"])
            }
        }"""
        parameters = {
            "uuid_min": "80000000-0000-0000-0000-000000000000",
        }
        number_of_pages = 10
        query_metadata = graphql_to_ir(
            schema_info.schema,
            graphql_query_string,
            type_equivalence_hints=schema_info.type_equivalence_hints
        ).query_metadata_table

        ints = analysis.get_field_value_intervals(schema_info, query_metadata, parameters)
        expected_ints = {
            (('Animal',), 'uuid'): Interval(
                lower_bound='80000000-0000-0000-0000-000000000001',
                upper_bound=None)
        }
        self.assertEqual(expected_ints, ints)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_get_distinct_result_set_estimates(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        graphql_query_string = """{
            Animal {
                name @output(out_name: "animal_name")
                uuid @filter(op_name: "=", value: ["$uuid"])
                out_Animal_ParentOf {
                    name @output(out_name: "child_name")
                }
            }
        }"""
        parameters = {
            "uuid": "80000000-0000-0000-0000-000000000000",
        }
        number_of_pages = 10
        query_metadata = graphql_to_ir(
            schema_info.schema,
            graphql_query_string,
            type_equivalence_hints=schema_info.type_equivalence_hints
        ).query_metadata_table

        estimates = analysis.get_distinct_result_set_estimates(schema_info, query_metadata, parameters)
        expected_estimates = {
            ('Animal',): 1,
            ('Animal', 'out_Animal_ParentOf'): 1000,
        }
        self.assertEqual(expected_estimates, estimates)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_get_pagination_capacities(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        graphql_query_string = """{
            Animal {
                name @output(out_name: "animal_name")
                uuid @filter(op_name: ">", value: ["$uuid_min"])
            }
        }"""
        parameters = {
            "uuid_min": "80000000-0000-0000-0000-000000000000",
        }
        number_of_pages = 10
        query_metadata = graphql_to_ir(
            schema_info.schema,
            graphql_query_string,
            type_equivalence_hints=schema_info.type_equivalence_hints
        ).query_metadata_table

        ints = analysis.get_field_value_intervals(schema_info, query_metadata, parameters)
        distinct_result_estimates = analysis.get_distinct_result_set_estimates(
            schema_info, query_metadata, parameters)
        caps = analysis.get_pagination_capacities(
            schema_info, ints, distinct_result_estimates, query_metadata, parameters)
        expected_caps = {(('Animal',), 'uuid'): 500}
        self.assertEqual(expected_caps, caps)
