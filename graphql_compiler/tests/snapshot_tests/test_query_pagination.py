# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import paginate_query
from ..test_helpers import generate_schema_graph


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class QueryPaginationTests(unittest.TestCase):
    """Test the query pagination module."""

    # TODO: These tests can be sped up by having an existing test SchemaGraph object.
    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_basic_pagination(self):
        """Ensure a basic pagination query is handled correctly."""
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

        # Since query pagination is still a skeleton, we expect a NotImplementedError for this test.
        # Once query pagination is fully implemented, the result of this call should be equal to
        # expected_query_list.
        # pylint: disable=unused-variable
        with self.assertRaises(NotImplementedError):
            paginated_queries = paginate_query(                     # noqa: unused-variable
                schema_graph, statistics, test_data, parameters, page_size
            )

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_pagination_with_filters_on_uuid(self):
        """Ensure pagination handles already-existing filters over uuid correctly."""
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

        # Since query pagination is still a skeleton, we expect a NotImplementedError for this test.
        # Once query pagination is fully implemented, the result of this call should be equal to
        # expected_query_list.
        # pylint: disable=unused-variable
        with self.assertRaises(NotImplementedError):
            paginated_queries = paginate_query(                     # noqa: unused-variable
                schema_graph, statistics, test_data, parameters, page_size
            )
