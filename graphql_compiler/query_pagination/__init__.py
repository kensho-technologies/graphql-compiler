# Copyright 2019-present Kensho Technologies, LLC.
from typing import Tuple

from graphql.language.printer import print_ast

from ..cost_estimation.analysis import QueryPlanningAnalysis, analyze_query_string
from ..global_utils import ASTWithParameters, QueryStringWithParameters
from ..schema.schema_info import QueryPlanningSchemaInfo
from .pagination_planning import PaginationAdvisory, get_pagination_plan
from .query_splitter import split_into_page_query_and_remainder_query
from .typedefs import PageAndRemainder


def _estimate_number_of_pages(query: ASTWithParameters, result_size: float, page_size: int) -> int:
    """Estimate how many pages of results we should generate to meet the desired result size.

    Args:
        query: ASTWithParameters
        result_size: The estimated result size of a query
        page_size: The desired page size of a query

    Returns:
        int, estimated number of pages if the query were executed.

    Raises:
        ValueError if page_size is below 1.
    """
    if page_size < 1:
        raise ValueError(
            f"Could not estimate number of pages for query {query}"
            f" with page size lower than 1: {page_size}"
        )

    if result_size < 0.0:
        raise AssertionError(
            f"Received negative estimate {result_size} for cardinality of query {query}"
        )

    # Since using a // b returns the fraction rounded down, we instead use (a + b - 1) // b, which
    # returns the fraction value rounded up, which is the desired functionality.
    num_pages = int((result_size + page_size - 1) // page_size)
    if num_pages == 0:
        num_pages = 1

    return num_pages


def paginate_query_ast(
    query_analysis: QueryPlanningAnalysis, page_size: int
) -> Tuple[PageAndRemainder[ASTWithParameters], Tuple[PaginationAdvisory, ...]]:
    """Generate a query fetching a page of results and the remainder queries for a query AST.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        query_analysis: the query with any query analysis needed for pagination
        page_size: int, describes the desired number of result rows per page.

    Returns:
        tuple containing two elements:
            - page_and_remainder such that:
              - page_and_remainder.whole_query == query
              - page_and_remainder.page_size == page_size
            - Tuple of PaginationAdvisory objects that communicate what can be done to improve
              pagination

    Raises:
        ValueError if page_size is below 1.
    """
    if page_size < 1:
        raise ValueError(
            "Could not page query {} with page size lower than 1: {}".format(
                query_analysis.query_string_with_parameters, page_size
            )
        )

    # Initially, assume the query does not need to be paged i.e. will return one page of results.
    page_query = query_analysis.ast_with_parameters
    remainder_queries: Tuple[ASTWithParameters, ...] = tuple()
    advisories: Tuple[PaginationAdvisory, ...] = tuple()

    result_size = query_analysis.cardinality_estimate
    num_pages = _estimate_number_of_pages(
        query_analysis.query_string_with_parameters, result_size, page_size
    )
    if num_pages > 1:
        pagination_plan, advisories = get_pagination_plan(query_analysis, num_pages)
        if pagination_plan.vertex_partitions:
            page_query, remainder_query = split_into_page_query_and_remainder_query(
                query_analysis, pagination_plan
            )
            remainder_queries = (remainder_query,)

    return (
        PageAndRemainder[ASTWithParameters](
            query_analysis.ast_with_parameters, page_size, page_query, remainder_queries
        ),
        advisories,
    )


def paginate_query(
    schema_info: QueryPlanningSchemaInfo, query: QueryStringWithParameters, page_size: int
) -> Tuple[PageAndRemainder[QueryStringWithParameters], Tuple[PaginationAdvisory, ...]]:
    """Generate a query fetching a page of results and the remainder queries for a query string.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query: QueryStringWithParameters
        parameters: dict, parameters with which query will be estimated.
        page_size: int, describes the desired number of result rows per page.

    Returns:
        tuple containing two elements:
            - page_and_remainder such that:
              - page_and_remainder.whole_query == query
              - page_and_remainder.page_size == page_size
            - Tuple of PaginationAdvisory objects that communicate what can be done to improve
              pagination
    """
    query_analysis = analyze_query_string(schema_info, query)
    ast_page_and_remainder, advisories = paginate_query_ast(query_analysis, page_size)

    page_query_with_parameters = QueryStringWithParameters(
        print_ast(ast_page_and_remainder.one_page.query_ast),
        ast_page_and_remainder.one_page.parameters,
    )
    remainder_queries_with_parameters = tuple(
        QueryStringWithParameters(print_ast(query.query_ast), query.parameters)
        for query in ast_page_and_remainder.remainder
    )
    text_page_and_remainder = PageAndRemainder[QueryStringWithParameters](
        query, page_size, page_query_with_parameters, remainder_queries_with_parameters
    )

    return text_page_and_remainder, advisories
