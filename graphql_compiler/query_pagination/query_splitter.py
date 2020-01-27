# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from .parameter_generator import (
    generate_parameters_for_vertex_partition
)
from .query_parameterizer import generate_parameterized_queries
from .pagination_planning import get_pagination_plan


ASTWithParameters = namedtuple(
    'ASTWithParameters',
    (
        'query_ast',        # Document, AST describing a GraphQL query.
        'parameters',       # dict, parameters for executing the given query.
    ),
)


def split_into_page_query_and_remainder_query(schema_info, query_ast, parameters, num_pages):
    """Split a query into two equivalent queries, one of which will return roughly a page of data.
    First, two parameterized queries are generated that contain filters usable for pagination i.e.
    filters with which the number of results can be constrained. Parameters for these filters are
    then generated such that one of the new queries will return roughly a page of results, while the
    other query will generate the rest of the results. This ensures that the two new queries' result
    data is equivalent to the original query's result data.
    Args:
        schema_info: QueryPlanningSchemaInfo
        query_ast: Document, AST of the GraphQL query that will be split.
        parameters: dict, parameters with which query will be estimated.
        num_pages: int, number of pages to split the query into.
    Returns:
        tuple of (ASTWithParameters namedtuple, ASTWithParameters namedtuple), describing two
        queries: the first query when executed will return roughly a page of results of the original
        query; the second query will return the rest of the results of the original query. The union
        of the two queries' result data is equivalent to the given query and parameter's result
        data. There are no guarantees on the order of the result rows for the two generated queries.
    """
    if num_pages <= 1:
        raise AssertionError(u'Could not split query {} into pagination queries for the next page'
                             u' of results, as the number of pages {} must be greater than 1: {}'
                             .format(query_ast, num_pages, parameters))

    pagination_plan, advisories = get_pagination_plan(schema_info, query_ast, num_pages)
    if len(pagination_plan.vertex_partitions) != 1:
        raise NotImplementedError(u'We only support pagination plans with one vertex partition. '
                                  u'Reveived {}'.format(pagination_plan))

    parameter_generator = generate_parameters_for_vertex_partition(
        schema_info, query_ast, parameters, pagination_plan.vertex_partitions[0])
    first_param = next(parameter_generator)

    page_query, remainder_query, param_name = generate_parameterized_queries(
        schema_info, query_ast, parameters, pagination_plan.vertex_partitions[0])

    page_parameters = dict(parameters)
    page_parameters.update({
        param_name: first_param
    })
    remainder_parameters = dict(parameters)
    remainder_parameters.update({
        param_name: first_param
    })

    # Function is complete, but not tested.
    raise NotImplementedError(
        ASTWithParameters(page_query, page_parameters),
        ASTWithParameters(remainder_query, remainder_parameters),
    )
