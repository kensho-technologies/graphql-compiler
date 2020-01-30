# Copyright 2019-present Kensho Technologies, LLC.
import datetime
from typing import Tuple
import unittest

from graphql import print_ast
import pytest
import pytz

from ...ast_manipulation import safe_parse_graphql
from ...cost_estimation.cardinality_estimator import estimate_query_result_cardinality
from ...cost_estimation.statistics import LocalStatistics
from ...global_utils import ASTWithParameters, QueryStringWithParameters
from ...query_pagination import paginate_query
from ...query_pagination.pagination_planning import (
    InsufficientQuantiles,
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
from ...schema.schema_info import QueryPlanningSchemaInfo
from ...schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from ..test_helpers import compare_graphql, generate_schema_graph


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

        # Check that the correct plan is generated when it's obvious (page the root)
        query = """{
            Animal {
                name @output(out_name: "animal_name")
            }
        }"""
        number_of_pages = 10
        query_ast = safe_parse_graphql(query)
        pagination_plan, warnings = get_pagination_plan(schema_info, query_ast, number_of_pages)
        expected_plan = PaginationPlan((VertexPartitionPlan(("Animal",), "uuid", number_of_pages),))
        expected_warnings: Tuple[PaginationAdvisory, ...] = tuple()
        self.assertEqual([w.message for w in expected_warnings], [w.message for w in warnings])
        self.assertEqual(expected_plan, pagination_plan)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_planning_on_int(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
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
            uuid4_fields=uuid4_fields,
        )

        # Check that the paginator generates a plan paginating on an int field
        query = """{
            Species {
                name @output(out_name: "species_name")
            }
        }"""
        number_of_pages = 10
        query_ast = safe_parse_graphql(query)
        pagination_plan, warnings = get_pagination_plan(schema_info, query_ast, number_of_pages)
        expected_plan = PaginationPlan(
            (VertexPartitionPlan(("Species",), "limbs", number_of_pages),)
        )
        expected_warnings: Tuple[PaginationAdvisory, ...] = ()
        self.assertEqual([w.message for w in expected_warnings], [w.message for w in warnings])
        self.assertEqual(expected_plan, pagination_plan)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_planning_on_int_error(self) -> None:
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(class_counts)
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        # Check that the paginator detects a lack of quantile data for Species.limbs
        query = """{
            Species {
                name @output(out_name: "species_name")
            }
        }"""
        number_of_pages = 10
        query_ast = safe_parse_graphql(query)
        pagination_plan, warnings = get_pagination_plan(schema_info, query_ast, number_of_pages)
        expected_plan = PaginationPlan(tuple())
        expected_warnings = (InsufficientQuantiles("Species", "limbs", 0, 51),)
        self.assertEqual([w.message for w in expected_warnings], [w.message for w in warnings])
        self.assertEqual(expected_plan, pagination_plan)

    # TODO: These tests can be sped up by having an existing test SchemaGraph object.
    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_basic_pagination(self) -> None:
        """Ensure a basic pagination query is handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)  # type: ignore  # from fixture
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
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
            {"__paged_param_0": "40000000-0000-0000-0000-000000000000",},
        )

        expected_remainder = QueryStringWithParameters(
            """{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_param_0"])
                    name @output(out_name: "animal")
                }
            }""",
            {"__paged_param_0": "40000000-0000-0000-0000-000000000000",},
        )

        # Check that the correct first page and remainder are generated
        compare_graphql(self, expected_first.query_string, first.query_string)
        self.assertEqual(expected_first.parameters, first.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder.parameters, remainder[0].parameters)

        # Check that the first page is estimated to fit into a page
        first_page_cardinality_estimate = estimate_query_result_cardinality(
            schema_info, first.query_string, first.parameters
        )
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
            {"__paged_param_1": "80000000-0000-0000-0000-000000000000",},
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_second.query_string, second.query_string)
        self.assertEqual(expected_second.parameters, second.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder.parameters, remainder[0].parameters)

        # Check that the second page is estimated to fit into a page
        second_page_cardinality_estimate = estimate_query_result_cardinality(
            schema_info, second.query_string, second.parameters
        )
        self.assertAlmostEqual(1, second_page_cardinality_estimate)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_datetime(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Event"] = "event_date"  # Force pagination on datetime field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
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
            {"__paged_param_0": datetime.datetime(2010, 1, 1, 0, 0),},
        )
        expected_remainder_query = QueryStringWithParameters(
            """{
                Event {
                    event_date @filter(op_name: ">=", value: ["$__paged_param_0"])
                    name @output(out_name: "event_name")
                }
            }""",
            {"__paged_param_0": datetime.datetime(2010, 1, 1, 0, 0),},
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
            {"__paged_param_1": datetime.datetime(2019, 1, 1, 0, 0),},
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
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Event"] = "event_date"  # Force pagination on datetime field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
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
        # 100 results after 2050, we stop at 2058.
        expected_page_query = QueryStringWithParameters(
            """{
                Event {
                    name @output(out_name: "event_name")
                    event_date @filter(op_name: ">=", value: ["$date_lower"])
                               @filter(op_name: "<", value: ["$__paged_param_0"])
                }
            }""",
            {"date_lower": local_datetime, "__paged_param_0": datetime.datetime(2058, 1, 1, 0, 0),},
        )
        expected_remainder_query = QueryStringWithParameters(
            """{
                Event {
                    name @output(out_name: "event_name")
                    event_date @filter(op_name: ">=", value: ["$__paged_param_0"])
                }
            }""",
            {"__paged_param_0": datetime.datetime(2058, 1, 1, 0, 0),},
        )

        # Check that the correct queries are generated
        compare_graphql(self, expected_page_query.query_string, first.query_string)
        self.assertEqual(expected_page_query.parameters, first.parameters)
        self.assertEqual(1, len(remainder))
        compare_graphql(self, expected_remainder_query.query_string, remainder[0].query_string)
        self.assertEqual(expected_remainder_query.parameters, remainder[0].parameters)

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_pagination_datetime_existing_tz_aware_filter(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Event"] = "event_date"  # Force pagination on datetime field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
        )

        query = QueryStringWithParameters(
            """{
            Event {
                name @output(out_name: "event_name")
                event_date @filter(op_name: ">=", value: ["$date_lower"])
            }
        }""",
            {"date_lower": datetime.datetime(2050, 1, 1, 0, 0, tzinfo=pytz.utc)},
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
                "date_lower": datetime.datetime(2050, 1, 1, 0, 0, tzinfo=pytz.utc),
                "__paged_param_0": datetime.datetime(2058, 1, 1, 0, 0),
            },
        )
        expected_remainder_query = QueryStringWithParameters(
            """{
                Event {
                    name @output(out_name: "event_name")
                    event_date @filter(op_name: ">=", value: ["$__paged_param_0"])
                }
            }""",
            {"__paged_param_0": datetime.datetime(2058, 1, 1, 0, 0),},
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
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts, field_quantiles={("Species", "limbs"): [i for i in range(101)],}
        )
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                name @output(out_name: "species_name")
            }
        }"""
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition
        )

        expected_parameters = [25, 50, 75]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_int_few_quantiles(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {"Species": 10000000}
        statistics = LocalStatistics(
            class_counts, field_quantiles={("Species", "limbs"): [0, 10, 20, 30,],}
        )
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                name @output(out_name: "species_name")
            }
        }"""
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 3)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition
        )

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
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts, field_quantiles={("Species", "limbs"): [i for i in range(101)],}
        )
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                name @output(out_name: "species_name")
                limbs @filter(op_name: ">=", value: ["$limbs_lower"])
            }
        }"""
        args = {"limbs_lower": 26}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 3)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition
        )

        expected_parameters = [50, 75]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_int_existing_filters_2(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts, field_quantiles={("Species", "limbs"): [i for i in range(101)],}
        )
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                name @output(out_name: "species_name")
                limbs @filter(op_name: "<", value: ["$limbs_upper"])
            }
        }"""
        args = {"limbs_upper": 76}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 3)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition
        )

        expected_parameters = [25, 50]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_inline_fragment(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
        class_counts = {"Species": 1000}
        statistics = LocalStatistics(
            class_counts, field_quantiles={("Species", "limbs"): [i for i in range(101)],}
        )
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                out_Entity_Related {
                    ... on Species {
                        name @output(out_name: "species_name")
                    }
                }
            }
        }"""
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species", "out_Entity_Related"), "limbs", 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition
        )

        expected_parameters = [25, 50, 75]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_with_existing_filters(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                limbs @filter(op_name: "<", value: ["$num_limbs"])
                name @output(out_name: "species_name")
            }
        }"""
        args = {"num_limbs": 505}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition
        )

        # XXX document why this is expected, see if bisect_left logic is correct
        expected_parameters = [130, 260, 390]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_datetime(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Event"] = "event_date"  # Force pagination on datetime field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Event {
                name @output(out_name: "event_name")
            }
        }"""
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Event",), "event_date", 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition
        )

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

        query = """{
            Animal {
                name @output(out_name: "animal_name")
            }
        }"""
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Animal",), "uuid", 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition
        )

        expected_parameters = [
            "40000000-0000-0000-0000-000000000000",
            "80000000-0000-0000-0000-000000000000",
            "c0000000-0000-0000-0000-000000000000",
        ]
        self.assertEqual(expected_parameters, list(generated_parameters))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_parameter_value_generation_consecutive(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                name @output(out_name: "species_name")
            }
        }"""
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)
        generated_parameters = generate_parameters_for_vertex_partition(
            schema_info, query_ast, args, vertex_partition
        )

        # Check that there are no duplicates
        list_parameters = list(generated_parameters)
        self.assertEqual(len(list_parameters), len(set(list_parameters)))

    @pytest.mark.usefixtures("snapshot_orientdb_client")
    def test_query_parameterizer(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                name @output(out_name: "species_name")
            }
        }"""
        args = {}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)
        next_page, remainder = generate_parameterized_queries(
            schema_info, ASTWithParameters(query_ast, args), vertex_partition, 100
        )

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
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                name @output(out_name: "species_name")
                     @filter(op_name: "!=", value: ["$__paged_param_0"])
            }
        }"""
        args = {"__paged_param_0": "Cow"}
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)
        next_page, remainder = generate_parameterized_queries(
            schema_info, ASTWithParameters(query_ast, args), vertex_partition, 100
        )

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
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        pagination_keys["Species"] = "limbs"  # Force pagination on int field
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
        )

        query = """{
            Species {
                limbs @filter(op_name: ">=", value: ["$limbs_more_than"])
                name @output(out_name: "species_name")
            }
        }"""
        args = {
            "limbs_more_than": 100,
        }
        query_ast = safe_parse_graphql(query)
        vertex_partition = VertexPartitionPlan(("Species",), "limbs", 4)
        next_page, remainder = generate_parameterized_queries(
            schema_info, ASTWithParameters(query_ast, args), vertex_partition, 100
        )

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
        pagination_keys = {vertex_name: "uuid" for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {"uuid"} for vertex_name in schema_graph.vertex_class_names}
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
            uuid4_fields=uuid4_fields,
        )

        first_page_and_remainder, _ = paginate_query(schema_info, original_query, 10)
        first = first_page_and_remainder.one_page
        remainder = first_page_and_remainder.remainder

        # No pagination necessary
        compare_graphql(self, original_query.query_string, first.query_string)
        self.assertEqual(original_query.parameters, first.parameters)
        self.assertEqual(0, len(remainder))
