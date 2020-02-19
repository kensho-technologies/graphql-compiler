# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ...cost_estimation.analysis import analyze_query_string
from ...cost_estimation.interval import Interval
from ...cost_estimation.statistics import LocalStatistics
from ...global_utils import QueryStringWithParameters
from ...schema.schema_info import QueryPlanningSchemaInfo
from ...schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from ..test_helpers import generate_schema_graph


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class CostEstimationAnalysisTests(unittest.TestCase):
    """Test the cost estimation analysis passes."""

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

        query = QueryStringWithParameters(
            """{
                Animal {
                    name @output(out_name: "animal_name")
                    uuid @filter(op_name: ">", value: ["$uuid_min"])
                }
            }""",
            {"uuid_min": "80000000-0000-0000-0000-000000000000",},
        )
        intervals = analyze_query_string(schema_info, query).field_value_intervals
        expected_intervals = {
            (("Animal",), "uuid"): Interval(
                lower_bound="80000000-0000-0000-0000-000000000001", upper_bound=None
            )
        }
        self.assertEqual(expected_intervals, intervals)

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

        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
                uuid @filter(op_name: "=", value: ["$uuid"])
                out_Animal_ParentOf {
                    name @output(out_name: "child_name")
                }
            }
        }""",
            {"uuid": "80000000-0000-0000-0000-000000000000",},
        )

        estimates = analyze_query_string(schema_info, query).distinct_result_set_estimates
        expected_estimates = {
            ("Animal",): 1,
            ("Animal", "out_Animal_ParentOf"): 1000,
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

        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
                uuid @filter(op_name: ">", value: ["$uuid_min"])
            }
        }""",
            {"uuid_min": "80000000-0000-0000-0000-000000000000",},
        )

        capacities = analyze_query_string(schema_info, query).pagination_capacities
        expected_capacities = {(("Animal",), "uuid"): 500}
        self.assertEqual(expected_capacities, capacities)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_get_pagination_capacities_unique_filter(self) -> None:
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

        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
                uuid @filter(op_name: "=", value: ["$uuid"])
            }
        }""",
            {"uuid": "80000000-0000-0000-0000-000000000000",},
        )

        capacities = analyze_query_string(schema_info, query).pagination_capacities
        expected_capacities = {(("Animal",), "uuid"): 1}
        self.assertEqual(expected_capacities, capacities)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_get_pagination_capacities_int_field(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts, field_quantiles={("Species", "limbs"): list(range(101))}
        )
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        query = QueryStringWithParameters(
            """{
            Species {
                name @output(out_name: "species_name")
            }
        }""",
            {},
        )

        capacities = analyze_query_string(schema_info, query).pagination_capacities
        expected_capacities = {
            (("Species",), "limbs"): 100,
            (("Species",), "uuid"): 1000,
        }
        self.assertEqual(expected_capacities, capacities)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_get_pagination_capacities_int_field_existing_filter(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts, field_quantiles={("Species", "limbs"): list(range(101))}
        )
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        query = QueryStringWithParameters(
            """{
            Species {
                name @output(out_name: "species_name")
                limbs @filter(op_name: ">=", value: ["$limbs_min"])
            }
        }""",
            {"limbs_min": 10,},
        )

        capacities = analyze_query_string(schema_info, query).pagination_capacities
        expected_capacities = {
            (("Species",), "limbs"): 91,
            (("Species",), "uuid"): 905,
        }
        self.assertEqual(expected_capacities, capacities)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_analysis_with_fold(self) -> None:
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

        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    name @output(out_name: "child_names")
                }
            }
        }""",
            {"animal_uuid": "40000000-0000-0000-0000-000000000000",},
        )
        analysis = analyze_query_string(schema_info, query)
        capacities = analysis.pagination_capacities
        expected_capacities = {
            (("Animal",), "uuid"): 1000,
        }
        self.assertEqual(expected_capacities, capacities)
