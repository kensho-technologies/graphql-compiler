# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.language.ast import Argument, Directive, ListValue, Name, StringValue
import pytest

from graphql_compiler.schema import FilterDirective

from ...ast_manipulation import safe_parse_graphql
from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import paginate_query
from ...query_pagination.modify_query import PaginationFilter, ParameterizedPaginationQueries
from ...query_pagination.parameter_generator import generate_parameters_for_parameterized_query
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

    def test_parameter_generation(self):
        """"""
        schema_graph = generate_schema_graph(self.orientdb_client)
        parameterized_queries = ParameterizedPaginationQueries(
            safe_parse_graphql('''{
                Animal {
                    uuid @filter(op_name: "<", value: ["$__paged_upper_bound_0"])
                    out_Animal_BornAt {
                        name @output(out_name: "birth_event")
                    }
                }
            }'''),
            safe_parse_graphql('''{
                Animal {
                    uuid @filter(op_name: ">=", value: ["$__paged_lower_bound_0"])
                    out_Animal_BornAt {
                        name @output(out_name: "birth_event")
                    }
                }
            }'''),
            [PaginationFilter(
                'Animal',
                'uuid',
                Directive(
                    name=Name(value=FilterDirective.name),
                    arguments=[
                        Argument(
                            name=Name(value='op_name'),
                            value=StringValue(value='<'),
                        ),
                        Argument(
                            name=Name(value='value'),
                            value=ListValue(
                                values=[
                                    StringValue(value=u'$__paged_upper_bound_0'),
                                ],
                            ),
                        ),
                    ],
                ),
                Directive(
                    name=Name(value=FilterDirective.name),
                    arguments=[
                        Argument(
                            name=Name(value='op_name'),
                            value=StringValue(value='>='),
                        ),
                        Argument(
                            name=Name(value='value'),
                            value=ListValue(
                                values=[
                                    StringValue(value=u'$__paged_lower_bound_0'),
                                ],
                            ),
                        ),
                    ],
                ),
                []      # already_existing_filters is empty, as there are no filters there.
            )],
            dict()      # the user parameters dict is empty, as no parameters were provided.
        )

        parameters = {}
        page_size = 2

        count_data = {
            'Animal': 8,
        }
        # Since there are 8 Animals, and we want a page size of 2, the query is going to be split
        # into quarters of equal size.
        num_pages = 4

        statistics = LocalStatistics(count_data)

        expected_next_page_parameters = {
            '__paged_upper_bound_0': '40000000-0000-0000-0000-000000000000',
        }
        expected_remainder_parameters = {
            '__paged_lower_bound_0': '40000000-0000-0000-0000-000000000000',
        }

        # Since the query is supposed to be split into four smaller queries, the parameter generator
        # sets a filter that only allows a quarter of all UUIDs to pass through it.
        received_next_page_parameters, received_remainder_parameters = (
            generate_parameters_for_parameterized_query(
                schema_graph, statistics, parameterized_queries, num_pages
            )
        )

        self.assertEqual(expected_next_page_parameters, received_next_page_parameters)
        self.assertEqual(expected_remainder_parameters, received_remainder_parameters)
