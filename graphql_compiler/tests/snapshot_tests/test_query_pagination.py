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

    def _compare_query_with_parameters_namedtuple(self, expected, received):
        """Compares two given QueryWithParameters namedtuple, raising error if not equal."""
        if expected is None and received is None:
            return True
        elif expected is None != received is None:
            return False

        compare_graphql(
            self, expected.query_string, received.query_string
        )
        self.assertEqual(expected.parameters, received.parameters)


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
            'Animal': 2,
        }

        statistics = LocalStatistics(count_data)

        expected_first_next_page = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: "<", value: ["$__paged_upper_bound_0"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '__paged_upper_bound_0': '80000000-0000-0000-0000-000000000000',
            },
        )
        expected_second_next_page = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_lower_bound_0"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '__paged_lower_bound_0': '80000000-0000-0000-0000-000000000000',
            },
        )
        expected_first_remainder = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_lower_bound_0"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '__paged_lower_bound_0': '80000000-0000-0000-0000-000000000000',
            },
        )
        expected_second_remainder = None        # This query generates 2 pages, so the
                                                # remainder after 2 pages is None.

        received_first_next_page, received_first_remainder = (
            paginate_query(schema_graph, statistics, test_data, parameters, 1)
        )

        # Then we page the remainder we've received, to ensure paginating twice is handled
        # correctly.
        received_second_next_page, received_second_remainder = (
            paginate_query(
                schema_graph, statistics,
                received_first_remainder.query_string,
                received_first_remainder.parameters, 1
            )
        )

        self._compare_query_with_parameters_namedtuple(
            expected_first_next_page, received_first_next_page
        )
        self._compare_query_with_parameters_namedtuple(
            expected_first_remainder, received_first_remainder
        )

        self._compare_query_with_parameters_namedtuple(
            expected_second_next_page, received_second_next_page
        )
        self._compare_query_with_parameters_namedtuple(
            received_second_remainder, expected_second_remainder
        )
