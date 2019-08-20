# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql.language.printer import print_ast

from graphql_compiler.cost_estimation.cardinality_estimator import estimate_number_of_pages
from graphql_compiler.query_pagination.parameter_generator import (
    hydrate_parameters_of_parameterized_query
)
from graphql_compiler.query_pagination.query_parameterizer import generate_parameterized_queries


PaginationQueries = namedtuple(
    'PaginationQueries',
    (
        'next_page_query',          # Document, AST for the query that along with
                                    # next_page_parameters is expected to return the next page of
                                    # page of results of the original query.
        'next_page_parameters',     # dict, parameters with which to execute the next page query.
        'continuation_query',       # Document or None, AST for the query that along with
                                    # continuation_parameters returns the rest of the results of the
                                    # original query, or None if the original query was not split
                                    # into two queries.
        'continuation_parameters',  # dict or None, parameters with which to execute the
                                    # continuation query, or None if the continuation query was not
                                    # generated.
    )
)


def split_into_next_page_query_and_continuation_query(
    schema_graph, statistics, query_ast, parameters, num_pages
):
    """Split a query into two equivalent queries, one of which will return roughly a page of data.

    First, two parameterized queries are generated that contain filters usable for pagination i.e.
    filters with which the number of results can be constrained. Parameters for these filters are
    then generated such that one of the new queries will return roughly a page of results, while the
    other query will generate the rest of the results. This ensures that the two new queries' result
    data is equivalent to the original query's result data.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, AST of the GraphQL query that will be split.
        parameters: dict, parameters with which query will be estimated.
        num_pages: int, number of pages to split the query into.

    Returns:
        PaginationQueries namedtuple, describing two queries: the first is described in
        next_page_query and next_page_parameters, which when executed will return roughly a page of
        results of the original query; while the second query is described in continuation_query and
        continuation_parameters, which will return the rest of the results of the original query.
        The union of the two queries' result data is equivalent to the given query and parameter's
        result data. There are no guarantees on the order of the result rows for the two generated
        queries.
    """
    if num_pages <= 1:
        raise AssertionError(u'Could not split query {} into pagination queries for the next page'
                             u' of results, as the number of pages {} must be greater than 1: {}'
                             .format(query_ast, num_pages, parameters))

    parameterized_queries = generate_parameterized_queries(
        schema_graph, statistics, query_ast, parameters
    )

    hydrated_parameters = hydrate_parameters_of_parameterized_query(
        schema_graph, statistics, parameterized_queries, num_pages
    )

    result_pagination = PaginationQueries(
        parameterized_queries.next_page_query,
        hydrated_parameters.next_page_parameters,
        parameterized_queries.continuation_query,
        hydrated_parameters.continuation_parameterst,
    )

    return result_pagination


def paginate_query(schema_graph, statistics, query_ast, parameters, page_size):
    """Return two query ASTs usable for pagination whose union is equivalent to the given query.

    The first query when executed will return approximately page_size results, while the second
    query will return the rest of the results. In case the given query is estimated to return less
    than a page of data, the query will not be split.
    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results to be within two orders of magnitude of the estimate.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, AST of the GraphQL query that is being paginated.
        parameters: dict, parameters with which query will be estimated.
        page_size: int, describes the desired number of result rows per page.

    Returns:
        PaginationQueries namedtuple, describing one or two queries that paginate over the original
        query, containing:
            - next_page_query and next_page_parameters describe a query that will return roughly a
              page of results for the original query.
            - continuation_query and continuation_parameters describe a query that will return the
              rest of the results of the original query. If the original query is expected to return
              only a page or less of results, then continuation_query and continuation_parameters
              will have a value of None.

    Raises:
        ValueError if page_size is below 1.
    """
    if page_size < 1:
        raise ValueError(
            u'Could not page GraphQL query {} with page size {}.'.format(query_ast, page_size)
        )

    # Initially, assume the query does not need to be paged i.e. will return one page of results.
    result_queries = PaginationQueries(
        query_ast,
        parameters,
        None,
        None,
    )

    # HACK(vlad): Since the current cost estimator expects GraphQL queries given as a string, we
    #             print the given AST and provide that to the cost estimator.
    graphql_query_string = print_ast(query_ast)
    num_pages = estimate_number_of_pages(
        schema_graph, statistics, graphql_query_string, parameters, page_size
    )
    if num_pages > 1:
        result_queries = split_into_next_page_query_and_continuation_query(
            schema_graph, statistics, query_ast, parameters, num_pages
        )

    return result_queries
