# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql.language.printer import print_ast

from graphql_compiler.ast_manipulation import safe_parse_graphql
from graphql_compiler.cost_estimation.cardinality_estimator import estimate_number_of_pages
from graphql_compiler.query_pagination.parameter_generator import (
    generate_parameters_for_parameterized_query
)
from graphql_compiler.query_pagination.query_parameterizer import generate_parameterized_queries


QueryStringWithParameters = namedtuple(
    'QueryStringWithParameters',
    (
        'query_string',     # str, describing a GraphQL query.
        'parameters',       # dict, parameters for executing the given query.
    ),
)

ASTWithParameters = namedtuple(
    'ASTWithParameters',
    (
        'query_ast',        # Document, AST describing a GraphQL query.
        'parameters',       # dict, parameters for executing the given query.
    ),
)


def _split_into_next_page_query_and_continuation_query(
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

    parameterized_queries = generate_parameterized_queries(
        schema_graph, statistics, query_ast, parameters
    )

    pagination_parameters = generate_parameters_for_parameterized_query(
        schema_graph, statistics, parameterized_queries, num_pages
    )

    next_page_ast_with_parameters = ASTWithParameters(
        parameterized_queries.next_page_query,
        pagination_parameters.next_page_parameters,
    )
    continuation_ast_with_parameters = ASTWithParameters(
        parameterized_queries.continuation_query,
        pagination_parameters.continuation_parameters,
    )

    return next_page_ast_with_parameters, continuation_ast_with_parameters


def paginate_query_ast(schema_graph, statistics, query_ast, parameters, page_size):
    """Generates a query fetching a page of results and the cursor for a GraphQL query AST.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, AST of the GraphQL query that is being paginated.
        parameters: dict, parameters with which query will be estimated.
        page_size: int, describes the desired number of result rows per page.

    Returns:
        tuple containing two elements:
            - ASTWithParameters namedtuple, describing a query expected to return roughly a page
              of result data of the original query.
            - ASTWithParameters namedtuple or None, describing a query that returns the rest of the
              result data of the original query. If the original query is expected to return only a
              page or less of results, then this element will have value None.

    Raises:
        ValueError if page_size is below 1.
    """
    if page_size < 1:
        raise ValueError(
            u'Could not page query {} with page size lower than 1: {}'.format(query_ast, page_size)
        )

    # Initially, assume the query does not need to be paged i.e. will return one page of results.
    result_queries = (
        ASTWithParameters(query_ast, parameters),
        None,
    )

    # HACK(vlad): Since the current cost estimator expects GraphQL queries given as a string, we
    #             print the given AST and provide that to the cost estimator.
    graphql_query_string = print_ast(query_ast)
    num_pages = estimate_number_of_pages(
        schema_graph, statistics, graphql_query_string, parameters, page_size
    )
    if num_pages > 1:
        result_queries = _split_into_next_page_query_and_continuation_query(
            schema_graph, statistics, query_ast, parameters, num_pages
        )

    return result_queries


def paginate_query(schema_graph, statistics, query_string, parameters, page_size):
    """Generates a query fetching a page of results and the cursor for a GraphQL query string.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_string: str, valid GraphQL query to be paginated.
        parameters: dict, parameters with which query will be estimated.
        page_size: int, describes the desired number of result rows per page.

    Returns:
        tuple containing queries for going over the original query in a paginated fashion:
            - QueryStringWithParameters namedtuple, query expected to return roughly a page of
              result data of the original query.
            - QueryStringWithParameters namedtuple or None, query returning the rest of the result
              data of the original query. If the original query is expected to return only a page or
              less of results, then this element will have value None.

    Raises:
        ValueError if page_size is below 1.
    """
    query_ast = safe_parse_graphql(query_string)

    next_page_ast_with_parameters, continuation_ast_with_parameters = paginate_query_ast(
        schema_graph, statistics, query_ast, parameters, page_size
    )

    next_page_query_with_parameters = QueryStringWithParameters(
        print_ast(next_page_ast_with_parameters.query_ast),
        next_page_ast_with_parameters.parameters,
    )
    continuation_query_with_parameters = QueryStringWithParameters(
        print_ast(continuation_ast_with_parameters.query_ast),
        continuation_ast_with_parameters.parameters,
    )

    return next_page_query_with_parameters, continuation_query_with_parameters
