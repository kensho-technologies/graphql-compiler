# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ...cost_estimation.analysis import analyze_query_string
from ...cost_estimation.filter_selectivity_utils import Selectivity
from ...cost_estimation.interval import Interval
from ...cost_estimation.statistics import LocalStatistics
from ...global_utils import QueryStringWithParameters
from ...schema.schema_info import EdgeConstraint, QueryPlanningSchemaInfo, UUIDOrdering
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
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        query = QueryStringWithParameters(
            """{
                Animal {
                    name @output(out_name: "animal_name")
                    uuid @filter(op_name: ">", value: ["$uuid_min"])
                }
            }""",
            {
                "uuid_min": "80000000-0000-0000-0000-000000000000",
            },
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
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
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
            {
                "uuid": "80000000-0000-0000-0000-000000000000",
            },
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
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
                uuid @filter(op_name: ">", value: ["$uuid_min"])
            }
        }""",
            {
                "uuid_min": "80000000-0000-0000-0000-000000000000",
            },
        )

        capacities = analyze_query_string(schema_info, query).pagination_capacities
        expected_capacities = {(("Animal",), "uuid"): 500}
        self.assertEqual(expected_capacities, capacities)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_get_pagination_capacities_unique_filter(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
                uuid @filter(op_name: "=", value: ["$uuid"])
            }
        }""",
            {
                "uuid": "80000000-0000-0000-0000-000000000000",
            },
        )

        capacities = analyze_query_string(schema_info, query).pagination_capacities
        expected_capacities = {(("Animal",), "uuid"): 1}
        self.assertEqual(expected_capacities, capacities)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_get_selectivities(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
                uuid @filter(op_name: "=", value: ["$animal_uuid"])
                out_Animal_ParentOf {
                    uuid @filter(op_name: "<", value: ["$child_uuid_upper_bound"])
                }
            }
        }""",
            {
                "animal_uuid": "80000000-0000-0000-0000-000000000000",
                "child_uuid_upper_bound": "80000000-0000-0000-0000-000000000000",
            },
        )

        self.assertEqual(
            {
                ("Animal",): Selectivity(kind="absolute", value=1.0),
                ("Animal", "out_Animal_ParentOf"): Selectivity(kind="fractional", value=0.5),
            },
            analyze_query_string(schema_info, query).selectivities,
        )

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_get_pagination_capacities_int_field(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
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
            uuid4_field_info=uuid4_field_info,
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
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
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
            uuid4_field_info=uuid4_field_info,
        )

        query = QueryStringWithParameters(
            """{
            Species {
                name @output(out_name: "species_name")
                limbs @filter(op_name: ">=", value: ["$limbs_min"])
            }
        }""",
            {
                "limbs_min": 10,
            },
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
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
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
            {},
        )
        analysis = analyze_query_string(schema_info, query)

        self.assertEqual(
            {
                ("Animal",): graphql_schema.get_type("Animal"),
                ("Animal", "out_Animal_ParentOf"): graphql_schema.get_type("Animal"),
            },
            analysis.types,
        )

        self.assertEqual(
            {("Animal", "out_Animal_ParentOf"): ("Animal",)}, analysis.fold_scope_roots
        )

        self.assertEqual(
            {
                (("Animal",), "uuid"): 1000,
            },
            analysis.pagination_capacities,
        )

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_eligible_fields(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        query = QueryStringWithParameters(
            """{
            Animal {
                uuid @tag(tag_name: "uuid_tag")
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    name @output(out_name: "child_names")
                }
                in_Animal_ParentOf {
                    uuid @filter(op_name: ">=", value: ["%uuid_tag"])
                }
            }
        }""",
            {},
        )
        analysis = analyze_query_string(schema_info, query)
        eligible_fields = analysis.fields_eligible_for_pagination
        expected_eligible_fields = {
            (("Animal",), "uuid"),
            (("Animal",), "birthday"),
            (("Animal", "in_Animal_ParentOf"), "birthday"),
        }
        self.assertEqual(expected_eligible_fields, eligible_fields)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_distinct_result_set_estimates_edge_constraint_propagation(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Animal": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
            edge_constraints={
                "Animal_ParentOf": EdgeConstraint.AtMostOneSource,
            },
        )

        # The Animal_ParentOf edge has an AtMostOneSource constraint, meaning that each
        # destination is connected to at most one source.
        # The query below has a unique filter on the root, so the distinct result set
        # estimate at the root is 1. However, since that animal has at most one parent,
        # the distinct result set estimate at that location is 1 as well, even though
        # there are no explicit filters on it.
        query = QueryStringWithParameters(
            """{
            Animal {
                name @filter(op_name: "=", value: ["$animal_name"])
                in_Animal_ParentOf @optional {
                    name @output(out_name: "parent_name")
                    in_Animal_ParentOf {
                        name @output(out_name: "grandparent_name")
                    }
                }
            }
        }""",
            {
                "animal_name": "Joe",
            },
        )
        estimates = analyze_query_string(schema_info, query).distinct_result_set_estimates
        expected_estimates = {
            ("Animal",): 1.0,
            ("Animal", "in_Animal_ParentOf"): 1.0,
            ("Animal", "in_Animal_ParentOf", "in_Animal_ParentOf"): 1.0,
        }
        self.assertEqual(expected_estimates, estimates)

        # Even though the distinct result set estimate at the root is 1, that doesn't affect
        # the result on the child node, since an animal can have an unlimited number of
        # children.
        query = QueryStringWithParameters(
            """{
            Animal {
                name @filter(op_name: "=", value: ["$animal_name"])
                out_Animal_ParentOf @optional {
                    name @output(out_name: "child_name")
                    out_Animal_ParentOf {
                        name @output(out_name: "grandchild_name")
                    }
                }
            }
        }""",
            {
                "animal_name": "Joe",
            },
        )
        estimates = analyze_query_string(schema_info, query).distinct_result_set_estimates
        expected_estimates = {
            ("Animal",): 1.0,
            ("Animal", "out_Animal_ParentOf"): 1000.0,
            ("Animal", "out_Animal_ParentOf", "out_Animal_ParentOf"): 1000.0,
        }
        self.assertEqual(expected_estimates, estimates)
