# Copyright 2019-present Kensho Technologies, LLC.
from datetime import date
import unittest

import pytest

from .. import test_input_data
from ...compiler.metadata import FilterInfo
from ...cost_estimation.cardinality_estimator import estimate_query_result_cardinality
from ...cost_estimation.filter_selectivity_utils import (
    ABSOLUTE_SELECTIVITY, FRACTIONAL_SELECTIVITY, Selectivity, _combine_filter_selectivities,
    _create_integer_interval, _get_intersection_of_intervals,
    adjust_counts_for_filters
)
from ...cost_estimation.statistics import LocalStatistics
from ...schema.schema_info import QueryPlanningSchemaInfo
from ...schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from ..test_helpers import generate_schema_graph


def _make_schema_info_and_estimate_cardinality(schema_graph, statistics, graphql_input, args):
    graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
    pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
    uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
    schema_info = QueryPlanningSchemaInfo(
        schema=graphql_schema,
        type_equivalence_hints=type_equivalence_hints,
        schema_graph=schema_graph,
        statistics=statistics,
        pagination_keys=pagination_keys,
        uuid4_fields=uuid4_fields)
    return estimate_query_result_cardinality(schema_info, graphql_input, args)


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class CostEstimationTests(unittest.TestCase):
    """Test the cost estimation module using standard input data when possible."""

    # TODO: These tests can be sped up by having an existing test SchemaGraph object.
    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_root_count(self):
        """Ensure we correctly estimate the cardinality of the query root."""
        schema_graph = generate_schema_graph(self.orientdb_client)

        test_data = test_input_data.immediate_output()

        count_data = {
            'Animal': 3,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, test_data.graphql_input, dict()
        )
        expected_cardinality_estimate = 3.0

        self.assertEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traverse(self):
        """Ensure we correctly estimate cardinality over edges."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        test_data = test_input_data.traverse_and_output()

        count_data = {
            'Animal': 3,
            'Animal_ParentOf': 5,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, test_data.graphql_input, dict()
        )
        # For each Animal, there are on average 5.0 / 3.0 Animal_ParentOf edges, so we expect
        # 3.0 * (5.0 / 3.0) results.
        expected_cardinality_estimate = 5.0

        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fragment(self):
        """Ensure we correctly adjust for fragments."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        test_data = test_input_data.simple_union()

        count_data = {
            'Species': 3,
            'Species_Eats': 5,
            'Food': 11,
            'FoodOrSpecies': 14,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, test_data.graphql_input, dict()
        )
        # For each Animal, we expect 5.0 / 3.0 out_Species_Eats edges. Out of those FoodOrSpecies,
        # we expect 11.0 / 14.0 to be Food, so overall we expect 3.0 * (5.0 / 3.0) * (11.0 / 14.0)
        expected_cardinality_estimate = 3.0 * (5.0 / 3.0) * (11.0 / 14.0)

        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_complex_traverse(self):
        """Ensure we correctly handle more complicated arrangements of traversals."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                in_Entity_Related {
                    ... on Food {
                        name @output(out_name: "food")
                        in_Species_Eats {
                            name @output(out_name: "species")
                        }
                    }
                }
                out_Animal_BornAt{
                    name @output(out_name: "birth_event")
                }
            }
        }'''

        count_data = {
            'Animal': 19,
            'Entity_Related': 3,
            'Food': 5,
            'FoodOrSpecies': 16,
            'Entity': 47,
            'Species_Eats': 7,
            'Species': 11,
            'Animal_BornAt': 13,
            'BirthEvent': 17
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, dict()
        )

        # For each Animal, we expect 3.0 / 19.0 in_Entity_Related edges, 5.0 / 47.0 of which are
        # Food. For each Food, we expect 7.0 / 16.0 in_Species_Eats edges. Separately, for each
        # Animal, we expect 13.0 / 19.0 out_Animal_BornAt edges. So in total, we expect:
        # 19.0 * (3.0 / 47.0) * (5.0 / 47.0) * (7.0 / 16.0) * (13.0 / 19.0) results.
        expected_cardinality_estimate = (
            19.0 * (3.0 / 47.0) * (5.0 / 47.0) * (7.0 / 16.0) * (13.0 / 19.0)
        )
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traversal_provided_both_statistics(self):
        """Test type coercion provided both class_counts and vertex_edge_vertex_counts."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Entity_Related {
                    ... on Event {
                        uuid @output(out_name: "event_id")
                    }
                }
            }
        }'''
        params = {}

        count_data = {
            'Entity': 19,
            'Animal': 3,
            'Event': 7,
            'Entity_Related': 11
        }
        vertex_edge_vertex_data = {
            ('Animal', 'Entity_Related', 'Event'): 2
        }
        statistics = LocalStatistics(
            count_data, vertex_edge_vertex_counts=vertex_edge_vertex_data
        )

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Animal, vertex_edge_vertex counts tell us we should expect (2.0 / 3.0) Events
        # when traversing using Entity_Related. This totals to 3.0 * (2.0 / 3.0) results.
        expected_cardinality_estimate = 3.0 * (2.0 / 3.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traversal_with_no_results(self):
        """Test type coercion where no results should be expected."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Entity_Related {
                    ... on Event {
                        uuid @output(out_name: "event_id")
                    }
                }
            }
        }'''
        params = {}

        count_data = {
            'Entity': 19,
            'Animal': 3,
            'Event': 7,
            'Entity_Related': 11
        }
        vertex_edge_vertex_data = {
            ('Animal', 'Entity_Related', 'Event'): 0
        }
        statistics = LocalStatistics(
            count_data, vertex_edge_vertex_counts=vertex_edge_vertex_data
        )

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # Vertex_edge_vertex_data tells us that no Entity_Related edges connect Animals and Events,
        # so the result set is empty.
        expected_cardinality_estimate = 0.0
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traversal_in_inbound_direction_provided_both_statistics(self):
        """Test traversal in inbound direction provided multiple statistics."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Event {
                in_Entity_Related {
                    ... on Animal {
                        uuid @output(out_name: "animal_id")
                    }
                }
            }
        }'''
        params = {}

        count_data = {
            'Entity': 19,
            'Animal': 3,
            'Event': 7,
            'Entity_Related': 11
        }
        vertex_edge_vertex_data = {
            ('Animal', 'Entity_Related', 'Event'): 2
        }
        statistics = LocalStatistics(
            count_data, vertex_edge_vertex_counts=vertex_edge_vertex_data
        )

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Event, vertex_edge_vertex_count tells us we should expect (2.0 / 7.0) Animals
        # when traversing using Entity_Related. This totals to 7.0 * (2.0 / 7.0) result sets.
        expected_cardinality_estimate = 7.0 * (2.0 / 7.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traversals_with_different_statistics_combination(self):
        """Test two traversals, where one has vertex_edge_vertex counts and the other doesn't."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Entity_Related {
                    ... on Event {
                        uuid @output(out_name: "event_id")
                        out_Entity_Related {
                            ... on Location {
                                name @output(out_name: "location_name")
                            }
                        }
                    }
                }
            }
        }'''
        params = {}

        count_data = {
            'Entity': 19,
            'Animal': 3,
            'Event': 7,
            'Entity_Related': 11,
            'Location': 13
        }
        vertex_edge_vertex_data = {
            ('Animal', 'Entity_Related', 'Event'): 2
        }
        statistics = LocalStatistics(
            count_data, vertex_edge_vertex_counts=vertex_edge_vertex_data
        )

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Animal, we expect (2.0 / 3.0) Events when traversing using Entity_Related edge.
        # For each further Event, we estimate there are (11.0 / 19.0) outgoing Entity_Related
        # edges. Of those, a total of (11.0 / 19.0) * (13.0 / 19.0) edges go into a Location.
        # So our total is 3.0 * (2.0 / 3.0) * (11.0 / 19.0) * (13.0 / 19.0)

        expected_cardinality_estimate = 3.0 * (2.0 / 3.0) * (11.0 / 19.0) * (13.0 / 19.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional(self):
        """Ensure we handle an optional edge correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_BornAt @optional {
                    name @output(out_name: "birth_event")
                }
                out_Animal_FedAt @optional {
                    name @output(out_name: "feeding_event")
                }
            }
        }'''

        count_data = {
            'Animal': 5,
            'Animal_BornAt': 7,
            'Animal_FedAt': 3,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, dict()
        )

        # For each Animal, we expect 7.0 / 5.0 out_Animal_BornAt edges, yielding 5.0 * (7.0 / 5.0)
        # result sets. For each of these we expect 3.0 / 5.0 out_Animal_FedAt edges, but since this
        # is optional, we return a result set even if it doesn't have a connected FeedingEvent (i.e.
        # the expected cardinality can never decrease via an optional). So in total, we expect 5.0 *
        # (7.0 / 5.0) results.
        expected_cardinality_estimate = 5.0 * (7.0 / 5.0)

        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional_and_traverse(self):
        """Ensure traversals inside optionals are handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                in_Entity_Related @optional {
                    ... on Food {
                        in_Species_Eats {
                            name @output(out_name: "species")
                        }
                    }
                }
            }
        }'''

        count_data = {
            'Animal': 3,
            'Entity_Related': 23,
            'Food': 7,
            'FoodOrSpecies': 13,
            'Entity': 11,
            'Species_Eats': 5,
            'Species': 97,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, dict()
        )

        # For each Animal, we expect 23.0 / 11.0 * 7.0 / 11.0 * 5.0 / 13.0 = .511
        # Animal->Food->Species result sets. Since the Food->Species parts are optional, we expect
        # at least one result per Animal, so we expect 3.0 results.
        expected_cardinality_estimate = 3.0
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

        count_data = {
            'Animal': 3,
            'Entity_Related': 23,
            'Food': 7,
            'FoodOrSpecies': 13,
            'Entity': 11,
            'Species_Eats': 17,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, dict()
        )

        # For each Animal, we expect 23.0 / 11.0 * 7.0 / 11.0 * 17.0 / 13.0 = 1.74
        # Animal->Food->Species result sets, so we expect 3.0 * 1.74  results.
        expected_cardinality_estimate = 3.0 * (23.0 / 11.0) * (7.0 / 11.0) * (17.0 / 13.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold(self):
        """Ensure we handle an folded edge correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_BornAt @fold {
                    name @output(out_name: "birth_event")
                }
                out_Animal_FedAt @fold {
                    name @output(out_name: "feeding_event")
                }
            }
        }'''

        count_data = {
            'Animal': 5,
            'Animal_BornAt': 7,
            'Animal_FedAt': 3,
            'FeedingEvent': 11
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, dict()
        )

        # For each Animal, we expect 7.0 / 5.0 out_Animal_BornAt edges, yielding 5.0 * (7.0 / 5.0)
        # result sets. For each of these we expect 3.0 / 5.0 out_Animal_FedAt edges, but since this
        # is folded, we return a result set even if it doesn't have a connected FeedingEvent (i.e.
        # the expected cardinality can never decrease via an optional). So in total, we expect 5.0 *
        # (7.0 / 5.0) results.
        expected_cardinality_estimate = 5.0 * (7.0 / 5.0)

        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_and_traverse(self):
        """Ensure traversals inside folds are handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                in_Entity_Related @fold {
                    ... on Food {
                        in_Species_Eats {
                            name @output(out_name: "species")
                        }
                    }
                }
            }
        }'''

        count_data = {
            'Animal': 3,
            'Entity_Related': 23,
            'Food': 7,
            'FoodOrSpecies': 13,
            'Entity': 11,
            'Species_Eats': 5,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, dict()
        )

        # For each Animal, we expect 23.0 / 11.0 * 7.0 / 11.0 * 5.0 / 13.0 = .511
        # Animal->Food->Species result sets. Since the Food->Species parts are folded, we expect
        # at least one result per Animal, so we expect 3.0 results.
        expected_cardinality_estimate = 3.0
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

        count_data = {
            'Animal': 3,
            'Entity_Related': 23,
            'Food': 7,
            'FoodOrSpecies': 13,
            'Entity': 11,
            'Species_Eats': 17,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, dict()
        )

        # For each Animal, we expect 23.0 / 11.0 * 7.0 / 11.0 * 17.0 / 13.0 = 1.74
        # Animal->Food->Species result sets, so we expect 3.0 * 1.74  results.
        expected_cardinality_estimate = 3.0 * (23.0 / 11.0) * (7.0 / 11.0) * (17.0 / 13.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_recurse(self):
        """Ensure we handle recursion correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 2){
                    name @output(out_name: "animal")
                }
            }
        }'''

        count_data = {
            'Animal': 7,
            'Animal_ParentOf': 11,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, dict()
        )

        # For each Animal, we expect 11.0 / 7.0 "child" Animals. Since recurse first explores
        # depth=0, we add 1 to account for the parent. At the moment, we don't account for depths
        # greater than 1, so we expect 7.0 * (11.0 / 7.0 + 1) results.
        expected_cardinality_estimate = 7.0 * (11.0 / 7.0 + 1)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_recurse_and_traverse(self):
        """Ensure we handle traversals inside recurses correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 2){
                    name @output(out_name: "animal")
                    out_Animal_BornAt {
                        name @output(out_name: "birth_event")
                    }
                }
            }
        }'''

        count_data = {
            'Animal': 7,
            'Animal_ParentOf': 11,
            'Animal_BornAt': 13,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, dict()
        )

        # For each Animal, we expect 11.0 / 7.0 "child" Animals. Since recurse first explores
        # depth=0, we add 1 to account for the parent. At the moment, we don't account for depths
        # greater than 1, so we exepct 11.0 / 7.0 + 1 total children, each of which has 13.0 / 7.0
        # Animal_BornAt edges.
        expected_cardinality_estimate = 7.0 * (11.0 / 7.0 + 1) * (13.0 / 7.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_single_filter(self):
        """Ensure we handle filters correctly."""
        # TODO: eventually, we should ensure other fractional/absolute selectivies work.
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                uuid @filter(op_name: "=", value:["$uuid"])
                name @output(out_name: "name")
            }
        }'''
        params = {
            'uuid': '00000000-0000-0000-0000-000000000000',
        }

        count_data = {
            'Animal': 3,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # When '='-filtering on a field that's uniquely indexed, expect exactly 1 result.
        expected_cardinality_estimate = 1.0
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traverse_and_filter(self):
        """Ensure we filters work correctly below the root location."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_BornAt {
                    uuid @filter(op_name: "=", value:["$uuid"])
                    out_Event_RelatedEvent {
                        ... on FeedingEvent {
                            name @output(out_name: "feeding_event")
                        }
                    }
                }
            }
        }'''
        params = {
            'uuid': '00000000-0000-0000-0000-000000000000',
        }

        count_data = {
            'Animal': 3,
            'Animal_BornAt': 5,
            'Event_RelatedEvent': 7,
            'Event': 17,
            'FeedingEvent': 11,
            'BirthEvent': 13
        }
        vertex_edge_vertex_data = {
            ('Animal', 'Animal_BornAt', 'BirthEvent'): 2
        }
        statistics = LocalStatistics(count_data, vertex_edge_vertex_counts=vertex_edge_vertex_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Animal, we expect exactly 1 BirthEvent. For each of these, we expect (7.0 / 17.0)
        # * (11.0 / 17.0) connected FeedingEvents.
        expected_cardinality_estimate = 3.0 * 1.0 * (7.0 / 17.0) * (11.0 / 17.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_multiple_filters(self):
        """Ensure we handle multiple filters correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal @filter(op_name: "name_or_alias", value: ["$name"]) {
                uuid @filter(op_name: "=", value:["$uuid"])
                net_worth @filter(op_name: ">", value: ["$worth"])
                name @output(out_name: "name")
            }
        }'''
        params = {
            'uuid': '00000000-0000-0000-0000-000000000000',
            'worth': 100.0,
        }

        count_data = {
            'Animal': 3,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # When '='-filtering on a field that's uniquely indexed, expect exactly 1 result. All other
        # filters are not currently implemented.
        expected_cardinality_estimate = 1.0
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_inequality_filters_on_uuid(self):
        """Ensure we handle inequality filters on UUIDs correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                uuid @filter(op_name: "<", value:["$uuid"])
                name @output(out_name: "name")
            }
        }'''
        # There's nearly an equal number of UUIDs below and above the UUID given in the params.
        params = {
            'uuid': '80000000-0000-0000-0000-000000000000',
        }

        count_data = {
            'Animal': 32,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # There are 32 Animals, and an estimated (1.0 / 2.0) of them have a UUID below the one given
        # in the parameters dict, so we get a result size of 32.0 * (1.0 / 2.0) = 16.0 results.
        expected_cardinality_estimate = 32.0 * (1.0 / 2.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional_and_filter(self):
        """Test an optional and filter on the same Location."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_BornAt @optional {
                    uuid @filter(op_name: "=", value:["$uuid"])
                    out_Event_RelatedEvent {
                        ... on FeedingEvent {
                            name @output(out_name: "feeding_event")
                        }
                    }
                }
            }
        }'''
        params = {
            'uuid': '00000000-0000-0000-0000-000000000000',
        }

        count_data = {
            'Animal': 5,
            'Animal_BornAt': 2,
            'Event_RelatedEvent': 11,
            'Event': 7,
            'FeedingEvent': 6,
            'BirthEvent': 13
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Animal, we expect exactly 1 BirthEvent (rather than 2.0 / 5.0). For each of
        # these, we expect (11.0 / 7.0) * (6.0 / 7.0) FeedingEvents. In general, we would have
        # expected (2.0 / 5.0) * (11.0 / 7.0) * (6.0 / 7.0) = .54 result sets per Animal, which the
        # optional would've converted into a 1. Now, we expect (11.0 / 5.0) * (6.0 / 7.0) = 1.35
        # result sets per Animal, avoiding the optional.
        expected_cardinality_estimate = 5.0 * 1.0 * (11.0 / 7.0) * (6.0 / 7.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional_then_filter(self):
        """Test a filter within an optional scope."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_BornAt @optional {
                    out_Event_RelatedEvent {
                        ... on FeedingEvent {
                            uuid @filter(op_name: "=", value:["$uuid"])
                            name @output(out_name: "feeding_event")
                        }
                    }
                }
            }
        }'''
        params = {
            'uuid': '00000000-0000-0000-0000-000000000000',
        }

        # Test that a filter correctly triggers the optional check for <1 subexpansion result.
        count_data = {
            'Animal': 5,
            'Animal_BornAt': 3,
            'Event_RelatedEvent': 23,
            'Event': 7,
            'FeedingEvent': 6,
            'BirthEvent': 13
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Animal, we expect exactly 2.0 / 5.0 BirthEvents. In general, for each of
        # these, we expect (23.0 / 7.0) * (6.0 / 7.0) FeedingEvents. Together this is 1.13
        # subexpansion results, but since there's a filter on FeedingEvents, we expect exactly 1,
        # giving 2.0 / 5.0 * 1.0 = .4 subexpansion results. Since this is optional, we raise it to
        # 1.0 and expect 5.0 * 1.0 = 5.0 results total.
        expected_cardinality_estimate = 5.0 * 1.0
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_and_filter(self):
        """Test an fold and filter on the same Location."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_BornAt @fold {
                    uuid @filter(op_name: "=", value:["$uuid"])
                    out_Event_RelatedEvent {
                        ... on FeedingEvent {
                            name @output(out_name: "feeding_event")
                        }
                    }
                }
            }
        }'''
        params = {
            'uuid': '00000000-0000-0000-0000-000000000000',
        }

        count_data = {
            'Animal': 5,
            'Animal_BornAt': 2,
            'Event_RelatedEvent': 11,
            'Event': 7,
            'FeedingEvent': 6,
            'BirthEvent': 13
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Animal, we expect exactly 1 BirthEvent (rather than 2.0 / 5.0). For each of
        # these, we expect (11.0 / 7.0) * (6.0 / 7.0) FeedingEvents. In general, we would have
        # expected (2.0 / 5.0) * (11.0 / 7.0) * (6.0 / 7.0) = .54 result sets per Animal, which the
        # fold would've converted into a 1. Now, we expect (11.0 / 5.0) * (6.0 / 7.0) = 1.35 result
        # sets per Animal, avoiding the fold.
        expected_cardinality_estimate = 5.0 * 1.0 * (11.0 / 7.0) * (6.0 / 7.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_then_filter(self):
        """Test a filter within an fold scope."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_BornAt @fold {
                    out_Event_RelatedEvent {
                        ... on FeedingEvent {
                            uuid @filter(op_name: "=", value:["$uuid"])
                            name @output(out_name: "feeding_event")
                        }
                    }
                }
            }
        }'''
        params = {
            'uuid': '00000000-0000-0000-0000-000000000000',
        }

        # Test that a filter correctly triggers the fold check for <1 subexpansion result.
        count_data = {
            'Animal': 5,
            'Animal_BornAt': 3,
            'Event_RelatedEvent': 23,
            'Event': 7,
            'FeedingEvent': 6,
            'BirthEvent': 11
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Animal, we expect exactly 2.0 / 5.0 BirthEvents. In general, for each of these,
        # we expect (23.0 / 7.0) * (6.0 / 7.0) FeedingEvents. Together this is 1.13 subexpansion
        # results, but since there's a filter on FeedingEvents, we expect exactly 1, giving 2.0 /
        # 5.0 * 1.0 = .4 subexpansion results. Since this is fold, we raise it to 1.0 and expect 5.0
        # * 1.0 = 5.0 results total.
        expected_cardinality_estimate = 5.0 * 1.0
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_recurse_and_filter(self):
        """Test a filter that immediately follows a recursed edge."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 2){
                    uuid @filter(op_name: "=", value:["$uuid"])
                    out_Animal_BornAt {
                        name @output(out_name: "birth_event")
                    }
                }
            }
        }'''
        params = {
            'uuid': '00000000-0000-0000-0000-000000000000',
        }

        count_data = {
            'Animal': 7,
            'Animal_ParentOf': 11,
            'Animal_BornAt': 13,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Animal, we expect 11.0 / 7.0 + 1 "child" Animals due to the recurse. Since
        # there's a filter immediately following, we only expect 1 Animal to pass. We expect this to
        # have 13.0 / 7.0 Animal_BornAt edges, giving a total of 7.0 * (13.0 / 7.0) results.
        expected_cardinality_estimate = 7.0 * 1.0 * (13.0 / 7.0)
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_recurse_then_filter(self):
        """Test a filter that immediately follows a recursed edge."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 2){
                    out_Animal_BornAt {
                        uuid @filter(op_name: "=", value:["$uuid"])
                        name @output(out_name: "birth_event")
                    }
                }
            }
        }'''
        params = {
            'uuid': '00000000-0000-0000-0000-000000000000',
        }

        count_data = {
            'Animal': 7,
            'Animal_ParentOf': 11,
            'Animal_BornAt': 13,
        }
        statistics = LocalStatistics(count_data)

        cardinality_estimate = _make_schema_info_and_estimate_cardinality(
            schema_graph, statistics, graphql_input, params
        )

        # For each Animal, we expect 11.0 / 7.0 + 1 "child" Animals due to the recurse. Since
        # there's a filter immediately following, we only expect 1 Animal to pass. We expect this to
        # have 13.0 / 7.0 Animal_BornAt edges, giving a total of 7.0 * (13.0 / 7.0) results.
        expected_cardinality_estimate = 7.0 * (11.0 / 7.0 + 1.0) * 1.0
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)


def _make_schema_info_and_get_filter_selectivity(schema_graph, statistics, filter_info,
                                                 parameters, location_name):
    graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
    pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
    uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
    schema_info = QueryPlanningSchemaInfo(
        schema=graphql_schema,
        type_equivalence_hints=type_equivalence_hints,
        schema_graph=schema_graph,
        statistics=statistics,
        pagination_keys=pagination_keys,
        uuid4_fields=uuid4_fields)
    return _get_filter_selectivity(schema_info, filter_info, parameters, location_name)


class IntegerIntervalTests(unittest.TestCase):
    """Test methods that create IntegerIntervals."""

    def test_interval_creation(self):
        """Test that intervals are created correctly, and that empty intervals are detected."""
        interval = _create_integer_interval(5, 1000)
        self.assertTrue(interval is not None)

        interval = _create_integer_interval(5, 5)
        self.assertTrue(interval is not None)

        interval = _create_integer_interval(5, 1)
        self.assertTrue(interval is None)

    def test_intersection_when_overlapping(self):
        """Test intersection computation for non-disjoint intervals."""
        interval_a = _create_integer_interval(1, 3)
        interval_b = _create_integer_interval(2, 4)

        expected_intersection = _create_integer_interval(2, 3)
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)

        interval_a = _create_integer_interval(4, 6)
        interval_b = _create_integer_interval(2, 4)

        expected_intersection = _create_integer_interval(4, 4)
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)

        interval_a = _create_integer_interval(4, 6)
        interval_b = _create_integer_interval(4, 6)

        expected_intersection = _create_integer_interval(4, 6)
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)

        interval_a = _create_integer_interval(0, None)
        interval_b = _create_integer_interval(4, 6)

        expected_intersection = _create_integer_interval(4, 6)
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)

        interval_a = _create_integer_interval(0, None)
        interval_b = _create_integer_interval(None, 6)

        expected_intersection = _create_integer_interval(0, 6)
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)

        interval_a = _create_integer_interval(None, None)
        interval_b = _create_integer_interval(None, 6)

        expected_intersection = _create_integer_interval(None, 6)
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)

        interval_a = _create_integer_interval(None, None)
        interval_b = _create_integer_interval(None, None)

        expected_intersection = _create_integer_interval(None, None)
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)

    def test_disjoint_intervals(self):
        """Test intersection computation when disjoint intervals are given."""
        interval_a = _create_integer_interval(1, 3)
        interval_b = _create_integer_interval(5, 7)

        expected_intersection = None
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)

        interval_a = _create_integer_interval(8, 10)
        interval_b = _create_integer_interval(5, 7)

        expected_intersection = None
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)

        interval_a = _create_integer_interval(0, 0)
        interval_b = _create_integer_interval(1, 1)

        expected_intersection = None
        received_intersection = _get_intersection_of_intervals(interval_a, interval_b)
        self.assertEqual(expected_intersection, received_intersection)
