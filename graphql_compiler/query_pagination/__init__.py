# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql.language.printer import print_ast

from graphql_compiler.ast_manipulation import safe_parse_graphql
from graphql_compiler.cost_estimation.cardinality_estimator import estimate_number_of_pages
from graphql_compiler.query_pagination.query_splitter import (
    ASTWithParameters, split_into_page_query_and_remainder_query
)


QueryStringWithParameters = namedtuple(
    'QueryStringWithParameters',
    (
        'query_string',     # str, describing a GraphQL query.
        'parameters',       # dict, parameters for executing the given query.
    ),
)


def paginate_query_ast(schema_info, query_ast, parameters, page_size):
    """Generate a query fetching a page of results and the remainder query for a query AST.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        schema_info: QueryPlanningSchemaInfo
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
    num_pages = estimate_number_of_pages(schema_info, graphql_query_string, parameters, page_size)
    if num_pages > 1:
        result_queries = split_into_page_query_and_remainder_query(
            schema_info, query_ast, parameters, num_pages)

    return result_queries


def paginate_query(schema_info, query_string, parameters, page_size):
    """Generate a query fetching a page of results and the remainder query for a query string.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        schema_info: QueryPlanningSchemaInfo
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_string: str, valid GraphQL query to be paginated.
        parameters: dict, parameters with which query will be estimated.
        page_size: int, describes the desired number of result rows per page.

    Returns:
        tuple containing queries for going over the original query in a paginated fashion:
            - QueryStringWithParameters namedtuple, query expected to return roughly a page of
              result data of the original query.
            - QueryStringWithParameters namedtuple or None. If the given query was estimated to
              return more than a page of results, this element is a QueryStringWithParameters
              namedtuple describing a query for the rest of the result data. Otherwise, this element
              is None.
    """
    query_ast = safe_parse_graphql(query_string)

    next_page_ast_with_parameters, remainder_ast_with_parameters = paginate_query_ast(
        schema_info, query_ast, parameters, page_size)

    page_query_with_parameters = QueryStringWithParameters(
        print_ast(next_page_ast_with_parameters.query_ast),
        next_page_ast_with_parameters.parameters,
    )
    remainder_query_with_parameters = None
    if remainder_ast_with_parameters is not None:
        remainder_query_with_parameters = QueryStringWithParameters(
            print_ast(remainder_ast_with_parameters.query_ast),
            remainder_ast_with_parameters.parameters,
        )

    return page_query_with_parameters, remainder_query_with_parameters
