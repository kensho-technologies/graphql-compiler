# Copyright 2019-present Kensho Technologies, LLC.
import datetime
from typing import Any, Dict, Tuple
import unittest

from graphql import print_ast
import pytest

from ...ast_manipulation import safe_parse_graphql
from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import QueryStringWithParameters, paginate_query
from ...query_pagination.pagination_planning import (
    InsufficientQuantiles,
    PaginationAdvisory,
    PaginationPlan,
    VertexPartitionPlan,
    get_pagination_plan,
)
from ...query_pagination.parameter_generator import generate_parameters_for_vertex_partition
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
        test_data = """{
            Animal {
                name @output(out_name: "animal")
            }
        }"""
        parameters: Dict[str, Any] = {}

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

        # Since query pagination is still a skeleton, we expect a NotImplementedError for this test.
        # Once query pagination is fully implemented, the result of this call should be equal to
        # expected_query_list.
        # pylint: disable=unused-variable
        with self.assertRaises(NotImplementedError):
            paginated_queries = paginate_query(  # noqa: unused-variable
                schema_info, test_data, parameters, 1
            )

        expected_query_list = (  # noqa: unused-variable
            QueryStringWithParameters(
                """{
                    Animal {
                        uuid @filter(op_name: "<", value: ["$_paged_upper_param_on_Animal_uuid"])
                        name @output(out_name: "animal")
                    }
                }""",
                {"_paged_upper_param_on_Animal_uuid": "40000000-0000-0000-0000-000000000000",},
            ),
            QueryStringWithParameters(
                """{
                    Animal {
                        uuid @filter(op_name: ">=", value: ["$_paged_lower_param_on_Animal_uuid"])
                        name @output(out_name: "animal")
                    }
                }""",
                {"_paged_lower_param_on_Animal_uuid": "40000000-0000-0000-0000-000000000000",},
            ),
        )
        # pylint: enable=unused-variable

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

        expected_parameters = [26, 51, 76]
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

        expected_parameters = [26, 51, 76]
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
        expected_parameters = [140, 270, 400]
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
            datetime.datetime(2026, 1, 1, 0, 0),
            datetime.datetime(2051, 1, 1, 0, 0),
            datetime.datetime(2076, 1, 1, 0, 0),
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
        next_page_ast, remainder_ast, param_name = generate_parameterized_queries(
            schema_info, query_ast, args, vertex_partition
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
        expected_param_name = "__paged_param_0"
        compare_graphql(self, expected_next_page, print_ast(next_page_ast))
        compare_graphql(self, expected_remainder, print_ast(remainder_ast))
        self.assertEqual(expected_param_name, param_name)
