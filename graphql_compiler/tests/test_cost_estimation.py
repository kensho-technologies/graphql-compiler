# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from . import test_input_data
from ..cost_estimation.cardinality_estimator import estimate_query_result_cardinality
from .test_helpers import generate_schema_graph


def create_lookup_counts(count_data):
    """Create lookup_counts function for use in estimating query cost."""
    def lookup_counts(name):
        """Lookup the total number of instances and subinstances of a given class name."""
        return count_data[name]
    return lookup_counts


# The following TestCase class uses the 'graph_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class CostEstimationTests(unittest.TestCase):
    """Test the cost estimation module using standard input data when possible."""

    #TODO: These tests can be sped up by having an existing test SchemaGraph object.
    @pytest.mark.usefixtures('graph_client')
    def test_root_count(self):
        """"Ensure we correctly estimate the cardinality of the query root."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_traverse(self):
        """Ensure we correctly estimate cardinality over edges."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_fragment(self):
        """Ensure we correctly adjust for fragments."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_complex_traverse(self):
        """Ensure we correctly handle more complicated arrangements of traversals."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_optional(self):
        """Ensure we handle an optional edge correctly."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_optional_and_traverse(self):
        """Ensure traversals inside optionals are handled correctly."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_fold(self):
        """Ensure we handle an folded edge correctly."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_fold_and_traverse(self):
        """Ensure traversals inside folds are handled correctly."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_recurse(self):
        """Ensure we handle recursion correctly."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_recurse_and_traverse(self):
        """Ensure we handle traversals inside recurses correctly."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_single_filter(self):
        """Ensure we handle filters correctly."""
        # TODO: eventually, we should ensure other fractional/absolute selectivies work.
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_traverse_and_filter(self):
        """Ensure we filters work correctly below the root location."""
        schema_graph = generate_schema_graph(self.graph_client)
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

    @pytest.mark.usefixtures('graph_client')
    def test_multiple_filters(self):
        """Ensure we handle multiple filters correctly."""
        schema_graph = generate_schema_graph(self.graph_client)
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
