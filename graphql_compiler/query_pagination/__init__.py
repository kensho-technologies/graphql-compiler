# Copyright 2019-present Kensho Technologies, LLC.
from typing import Tuple

from ..cost_estimation.analysis import QueryPlanningAnalysis, analyze_query_string
from ..global_utils import ASTWithParameters, QueryStringWithParameters
from ..schema.schema_info import QueryPlanningSchemaInfo
from .pagination_planning import MissingClassCount, PaginationAdvisory, get_pagination_plan
from .parameter_generator import generate_parameters_for_vertex_partition
from .query_parameterizer import generate_parameterized_queries
from .typedefs import PageAndRemainder


def _estimate_number_of_pages(
    query: QueryStringWithParameters, result_size: float, page_size: int
) -> int:
    """Estimate how many pages of results we should generate to meet the desired result size.

    Args:
        query: query string and parameters being analyzed for pagination
        result_size: estimated result size of running the supplied query as-is
        page_size: desired page size of the final paginated query

    Returns:
        int, estimated number of pages of the desired size into which the supplied query
        should be split up
    """
    if page_size < 1:
        raise AssertionError(
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
    """
    if page_size < 1:
        raise AssertionError(
            "Could not page query {} with page size lower than 1: {}".format(
                query_analysis.query_string_with_parameters, page_size
            )
        )

    # Initially, assume the query does not need to be paged i.e. will return one page of results.
    page_query = query_analysis.ast_with_parameters
    remainder_queries: Tuple[ASTWithParameters, ...] = tuple()
    advisories: Tuple[PaginationAdvisory, ...] = tuple()

    # See if we can and should split the query
    num_pages = 1
    if query_analysis.classes_with_missing_counts:
        advisories += tuple(
            MissingClassCount(class_name)
            for class_name in query_analysis.classes_with_missing_counts
        )
    else:
        result_size = query_analysis.cardinality_estimate
        num_pages = _estimate_number_of_pages(
            query_analysis.query_string_with_parameters, result_size, page_size
        )

    # Split the query if we can and should
    if num_pages > 1:
        pagination_plan, advisories = get_pagination_plan(query_analysis, num_pages)
        if len(pagination_plan.vertex_partitions) == 0:
            pass
        elif len(pagination_plan.vertex_partitions) == 1:
            plan_vertex_partition = pagination_plan.vertex_partitions[0]
            parameter_generator = generate_parameters_for_vertex_partition(
                query_analysis,
                plan_vertex_partition,
            )

            sentinel = object()
            first_param = next(parameter_generator, sentinel)
            if first_param is not sentinel:
                page_query, remainder_query = generate_parameterized_queries(
                    query_analysis,
                    plan_vertex_partition,
                    first_param,
                )
                remainder_queries = (remainder_query,)
        else:
            raise NotImplementedError(
                "We only support pagination plans with one vertex partition. "
                "Received {}".format(pagination_plan)
            )

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

    page_query_with_parameters = QueryStringWithParameters.from_ast_with_parameters(
        ast_page_and_remainder.one_page
    )
    remainder_queries_with_parameters = tuple(
        QueryStringWithParameters.from_ast_with_parameters(ast_with_params)
        for ast_with_params in ast_page_and_remainder.remainder
    )
    text_page_and_remainder = PageAndRemainder[QueryStringWithParameters](
        query, page_size, page_query_with_parameters, remainder_queries_with_parameters
    )

    return text_page_and_remainder, advisories
