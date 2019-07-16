# Copyright 2019-present Kensho Technologies, LLC.
from datetime import date
import unittest

import pytest

from .. import test_input_data
from ...compiler.metadata import FilterInfo
from ...cost_estimation.cardinality_estimator import estimate_query_result_cardinality
from ...cost_estimation.filter_selectivity_utils import (
    ABSOLUTE_SELECTIVITY, FRACTIONAL_SELECTIVITY, Selectivity, _combine_filter_selectivities,
    _get_filter_selectivity
)
from ..test_helpers import generate_schema_graph


def create_lookup_counts(count_data):
    """Create lookup_counts function for use in estimating query cost."""
    def lookup_counts(name):
        """Lookup the total number of instances and subinstances of a given class name."""
        return count_data[name]
    return lookup_counts


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class CostEstimationTests(unittest.TestCase):
    """Test the cost estimation module using standard input data when possible."""

    # TODO: These tests can be sped up by having an existing test SchemaGraph object.
    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_root_count(self):
        """"Ensure we correctly estimate the cardinality of the query root."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        test_data = test_input_data.immediate_output()

        count_data = {
            'Animal': 3,
        }
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, test_data.graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, test_data.graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, test_data.graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, dict()
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
        }
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, dict()
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, params
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
        }
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, params
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, params
        )

        # When '='-filtering on a field that's uniquely indexed, expect exactly 1 result. All other
        # filters are not currently implemented.
        expected_cardinality_estimate = 1.0
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
        }
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, params
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
        }
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, params
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
        }
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, params
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
        }
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, params
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, params
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
        lookup_counts = create_lookup_counts(count_data)

        cardinality_estimate = estimate_query_result_cardinality(
            schema_graph, lookup_counts, graphql_input, params
        )

        # For each Animal, we expect 11.0 / 7.0 + 1 "child" Animals due to the recurse. Since
        # there's a filter immediately following, we only expect 1 Animal to pass. We expect this to
        # have 13.0 / 7.0 Animal_BornAt edges, giving a total of 7.0 * (13.0 / 7.0) results.
        expected_cardinality_estimate = 7.0 * (11.0 / 7.0 + 1.0) * 1.0
        self.assertAlmostEqual(expected_cardinality_estimate, cardinality_estimate)


class FilterSelectivityUtilsTests(unittest.TestCase):
    def test_combine_filter_selectivities(self):
        """Test filter combination function."""
        # When there are no selectivities (e.g. there are no filters at a location, we should return
        # a dummy selectivity that doesn't affect the counts
        selectivities = []
        expected_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0)
        self.assertEqual(expected_selectivity, _combine_filter_selectivities(selectivities))

        # When there's a single selectivity, we should return that selectivity.
        fractional_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=0.5)
        self.assertEqual(
            fractional_selectivity, _combine_filter_selectivities([fractional_selectivity])
        )

        absolute_selectivity = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=5.0)
        self.assertEqual(
            absolute_selectivity, _combine_filter_selectivities([absolute_selectivity])
        )

        # When there are multiple fractional selectivities, multiply the values.
        fractional_selectivity1 = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=0.5)
        fractional_selectivity2 = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=0.6)
        selectivities = [fractional_selectivity1, fractional_selectivity2]

        expected_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=0.3)
        self.assertEqual(expected_selectivity, _combine_filter_selectivities(selectivities))

        # When there are multiple absolute selectivities, use the lowest value
        absolute_selectivity1 = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=2.0)
        absolute_selectivity2 = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=3.0)
        selectivities = [absolute_selectivity1, absolute_selectivity2]

        expected_selectivity = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=2.0)
        self.assertEqual(expected_selectivity, _combine_filter_selectivities(selectivities))

        # When there are mixed selectivities, use the lowest absolute-kind value.
        absolute_selectivity1 = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=4.0)
        fractional_selectivity1 = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=0.5)
        absolute_selectivity2 = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=2.0)
        fractional_selectivity2 = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=0.6)
        absolute_selectivity3 = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=3.0)
        selectivities = [
            absolute_selectivity1, fractional_selectivity1, absolute_selectivity2,
            fractional_selectivity2, absolute_selectivity3
        ]

        expected_selectivity = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=2.0)
        self.assertEqual(expected_selectivity, _combine_filter_selectivities(selectivities))

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_get_equals_filter_selectivity(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        classname = 'Animal'

        def empty_lookup_counts(classname):
            """Dummy function to pass into get_filter_selectivity."""
            return 100

        params = dict()

        # If we '='-filter on a property that isn't an index return a fractional selectivity of 1.
        filter_on_nonindex = FilterInfo(
            fields=('description',), op_name='=', args=('$description',)
        )
        selectivity = _get_filter_selectivity(
            schema_graph, empty_lookup_counts, filter_on_nonindex, params, classname
        )
        expected_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0)
        self.assertEqual(expected_selectivity, selectivity)

        # If we '='-filter on a property that's non-uniquely
        # indexed return a fractional selectivity of 1.
        nonunique_filter = FilterInfo(fields=('birthday',), op_name='=', args=('$birthday',))
        selectivity = _get_filter_selectivity(
            schema_graph, empty_lookup_counts, nonunique_filter, params, classname
        )
        expected_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0)
        self.assertEqual(expected_selectivity, selectivity)

        # If we '='-filter on a property that is uniquely indexed, expect exactly 1 result.
        unique_filter = FilterInfo(fields=('uuid',), op_name='=', args=('$uuid',))
        selectivity = _get_filter_selectivity(
            schema_graph, empty_lookup_counts, unique_filter, params, classname
        )
        expected_selectivity = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=1.0)
        self.assertEqual(expected_selectivity, selectivity)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_get_in_collection_filter_selectivity(self):
        schema_graph = generate_schema_graph(self.orientdb_client)
        classname = 'Animal'

        def empty_lookup_counts(classname):
            """Dummy function to pass into get_filter_selectivity."""
            return 100

        nonunique_filter = FilterInfo(fields=('birthday',), op_name='in_collection',
                                      args=('$birthday_collection',))
        nonunique_params = {
            'birthday_collection': [
                date(2017, 3, 22),
                date(1999, 12, 31),
            ]
        }
        # If we use an in_collection-filter on a property that is not uniquely indexed
        # return a fractional selectivity of 1.
        selectivity = _get_filter_selectivity(
            schema_graph, empty_lookup_counts, nonunique_filter, nonunique_params, classname
        )
        expected_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0)
        self.assertEqual(expected_selectivity, selectivity)

        in_collection_filter = FilterInfo(fields=('uuid',), op_name='in_collection',
                                          args=('$uuid_collection',))
        unique_params = {
            'uuid_collection': [
                '00000000-0000-0000-0000-000000000000',
                '00000000-0000-0000-0000-000000000001',
                '00000000-0000-0000-0000-000000000002'
            ]
        }
        # If we use an in_collection-filter on a property that is uniquely indexed, expect as many
        # results as there are elements in the collection.
        selectivity = _get_filter_selectivity(
            schema_graph, empty_lookup_counts, in_collection_filter, unique_params, classname
        )
        expected_selectivity = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=3.0)
        self.assertEqual(expected_selectivity, selectivity)


# pylint: enable=no-member
