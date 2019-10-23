# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import QueryStringWithParameters, paginate_query
from ...schema.schema_info import QueryPlanningSchemaInfo
from ...schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
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
        graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(schema_graph)
        pagination_keys = {vertex_name: 'uuid' for vertex_name in schema_graph.vertex_class_names}
        uuid4_fields = {vertex_name: {'uuid'} for vertex_name in schema_graph.vertex_class_names}
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
        schema_info = QueryPlanningSchemaInfo(
            schema=graphql_schema,
            type_equivalence_hints=type_equivalence_hints,
            schema_graph=schema_graph,
            statistics=statistics,
            pagination_keys=pagination_keys,
            uuid4_fields=uuid4_fields)

        # Since query pagination is still a skeleton, we expect a NotImplementedError for this test.
        # Once query pagination is fully implemented, the result of this call should be equal to
        # expected_query_list.
        # pylint: disable=unused-variable
        with self.assertRaises(NotImplementedError):
            paginated_queries = paginate_query(                     # noqa: unused-variable
                schema_info, test_data, parameters, 1
            )

        expected_query_list = (                                     # noqa: unused-variable
            QueryStringWithParameters(
                '''{
                    Animal {
                        uuid @filter(op_name: "<", value: ["$_paged_upper_param_on_Animal_uuid"])
                        name @output(out_name: "animal")
                    }
                }''',
                {
                    '_paged_upper_param_on_Animal_uuid': '40000000-0000-0000-0000-000000000000',
                },
            ),
            QueryStringWithParameters(
                '''{
                    Animal {
                        uuid @filter(op_name: ">=", value: ["$_paged_lower_param_on_Animal_uuid"])
                        name @output(out_name: "animal")
                    }
                }''',
                {
                    '_paged_lower_param_on_Animal_uuid': '40000000-0000-0000-0000-000000000000',
                },
            ),
        )
        # pylint: enable=unused-variable
