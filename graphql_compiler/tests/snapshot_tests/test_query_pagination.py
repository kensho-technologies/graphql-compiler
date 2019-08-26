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
        elif (expected is None) != (received is None):
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
        page_size = 1

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
        # This query generates 2 pages, so the remainder after 2 pages is None.
        expected_second_remainder = None

        received_first_next_page, received_first_remainder = (
            paginate_query(schema_graph, statistics, test_data, parameters, page_size)
        )

        # Then we page the remainder we've received, to ensure paginating more than once is handled
        # correctly.
        received_second_next_page, received_second_remainder = (
            paginate_query(
                schema_graph, statistics,
                received_first_remainder.query_string,
                received_first_remainder.parameters, page_size
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

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_pagination_with_filters_on_uuid(self):
        """"Ensure pagination handles already-existing filters over uuid correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        test_data = '''{
            Animal {
            	uuid @filter(op_name: ">=", value: ["$uuid_filter"])
                name @output(out_name: "animal")
            }
        }'''
        parameters = {
        	'uuid_filter': '80000000-0000-0000-0000-000000000000',
        }
        page_size = 2

        count_data = {
            'Animal': 8,
        }

        statistics = LocalStatistics(count_data)

        expected_first_next_page = QueryStringWithParameters(
            '''{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_lower_bound_0"])
                    	 @filter(op_name: "<", value: ["$__paged_upper_bound_0"])
                    name @output(out_name: "animal")
                }
            }''',
            {
                '__paged_lower_bound_0': '80000000-0000-0000-0000-000000000000',
                '__paged_upper_bound_0': 'c0000000-0000-0000-0000-000000000000',
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
                '__paged_lower_bound_0': 'c0000000-0000-0000-0000-000000000000',
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
                '__paged_lower_bound_0': 'c0000000-0000-0000-0000-000000000000',
            },
        )
        # This query generates 2 pages, so the remainder after 2 pages is None.
        expected_second_remainder = None

        # Since the user has added '>=' filters on uuid, the paginator can just use it instead,
        # making sure that the parameter name is changed to reflect that the filter is used for
        # pagination.
        received_first_next_page, received_first_remainder = (
            paginate_query(schema_graph, statistics, test_data, parameters, page_size)
        )

        # Then we page the remainder we've received, to ensure paginating more than once is handled
        # correctly.
        received_second_next_page, received_second_remainder = (
            paginate_query(
                schema_graph, statistics,
                received_first_remainder.query_string,
                received_first_remainder.parameters, page_size
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
