# Copyright 2019-present Kensho Technologies, LLC.
from typing import Tuple

from ..global_utils import ASTWithParameters
from ..schema.schema_info import QueryPlanningSchemaInfo
from .pagination_planning import PaginationAdvisory, get_pagination_plan
from .parameter_generator import generate_parameters_for_vertex_partition
from .query_parameterizer import generate_parameterized_queries


def split_into_page_query_and_remainder_query(
    schema_info: QueryPlanningSchemaInfo, query: ASTWithParameters, num_pages: int
) -> Tuple[ASTWithParameters, ASTWithParameters, Tuple[PaginationAdvisory, ...]]:
    """Split a query into two equivalent queries, one of which will return roughly a page of data.

    First, two parameterized queries are generated that contain filters usable for pagination i.e.
    filters with which the number of results can be constrained. Parameters for these filters are
    then generated such that one of the new queries will return roughly a page of results, while the
    other query will generate the rest of the results. This ensures that the two new queries' result
    data is equivalent to the original query's result data.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query: ASTWithParameters
        num_pages: int, number of pages to split the query into.

    Returns:
        tuple containing three elements:
            - ASTWithParameters, describing a query expected to return roughly a page
              of result data of the original query.
            - ASTWithParameters or None, describing a query that returns the rest of the
              result data of the original query. If the original query is expected to return only a
              page or less of results, then this element will have value None.
            - Tuple of PaginationAdvisories that communicate what can be done to improve pagination
    """
    if num_pages <= 1:
        raise AssertionError(
            u"Could not split query {} into pagination queries for the next page"
            u" of results, as the number of pages {} must be greater than 1: {}".format(
                query.query_ast, num_pages, query.parameters
            )
        )

    # TODO propagate advisories to top-level
    pagination_plan, advisories = get_pagination_plan(schema_info, query.query_ast, num_pages)
    if len(pagination_plan.vertex_partitions) != 1:
        raise NotImplementedError(
            u"We only support pagination plans with one vertex partition. "
            u"Received {}".format(pagination_plan)
        )

    parameter_generator = generate_parameters_for_vertex_partition(
        schema_info, query.query_ast, query.parameters, pagination_plan.vertex_partitions[0]
    )
    first_param = next(parameter_generator)

    page_query, remainder_query = generate_parameterized_queries(
        schema_info, query, pagination_plan.vertex_partitions[0], first_param
    )
    return page_query, remainder_query, advisories
