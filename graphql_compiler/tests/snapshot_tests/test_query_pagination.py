# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.language.ast import Argument, Directive, ListValue, Name, StringValue
import pytest

from graphql_compiler.schema import FilterDirective

from ...ast_manipulation import safe_parse_graphql
from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import QueryStringWithParameters, paginate_query
from ...query_pagination.filter_modifications import (
    FilterModification, get_modifications_needed_to_vertices_for_paging,
    get_vertices_for_pagination
)
from ...query_pagination.modify_query import (
    PaginationFilter, ParameterizedPaginationQueries, generate_parameterized_queries
)
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

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_modification_generation(self):
        """Ensure FilterModifications are found correctly."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        test_data = '''{
            Animal {
                out_Animal_BornAt{
                    name @output(out_name: "birth_event")
                }
            }
        }'''
        parameters = {}

        test_ast = safe_parse_graphql(test_data)
        statistics = LocalStatistics({})

        pagination_vertices = get_vertices_for_pagination(statistics, test_ast)
        pagination_vertex = pagination_vertices[0]

        expected_modifications = [FilterModification(
            pagination_vertex,
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
        )]

        # In this query, the paginator has to add a '>=' filter and '<' filter.
        received_modifications = get_modifications_needed_to_vertices_for_paging(
            schema_graph, statistics, test_ast, parameters, pagination_vertices
        )

        self.assertEqual(expected_modifications, received_modifications)

        test_data = '''{
            Animal {
                uuid @filter(op_name: ">=", value: ["$uuid_filter_lower_bound"])
                     @filter(op_name: "<", value: ["$uuid_filter_upper_bound"])
                out_Animal_BornAt {
                    name @output(out_name: "birth_event")
                }
            }
        }'''
        parameters = {
            'uuid_filter_lower_bound': '80000000-0000-0000-0000-000000000000',
            'uuid_filter_upper_bound': 'c0000000-0000-0000-0000-000000000000',
        }

        test_ast = safe_parse_graphql(test_data)
        statistics = LocalStatistics({})

        pagination_vertices = get_vertices_for_pagination(statistics, test_ast)
        pagination_vertex = pagination_vertices[0]

        expected_modifications = [FilterModification(
            pagination_vertex,
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
                                StringValue(value=u'$uuid_filter_upper_bound'),
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
                                StringValue(value=u'$uuid_filter_lower_bound'),
                            ],
                        ),
                    ),
                ],
            ),
        )]

        # This query already has '>=' and '<' filters defined on uuid which we expect the
        # paginator to use instead of creating a new filters.
        received_modifications = get_modifications_needed_to_vertices_for_paging(
            schema_graph, statistics, test_ast, parameters, pagination_vertices
        )

        self.assertEqual(expected_modifications, received_modifications)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_modify_query(self):
        """Ensure the query is modified correctly when given FilterModification namedtuples."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        test_data = '''{
            Animal {
                out_Animal_BornAt {
                    name @output(out_name: "birth_event")
                }
            }
        }'''
        parameters = {}

        test_ast = safe_parse_graphql(test_data)
        statistics = LocalStatistics({})

        pagination_vertices = get_vertices_for_pagination(statistics, test_ast)
        pagination_vertex = pagination_vertices[0]

        filter_modifications = [FilterModification(
            pagination_vertex,
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
        )]

        expected_parameterized_queries = ParameterizedPaginationQueries(
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

        received_parameterized_queries = generate_parameterized_queries(
            schema_graph, statistics, test_ast, parameters, filter_modifications
        )

        self.assertEqual(expected_parameterized_queries, received_parameterized_queries)
