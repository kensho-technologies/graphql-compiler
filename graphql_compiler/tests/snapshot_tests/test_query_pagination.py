# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ...ast_manipulation import safe_parse_graphql
from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import paginate_query
from ..test_helpers import generate_schema_graph


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class QueryPaginationTests(unittest.TestCase):
    """Test the cost estimation module using standard input data when possible."""

    # TODO: These tests can be sped up by having an existing test SchemaGraph object.
    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_basic_pagination(self):
        """"Ensure we correctly estimate the cardinality of the query root."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        test_data = '''{
            Animal {
                uuid @filter(op_name: ">", value: ["$keva_brat"])
                name @output(out_name: "animal") @filter(op_name: ">", value: ["$keva_brat"])
            }
        }'''
        test_ast = safe_parse_graphql(test_data)
        parameters = {'keva_brat': 'keva_kolku_dojde_sat'}

        count_data = {
            'Animal': 4,
        }

        statistics = LocalStatistics(count_data)

        paginated_queries = paginate_query(
            schema_graph, statistics, test_ast, parameters, 1
        )

        expected_query_list = [
            (
                '''{
                    Animal {
                        uuid @filter(op_name: "<", value: ["$_paged_upper_param_on_Animal"])
                        name @output(out_name: "animal")
                    }
                }''',
                {
                    '_paged_upper_param_on_Animal': '40000000-0000-0000-0000-000000000000',
                }
            ),
            (
                '''{
                    Animal {
                        uuid @filter(op_name: ">=", value: ["$_paged_lower_param_on_Animal"])
                        name @output(out_name: "animal")
                    }
                }''',
                {
                    '_paged_lower_param_on_Animal': '40000000-0000-0000-0000-000000000000',
                }
            )
        ]

        self.assertEqual(expected_query_list, paginated_queries)
