# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple


HydratedParameters = namedtuple(
    'HydratedParameters',
    (
        'next_page_parameters',     # dict, parameters with which to execute the next page
                                    # parameterized query.
        'continuation_parameters',  # dict, parameters with which to execute the parameterized
                                    # continuation query.
    ),
)


def hydrate_parameters_of_parameterized_query(
    schema_graph, statistics, parameterized_pagination_queries, num_pages
):
    """Generate parameters combining the user's parameters and parameters for paging.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        parameterized_pagination_queries: ParameterizedPaginationQueries namedtuple, parameterized
                                          queries whose parameters will be hydrated with pagination
                                          parameters.
        num_pages: int, number of pages to split the query into.

    Returns:
        HydratedParameters namedtuple, containing two dicts with which to execute the next page
        query and the continuation query respectively. The next page query parameters are generated
        such that only a page of result data is generated of the original pagination query, while
        the continuation query parameters generate the rest of the original query's result data.
    """
    raise NotImplementedError()
