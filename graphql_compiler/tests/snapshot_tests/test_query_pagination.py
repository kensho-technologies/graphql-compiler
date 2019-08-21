# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import QueryStringWithParameters, paginate_query
from ..test_helpers import compare_graphql, generate_schema_graph


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class QueryPaginationTests(unittest.TestCase):
    """Test the query pagination module."""

    # TODO: These tests can be sped up by having an existing test SchemaGraph object.
    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_basic_pagination(self):
        """"Ensure a basic pagination query is handled correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
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

        received_next_page_query, received_remainder_query = paginate_query(
            schema_graph, statistics, test_data, parameters, 1
        )

        expected_next_page_query = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: "<", value: ["$_paged_upper_param_on_Animal_uuid"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '_paged_upper_param_on_Animal_uuid': '40000000-0000-0000-0000-000000000000',
            },
        )
        expected_remainder_query = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$_paged_lower_param_on_Animal_uuid"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '_paged_lower_param_on_Animal_uuid': '40000000-0000-0000-0000-000000000000',
            },
        )

        compare_graphql(
            self, expected_next_page_query.query_string, received_next_page_query.query_string
        )
        self.assertEqual(expected_next_page_query.parameters, received_next_page_query.parameters)

        compare_graphql(
            self, expected_remainder_query.query_string, received_remainder_query.query_string
        )
        self.assertEqual(expected_remainder_query.parameters, received_remainder_query.parameters)
