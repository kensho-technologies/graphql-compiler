# Copyright 2019-present Kensho Technologies, LLC.
import datetime
from typing import Tuple
import unittest

from graphql import print_ast
import pytest

from .. import test_input_data
from ...cost_estimation.analysis import analyze_query_string
from ...cost_estimation.statistics import LocalStatistics
from ...exceptions import GraphQLInvalidArgumentError
from ...global_utils import QueryStringWithParameters
from ...query_pagination import paginate_query
from ...query_pagination.pagination_planning import (
    InsufficientQuantiles,
    MissingClassCount,
    PaginationAdvisory,
    PaginationPlan,
    VertexPartitionPlan,
    get_pagination_plan,
)
from ...query_pagination.parameter_generator import (
    _choose_parameter_values,
    generate_parameters_for_vertex_partition,
)
from ...query_pagination.query_parameterizer import generate_parameterized_queries
from ...schema.schema_info import EdgeConstraint, QueryPlanningSchemaInfo, UUIDOrdering
from ...schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from ..test_helpers import compare_graphql, generate_schema_graph, get_function_names_from_module
from ..test_input_data import CommonTestData


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class QueryPaginationTests(unittest.TestCase):
    """Test the query pagination module."""

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_planning_basic(self) -> None:
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

        # Check that the correct plan is generated when it's obvious (page the root)
        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
            }
        }""",
            {},
        )
        number_of_pages = 10
        analysis = analyze_query_string(schema_info, query)
        pagination_plan, advisories = get_pagination_plan(analysis, number_of_pages)
        expected_plan = PaginationPlan((VertexPartitionPlan(("Animal",), "uuid", number_of_pages),))
        expected_advisories: Tuple[PaginationAdvisory, ...] = tuple()
        self.assertEqual([w.message for w in expected_advisories], [w.message for w in advisories])
        self.assertEqual(expected_plan, pagination_plan)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_planning_invalid_extra_args(self) -> None:
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

        # Check that the correct plan is generated when it's obvious (page the root)
        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
            }
        }""",
            {"country": "USA"},
        )
        with self.assertRaises(GraphQLInvalidArgumentError):
            number_of_pages = 10
            analysis = analyze_query_string(schema_info, query)
            get_pagination_plan(analysis, number_of_pages)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_planning_invalid_missing_args(self) -> None:
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

        # Check that the correct plan is generated when it's obvious (page the root)
        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
                     @filter(op_name: "=", value: ["$animal_name"])
            }
        }""",
            {},
        )
        with self.assertRaises(GraphQLInvalidArgumentError):
            number_of_pages = 10
            analysis = analyze_query_string(schema_info, query)
            get_pagination_plan(analysis, number_of_pages)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_planning_unique_filter(self) -> None:
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
                uuid @filter(op_name: "=", value: ["$animal_uuid"])
                name @output(out_name: "animal_name")
            }
        }""",
            {
                "animal_uuid": "40000000-0000-0000-0000-000000000000",
            },
        )
        number_of_pages = 10
        analysis = analyze_query_string(schema_info, query)
        pagination_plan, advisories = get_pagination_plan(analysis, number_of_pages)

        # This is a white box test. We check that we don't paginate on the root when it has a
        # unique filter on it. A better plan is to paginate on a different vertex, but that is
        # not implemented.
        expected_plan = PaginationPlan(tuple())
        expected_advisories: Tuple[PaginationAdvisory, ...] = tuple()
        self.assertEqual([w.message for w in expected_advisories], [w.message for w in advisories])
        self.assertEqual(expected_plan, pagination_plan)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_planning_unique_filter_on_many_to_one(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {
            "Animal": 1000,
            "Animal_FedAt": 10000000,
            "FeedingEvent": 100000,
        }
        statistics = LocalStatistics(class_counts)
        edge_constraints = {"Animal_ParentOf": EdgeConstraint.AtMostOneSource}
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
            edge_constraints=edge_constraints,
        )

        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf {
                    uuid @filter(op_name: "=", value: ["$animal_uuid"])
                }
                out_Animal_FedAt {
                    name @output(out_name: "feeding_event_name")
                }
            }
        }""",
            {
                "animal_uuid": "40000000-0000-0000-0000-000000000000",
            },
        )
        number_of_pages = 10
        analysis = analyze_query_string(schema_info, query)
        pagination_plan, advisories = get_pagination_plan(analysis, number_of_pages)

        # This is a white box test. There's a filter on the child, which narrows down
        # the number of possible roots down to 1. This makes the root a bad pagination
        # vertex. Ideally, we'd paginate on the FeedingEvent node, but that's not implemented.
        expected_plan = PaginationPlan(tuple())
        expected_advisories: Tuple[PaginationAdvisory, ...] = tuple()
        self.assertEqual([w.message for w in expected_advisories], [w.message for w in advisories])
        self.assertEqual(expected_plan, pagination_plan)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_planning_on_int(self) -> None:
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
            class_counts, field_quantiles={("Species", "limbs"): list(range(100))}
        )
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        # Check that the paginator generates a plan paginating on an int field
        query = QueryStringWithParameters(
            """{
            Species {
                name @output(out_name: "species_name")
            }
        }""",
            {},
        )
        number_of_pages = 10
        analysis = analyze_query_string(schema_info, query)
        pagination_plan, advisories = get_pagination_plan(analysis, number_of_pages)
        expected_plan = PaginationPlan(
            (VertexPartitionPlan(("Species",), "limbs", number_of_pages),)
        )
        expected_advisories: Tuple[PaginationAdvisory, ...] = ()
        self.assertEqual([w.message for w in expected_advisories], [w.message for w in advisories])
        self.assertEqual(expected_plan, pagination_plan)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_planning_on_int_error(self) -> None:
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
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        # Check that the paginator detects a lack of quantile data for Species.limbs
        query = QueryStringWithParameters(
            """{
            Species {
                name @output(out_name: "species_name")
            }
        }""",
            {},
        )
        number_of_pages = 10
        analysis = analyze_query_string(schema_info, query)
        pagination_plan, advisories = get_pagination_plan(analysis, number_of_pages)
        expected_plan = PaginationPlan(tuple())
        expected_advisories = (InsufficientQuantiles("Species", "limbs", 0, 51),)
        self.assertEqual([w.message for w in expected_advisories], [w.message for w in advisories])
        self.assertEqual(expected_plan, pagination_plan)

    # TODO: These tests can be sped up by having an existing test SchemaGraph object.
    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_basic_pagination(self) -> None:
        """Ensure a basic pagination query is handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal")
            }
        }""",
            {},
        )

        count_data = {
            "Animal": 4,
        }

        statistics = LocalStatistics(count_data)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        first_page_and_remainder, _ = paginate_query(schema_info, query, 1)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        expected_first = QueryStringWithParameters(
            """{
                Animal {
                    uuid @filter(op_name: "<", value: ["$__paged_param_0"])
                    name @output(out_name: "animal")
                }
            }""",
            {
                "__paged_param_0": "40000000-0000-0000-0000-000000000000",
            },
        )

        expected_remainder = QueryStringWithParameters(
            """{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_0"])
                    name @output(out_name: "animal")
                }
            }""",
            {
                "__paged_param_0": "40000000-0000-0000-0000-000000000000",
            },
        )

        # Check that the correct first page and remainder are generated
        compare_graphql(self, expected_first.query_string, first.query_string)
        self.assertEqual(expected_first.parameters, first.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder.parameters, remainder[0].parameters)

        # Check that the first page is estimated to fit into a page
        first_page_cardinality_estimate = analyze_query_string(
            schema_info, first
        ).cardinality_estimate
        self.assertAlmostEqual(1, first_page_cardinality_estimate)

        # Get the second page
        second_page_and_remainder, _ = paginate_query(schema_info, remainder[0], 1)
        second = second_page_and_remainder.one_page
        remainder = second_page_and_remainder.remainder

        expected_second = QueryStringWithParameters(
            """{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_0"])
                         @filter(op_name: "<", value: ["$__paged_param_1"])
                    name @output(out_name: "animal")
                }
            }""",
            {
                "__paged_param_0": "40000000-0000-0000-0000-000000000000",
                "__paged_param_1": "80000000-0000-0000-0000-000000000000",
            },
        )
        expected_remainder = QueryStringWithParameters(
            """{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_1"])
                    name @output(out_name: "animal")
                }
            }""",
            {
                "__paged_param_1": "80000000-0000-0000-0000-000000000000",
            },
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_second.query_string, second.query_string)
        self.assertEqual(expected_second.parameters, second.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder.parameters, remainder[0].parameters)

        # Check that the second page is estimated to fit into a page
        second_page_cardinality_estimate = analyze_query_string(
            schema_info, first
        ).cardinality_estimate
        self.assertAlmostEqual(1, second_page_cardinality_estimate)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_basic_pagination_mssql_uuids(self) -> None:
        """Ensure a basic pagination query is handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LastSixBytesFirst}
            for vertex_name in schema_graph.vertex_class_names
        }
        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal")
            }
        }""",
            {},
        )

        count_data = {
            "Animal": 4,
        }

        statistics = LocalStatistics(count_data)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        first_page_and_remainder, _ = paginate_query(schema_info, query, 1)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        expected_first = QueryStringWithParameters(
            """{
                Animal {
                    uuid @filter(op_name: "<", value: ["$__paged_param_0"])
                    name @output(out_name: "animal")
                }
            }""",
            {
                "__paged_param_0": "00000000-0000-0000-0000-400000000000",
            },
        )

        expected_remainder = QueryStringWithParameters(
            """{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_0"])
                    name @output(out_name: "animal")
                }
            }""",
            {
                "__paged_param_0": "00000000-0000-0000-0000-400000000000",
            },
        )

        # Check that the correct first page and remainder are generated
        compare_graphql(self, expected_first.query_string, first.query_string)
        self.assertEqual(expected_first.parameters, first.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder.parameters, remainder[0].parameters)

        # Check that the first page is estimated to fit into a page
        first_page_cardinality_estimate = analyze_query_string(
            schema_info, first
        ).cardinality_estimate
        self.assertAlmostEqual(1, first_page_cardinality_estimate)

        # Get the second page
        second_page_and_remainder, _ = paginate_query(schema_info, remainder[0], 1)
        second = second_page_and_remainder.one_page
        remainder = second_page_and_remainder.remainder

        expected_second = QueryStringWithParameters(
            """{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_0"])
                         @filter(op_name: "<", value: ["$__paged_param_1"])
                    name @output(out_name: "animal")
                }
            }""",
            {
                "__paged_param_0": "00000000-0000-0000-0000-400000000000",
                "__paged_param_1": "00000000-0000-0000-0000-800000000000",
            },
        )
        expected_remainder = QueryStringWithParameters(
            """{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_1"])
                    name @output(out_name: "animal")
                }
            }""",
            {
                "__paged_param_1": "00000000-0000-0000-0000-800000000000",
            },
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_second.query_string, second.query_string)
        self.assertEqual(expected_second.parameters, second.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder.parameters, remainder[0].parameters)

        # Check that the second page is estimated to fit into a page
        second_page_cardinality_estimate = analyze_query_string(
            schema_info, first
        ).cardinality_estimate
        self.assertAlmostEqual(1, second_page_cardinality_estimate)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_datetime(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Event"] = ("event_date",)  # Force pagination on datetime field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Event": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Event", "event_date"): [datetime.datetime(2000 + i, 1, 1) for i in range(101)],
            },
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
            Event {
                name @output(out_name: "event_name")
            }
        }""",
            {},
        )

        first_page_and_remainder, _ = paginate_query(schema_info, query, 100)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        # There are 1000 dates uniformly spread out between year 2000 and 3000, so to get
        # 100 results, we stop at 2010.
        expected_page_query = QueryStringWithParameters(
            """{
                Event {
                    event_date @filter(op_name: "<", value: ["$__paged_param_0"])
                    name @output(out_name: "event_name")
                }
            }""",
            {
                "__paged_param_0": datetime.datetime(2010, 1, 1, 0, 0),
            },
        )
        expected_remainder_query = QueryStringWithParameters(
            """{
                Event {
                    event_date @filter(op_name: ">=", value: ["$__paged_param_0"])
                    name @output(out_name: "event_name")
                }
            }""",
            {
                "__paged_param_0": datetime.datetime(2010, 1, 1, 0, 0),
            },
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_page_query.query_string, first.query_string)
        self.assertEqual(expected_page_query.parameters, first.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder_query.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder_query.parameters, remainder[0].parameters)

        # Get the second page
        second_page_and_remainder, _ = paginate_query(schema_info, remainder[0], 100)
        second = second_page_and_remainder.one_page
        remainder = second_page_and_remainder.remainder

        expected_page_query = QueryStringWithParameters(
            """{
                Event {
                    event_date @filter(op_name: ">=", value: ["$__paged_param_0"])
                               @filter(op_name: "<", value: ["$__paged_param_1"])
                    name @output(out_name: "event_name")
                }
            }""",
            {
                # TODO parameters seem wonky
                "__paged_param_0": datetime.datetime(2010, 1, 1, 0, 0),
                "__paged_param_1": datetime.datetime(2019, 1, 1, 0, 0),
            },
        )
        expected_remainder_query = QueryStringWithParameters(
            """{
                Event {
                    event_date @filter(op_name: ">=", value: ["$__paged_param_1"])
                    name @output(out_name: "event_name")
                }
            }""",
            {
                "__paged_param_1": datetime.datetime(2019, 1, 1, 0, 0),
            },
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_page_query.query_string, second.query_string)
        self.assertEqual(expected_page_query.parameters, second.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder_query.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder_query.parameters, remainder[0].parameters)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_datetime_existing_filter(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        # We allow pagination on uuid as well and leave it to the pagination planner to decide to
        # paginate on event_date to prevent empty pages if the two fields are correlated.
        pagination_keys["Event"] = ("uuid", "event_date")
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Event": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Event", "event_date"): [datetime.datetime(2000 + i, 1, 1) for i in range(101)],
            },
        )
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        local_datetime = datetime.datetime(2050, 1, 1, 0, 0)
        query = QueryStringWithParameters(
            """{
            Event {
                name @output(out_name: "event_name")
                event_date @filter(op_name: ">=", value: ["$date_lower"])
            }
        }""",
            {"date_lower": local_datetime},
        )

        first_page_and_remainder, _ = paginate_query(schema_info, query, 100)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        # There are 1000 dates uniformly spread out between year 2000 and 3000, so to get
        # 100 results after 2050, we stop at 2059.
        expected_page_query = QueryStringWithParameters(
            """{
                Event {
                    name @output(out_name: "event_name")
                    event_date @filter(op_name: ">=", value: ["$date_lower"])
                               @filter(op_name: "<", value: ["$__paged_param_0"])
                }
            }""",
            {
                "date_lower": local_datetime,
                "__paged_param_0": datetime.datetime(2059, 1, 1, 0, 0),
            },
        )
        expected_remainder_query = QueryStringWithParameters(
            """{
                Event {
                    name @output(out_name: "event_name")
                    event_date @filter(op_name: ">=", value: ["$__paged_param_0"])
                }
            }""",
            {
                "__paged_param_0": datetime.datetime(2059, 1, 1, 0, 0),
            },
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_page_query.query_string, first.query_string)
        self.assertEqual(expected_page_query.parameters, first.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder_query.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder_query.parameters, remainder[0].parameters)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_existing_datetime_filter(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Event"] = ("event_date",)  # Force pagination on datetime field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Event": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Event", "event_date"): [datetime.datetime(2000 + i, 1, 1) for i in range(101)],
            },
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
            Event {
                name @output(out_name: "event_name")
                event_date @filter(op_name: ">=", value: ["$date_lower"])
            }
        }""",
            {"date_lower": datetime.datetime(2050, 1, 1, 0, 0)},
        )

        first_page_and_remainder, _ = paginate_query(schema_info, query, 100)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        # We can't expect anything good when using a tz-aware filter on a tz-naive
        # field, but at least we shouldn't error. The current implementation ignores
        # the timezone, so this is a white-box test for that behavior.
        expected_page_query = QueryStringWithParameters(
            """{
                Event {
                    name @output(out_name: "event_name")
                    event_date @filter(op_name: ">=", value: ["$date_lower"])
                               @filter(op_name: "<", value: ["$__paged_param_0"])
                }
            }""",
            {
                "date_lower": datetime.datetime(2050, 1, 1, 0, 0),
                "__paged_param_0": datetime.datetime(2059, 1, 1, 0, 0),
            },
        )
        expected_remainder_query = QueryStringWithParameters(
            """{
                Event {
                    name @output(out_name: "event_name")
                    event_date @filter(op_name: ">=", value: ["$__paged_param_0"])
                }
            }""",
            {
                "__paged_param_0": datetime.datetime(2059, 1, 1, 0, 0),
            },
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_page_query.query_string, first.query_string)
        self.assertEqual(expected_page_query.parameters, first.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder_query.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder_query.parameters, remainder[0].parameters)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_int(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Species", "limbs"): [i for i in range(101)],
            },
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
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        expected_parameters = [25, 50, 75]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_int_few_quantiles(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 10000000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Species", "limbs"): [
                    0,
                    10,
                    20,
                    30,
                ],
            },
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
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 3)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        expected_parameters = [10, 20]
        self.assertEqual(expected_parameters, list(generated_parameters))

    def test_choose_parameter_values(self):
        self.assertEqual([1], list(_choose_parameter_values([1], 2)))
        self.assertEqual([1], list(_choose_parameter_values([1], 3)))
        self.assertEqual([1], list(_choose_parameter_values([1, 1], 3)))
        self.assertEqual([3], list(_choose_parameter_values([1, 3], 2)))
        self.assertEqual([1, 3], list(_choose_parameter_values([1, 3], 3)))
        self.assertEqual([1, 3], list(_choose_parameter_values([1, 3], 4)))
        self.assertEqual([3], list(_choose_parameter_values([1, 3, 5], 2)))
        self.assertEqual([3, 5], list(_choose_parameter_values([1, 3, 5], 3)))
        self.assertEqual([1, 3, 5], list(_choose_parameter_values([1, 3, 5], 4)))
        self.assertEqual([1, 3, 5], list(_choose_parameter_values([1, 3, 5], 5)))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_int_existing_filters(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Species", "limbs"): [i for i in range(101)],
            },
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
                limbs @filter(op_name: ">=", value: ["$limbs_lower"])
            }
        }""",
            {"limbs_lower": 25},
        )
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 3)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        expected_parameters = [50, 75]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_int_existing_filter_tiny_page(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={("Species", "limbs"): list(range(0, 101, 10))},
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
                limbs @filter(op_name: ">=", value: ["$limbs_lower"])
            }
        }""",
            {"limbs_lower": 10},
        )
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 10)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        first_parameter = next(generated_parameters)
        self.assertTrue(first_parameter > 10)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_int_existing_filters_2(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Species", "limbs"): [i for i in range(101)],
            },
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
                limbs @filter(op_name: "<", value: ["$limbs_upper"])
            }
        }""",
            {"limbs_upper": 76},
        )
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 3)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        expected_parameters = [25, 50]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_inline_fragment(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Species", "limbs"): [i for i in range(101)],
            },
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
                out_Entity_Related {
                    ... on Species {
                        name @output(out_name: "species_name")
                    }
                }
            }
        }""",
            {},
        )
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Species", "out_Entity_Related"), "limbs", 4)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        expected_parameters = [25, 50, 75]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_with_existing_filters(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts, field_quantiles={("Species", "limbs"): list(range(0, 1001, 10))}
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
                limbs @filter(op_name: "<", value: ["$num_limbs"])
                name @output(out_name: "species_name")
            }
        }""",
            {"num_limbs": 505},
        )
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        # XXX document why this is expected, see if bisect_left logic is correct
        expected_parameters = [130, 260, 390]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_datetime(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Event"] = ("event_date",)  # Force pagination on datetime field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Event": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Event", "event_date"): [datetime.datetime(2000 + i, 1, 1) for i in range(101)],
            },
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
            Event {
                name @output(out_name: "event_name")
            }
        }""",
            {},
        )
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Event",), "event_date", 4)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        expected_parameters = [
            datetime.datetime(2025, 1, 1, 0, 0),
            datetime.datetime(2050, 1, 1, 0, 0),
            datetime.datetime(2075, 1, 1, 0, 0),
        ]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_uuid(self):
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
        )

        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal_name")
            }
        }""",
            {},
        )
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Animal",), "uuid", 4)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        expected_parameters = [
            "40000000-0000-0000-0000-000000000000",
            "80000000-0000-0000-0000-000000000000",
            "c0000000-0000-0000-0000-000000000000",
        ]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_mssql_uuid(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LastSixBytesFirst}
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
            }
        }""",
            {},
        )
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Animal",), "uuid", 4)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        expected_parameters = [
            "00000000-0000-0000-0000-400000000000",
            "00000000-0000-0000-0000-800000000000",
            "00000000-0000-0000-0000-c00000000000",
        ]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_mssql_uuid_with_existing_filter(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LastSixBytesFirst}
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
                uuid @filter(op_name: ">=", value: ["$uuid_lower"])
                name @output(out_name: "animal_name")
            }
        }""",
            {
                "uuid_lower": "00000000-0000-0000-0000-800000000000",
            },
        )
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Animal",), "uuid", 4)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        expected_parameters = [
            "00000000-0000-0000-0000-a00000000000",
            "00000000-0000-0000-0000-c00000000000",
            "00000000-0000-0000-0000-e00000000000",
        ]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_consecutive(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={("Species", "limbs"): [0 for i in range(1000)] + list(range(101))},
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
        analysis = analyze_query_string(schema_info, query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)
        generated_parameters = generate_parameters_for_vertex_partition(analysis, vertex_partition)

        # Check that there are no duplicates
        list_parameters = list(generated_parameters)
        self.assertEqual(len(list_parameters), len(set(list_parameters)))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_query_parameterizer(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={("Species", "limbs"): [0 for i in range(1000)] + list(range(101))},
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
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)

        analysis = analyze_query_string(schema_info, query)
        next_page, remainder = generate_parameterized_queries(analysis, vertex_partition, 100)

        expected_next_page = """{
            Species {
                limbs @filter(op_name: "<", value: ["$__paged_param_0"])
                name @output(out_name: "species_name")
            }
        }"""
        expected_remainder = """{
            Species {
                limbs @filter(op_name: ">=", value: ["$__paged_param_0"])
                name @output(out_name: "species_name")
            }
        }"""
        compare_graphql(self, expected_next_page, print_ast(next_page.query_ast))
        compare_graphql(self, expected_remainder, print_ast(remainder.query_ast))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_query_parameterizer_name_conflict(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={("Species", "limbs"): [0 for i in range(1000)] + list(range(101))},
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
                     @filter(op_name: "!=", value: ["$__paged_param_0"])
            }
        }""",
            {"__paged_param_0": "Cow"},
        )
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)

        analysis = analyze_query_string(schema_info, query)
        next_page, remainder = generate_parameterized_queries(analysis, vertex_partition, 100)

        expected_next_page = """{
            Species {
                limbs @filter(op_name: "<", value: ["$__paged_param_1"])
                name @output(out_name: "species_name")
                     @filter(op_name: "!=", value: ["$__paged_param_0"])
            }
        }"""
        expected_remainder = """{
            Species {
                limbs @filter(op_name: ">=", value: ["$__paged_param_1"])
                name @output(out_name: "species_name")
                     @filter(op_name: "!=", value: ["$__paged_param_0"])
            }
        }"""
        compare_graphql(self, expected_next_page, print_ast(next_page.query_ast))
        compare_graphql(self, expected_remainder, print_ast(remainder.query_ast))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_query_parameterizer_filter_deduplication(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={("Species", "limbs"): [0 for i in range(1000)] + list(range(101))},
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
                limbs @filter(op_name: ">=", value: ["$limbs_more_than"])
                name @output(out_name: "species_name")
            }
        }""",
            {
                "limbs_more_than": 100,
            },
        )
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)

        analysis = analyze_query_string(schema_info, query)
        next_page, remainder = generate_parameterized_queries(analysis, vertex_partition, 100)

        expected_next_page = """{
            Species {
                limbs @filter(op_name: ">=", value: ["$limbs_more_than"])
                      @filter(op_name: "<", value: ["$__paged_param_0"])
                name @output(out_name: "species_name")
            }
        }"""
        expected_remainder = """{
            Species {
                limbs @filter(op_name: ">=", value: ["$__paged_param_0"])
                name @output(out_name: "species_name")
            }
        }"""
        compare_graphql(self, expected_next_page, print_ast(next_page.query_ast))
        compare_graphql(self, expected_remainder, print_ast(remainder.query_ast))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_no_pagination(self):
        """Ensure pagination is not done when not needed."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        original_query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal")
            }
        }""",
            {},
        )

        count_data = {
            "Animal": 4,
        }

        statistics = LocalStatistics(count_data)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        first_page_and_remainder, _ = paginate_query(schema_info, original_query, 10)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        # No pagination necessary
        compare_graphql(self, original_query.query_string, first.query_string)
        self.assertEqual(original_query.parameters, first.parameters)
        self.assertEqual(0, len(remainder))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_impossible_pagination(self):
        """Ensure no unwanted error is raised when pagination is needed but stats are missing."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {}  # No pagination keys, so the planner has no options
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        original_query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal")
            }
        }""",
            {},
        )

        count_data = {
            "Animal": 100000,
        }

        statistics = LocalStatistics(count_data)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        first_page_and_remainder, _ = paginate_query(schema_info, original_query, 10)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        # Query should be split, but there's no viable pagination method.
        compare_graphql(self, original_query.query_string, first.query_string)
        self.assertEqual(original_query.parameters, first.parameters)
        self.assertEqual(0, len(remainder))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_impossible_pagination_strong_filters_few_repeated_quantiles(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000000000000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Species", "limbs"): list(i for i in range(0, 101, 10) for _ in range(10000))
            },
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
                limbs @filter(op_name: "between", value: ["$limbs_lower", "$limbs_upper"])
            }
        }""",
            {
                "limbs_lower": 10,
                "limbs_upper": 14,
            },
        )

        first_page_and_remainder, _ = paginate_query(schema_info, query, 10)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        # Query should be split, but there's not enough quantiles
        compare_graphql(self, query.query_string, first.query_string)
        self.assertEqual(query.parameters, first.parameters)
        self.assertEqual(0, len(remainder))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_impossible_pagination_strong_filters_few_quantiles(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000000000000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={
                ("Species", "limbs"): list(i for i in range(0, 101, 10) for _ in range(10000))
            },
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
                limbs @filter(op_name: "between", value: ["$limbs_lower", "$limbs_upper"])
            }
        }""",
            {
                "limbs_lower": 10,
                "limbs_upper": 14,
            },
        )

        first_page_and_remainder, _ = paginate_query(schema_info, query, 10)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        # Query should be split, but there's not enough quantiles
        compare_graphql(self, query.query_string, first.query_string)
        self.assertEqual(query.parameters, first.parameters)
        self.assertEqual(0, len(remainder))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_with_compiler_tests(self):
        """Test that pagination doesn't crash on any of the queries from the compiler tests."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        count_data = {vertex_name: 100 for vertex_name in schema_graph.vertex_class_names}
        count_data.update({edge_name: 100 for edge_name in schema_graph.edge_class_names})
        statistics = LocalStatistics(count_data)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        arbitrary_value_for_type = {
            "String": "string_1",
            "ID": "40000000-0000-0000-0000-000000000000",
            "Int": 5,
            "Date": datetime.date(2000, 1, 1),
            "DateTime": datetime.datetime(2000, 1, 1),
            "Decimal": 5.3,
            "[String]": ["string_1", "string_2"],
        }

        for test_name in get_function_names_from_module(test_input_data):
            method = getattr(test_input_data, test_name)
            if hasattr(method, "__annotations__"):
                output_type = method.__annotations__.get("return")
                if output_type == CommonTestData:
                    test_data = method()
                    query = test_data.graphql_input
                    args = {
                        arg_name: arbitrary_value_for_type[str(arg_type)]
                        for arg_name, arg_type in test_data.expected_input_metadata.items()
                    }
                    paginate_query(schema_info, QueryStringWithParameters(query, args), 10)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_missing_vertex_class_count(self) -> None:
        """Ensure a basic pagination query is handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        query = QueryStringWithParameters(
            """{
            Animal {
                name @output(out_name: "animal")
            }
        }""",
            {},
        )

        # No class counts provided
        statistics = LocalStatistics({})
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        first_page_and_remainder, advisories = paginate_query(schema_info, query, 1)
        self.assertTrue(first_page_and_remainder.remainder == tuple())
        self.assertEqual(advisories, (MissingClassCount("Animal"),))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_missing_non_root_vertex_class_count(self) -> None:
        """Ensure a basic pagination query is handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        query = QueryStringWithParameters(
            """{
            Animal {
                out_Animal_LivesIn {
                    name @output(out_name: "animal")
                }
            }
        }""",
            {},
        )

        # No counts for Location
        count_data = {
            "Animal": 1000,
            "Animal_LivesIn": 1000,
        }

        statistics = LocalStatistics(count_data)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        first_page_and_remainder, advisories = paginate_query(schema_info, query, 1)
        self.assertTrue(first_page_and_remainder.remainder == tuple())
        self.assertEqual(advisories, (MissingClassCount("Location"),))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_missing_edge_class_count(self) -> None:
        """Ensure a basic pagination query is handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        query = QueryStringWithParameters(
            """{
            Animal {
                out_Animal_LivesIn {
                    name @output(out_name: "animal")
                }
            }
        }""",
            {},
        )

        # No counts for Animal_LivesIn
        count_data = {
            "Animal": 1000,
            "Location": 10000,
        }

        statistics = LocalStatistics(count_data)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_field_info=uuid4_field_info,
        )

        first_page_and_remainder, advisories = paginate_query(schema_info, query, 1)
        self.assertTrue(first_page_and_remainder.remainder == tuple())
        self.assertEqual(advisories, (MissingClassCount("Animal_LivesIn"),))

    @pytest.mark.xfail(strict=True, reason="inline fragment not supported", raises=Exception)
    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_with_inline_fragment(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {
            vertex_name: ("uuid",) for vertex_name in schema_graph.vertex_class_names
        }
        pagination_keys["Species"] = ("limbs",)  # Force pagination on int field
        uuid4_field_info = {
            vertex_name: {"uuid": UUIDOrdering.LeftToRight}
            for vertex_name in schema_graph.vertex_class_names
        }
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts,
            field_quantiles={("Species", "limbs"): list(range(100))},
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
                out_Entity_Related {
                    ... on Species {
                        name @output(out_name: "species_name")
                    }
                }
            }
        }""",
            {},
        )
        analysis = analyze_query_string(schema_info, query)

        vertex_partition_plan = VertexPartitionPlan(("Species", "out_Entity_Related"), "limbs", 2)

        generated_parameters = generate_parameters_for_vertex_partition(
            analysis, vertex_partition_plan
        )

        sentinel = object()
        first_param = next(generated_parameters, sentinel)
        self.assertEqual(50, first_param)

        page_query, _ = generate_parameterized_queries(analysis, vertex_partition_plan, first_param)

        expected_page_query_string = """{
            Species {
                out_Entity_Related {
                    ... on Species {
                        limbs @filter(op_name: "<", value: ["$__paged_param_0"])
                        name @output(out_name: "species_name")
                    }
                }
            }
        }"""
        compare_graphql(self, expected_page_query_string, print_ast(page_query.query_ast))
