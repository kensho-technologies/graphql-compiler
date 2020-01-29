# Copyright 2019-present Kensho Technologies, LLC.
from typing import Tuple

from graphql.language.printer import print_ast

from ..ast_manipulation import safe_parse_graphql
from ..cost_estimation.cardinality_estimator import estimate_number_of_pages
from ..global_utils import ASTWithParameters, QueryStringWithParameters, canonicalize_value
from ..schema.schema_info import QueryPlanningSchemaInfo
from .pagination_planning import PaginationAdvisory
from .query_splitter import split_into_page_query_and_remainder_query


def paginate_query_ast(
    schema_info: QueryPlanningSchemaInfo, query: ASTWithParameters, page_size: int
) -> Tuple[ASTWithParameters, Tuple[ASTWithParameters, ...], Tuple[PaginationAdvisory, ...]]:
    """Generate a query fetching a page of results and the remainder query for a query AST.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query: ASTWithParameters
        page_size: int, describes the desired number of result rows per page.

    Returns:
        tuple containing two elements:
            - ASTWithParameters namedtuple, describing a query expected to return roughly a page
              of result data of the original query.
            - Tuple of ASTWithParameters, describing queries that return the rest of the result
              data of the original query. If the original query is expected to return only a page or
              less of results, then this element will be an empty tuple.
            - Tuple of PaginationAdvisories that communicate what can be done to improve pagination

    Raises:
        ValueError if page_size is below 1.
    """
    if page_size < 1:
        raise ValueError(
            u"Could not page query {} with page size lower than 1: {}".format(query, page_size)
        )

    # Initially, assume the query does not need to be paged i.e. will return one page of results.
    page_query = query
    remainder_queries: Tuple[ASTWithParameters, ...] = tuple()
    advisories: Tuple[PaginationAdvisory, ...] = tuple()

    # HACK(vlad): Since the current cost estimator expects GraphQL queries given as a string, we
    #             print the given AST and provide that to the cost estimator.
    graphql_query_string = print_ast(query.query_ast)
    num_pages = estimate_number_of_pages(
        schema_info, graphql_query_string, query.parameters, page_size
    )
    if num_pages > 1:
        page_query, remainder_query, advisories = split_into_page_query_and_remainder_query(
            schema_info, query, num_pages
        )
        remainder_queries = (remainder_query,)

    return page_query, remainder_queries, advisories


def paginate_query(
    schema_info: QueryPlanningSchemaInfo, query: QueryStringWithParameters, page_size: int
) -> Tuple[
    QueryStringWithParameters, Tuple[QueryStringWithParameters, ...], Tuple[PaginationAdvisory, ...]
]:
    """Generate a query fetching a page of results and the remainder query for a query string.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query: QueryStringWithParameters
        parameters: dict, parameters with which query will be estimated.
        page_size: int, describes the desired number of result rows per page.

    Returns:
        tuple containing queries for going over the original query in a paginated fashion:
            - QueryStringWithParameters namedtuple, query expected to return roughly a page of
              result data of the original query.
            - Tuple of QueryStringWithParameters, describing queries that return the rest of the
              result data of the original query. If the original query is expected to return only
              a page or less of results, then this element will be an empty tuple.
            - Tuple of PaginationAdvisories that communicate what can be done to improve pagination
    """
    query_ast = safe_parse_graphql(query.query_string)
    canonicalized_parameters = {
        key: canonicalize_value(value) for key, value in query.parameters.items()
    }

    next_page_ast_with_parameters, remainder_ast_with_parameters, advisories = paginate_query_ast(
        schema_info, ASTWithParameters(query_ast, canonicalized_parameters), page_size
    )

    page_query_with_parameters = QueryStringWithParameters(
        print_ast(next_page_ast_with_parameters.query_ast),
        next_page_ast_with_parameters.parameters,
    )
    remainder_queries_with_parameters = tuple(
        QueryStringWithParameters(print_ast(query.query_ast), query.parameters)
        for query in remainder_ast_with_parameters
    )

    return page_query_with_parameters, remainder_queries_with_parameters, advisories
