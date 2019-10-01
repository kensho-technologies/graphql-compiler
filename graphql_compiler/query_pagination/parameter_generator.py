# Copyright 2019-present Kensho Technologies, LLC.


def generate_parameters_for_parameterized_query(
    schema_info, parameterized_pagination_queries, num_pages
):
    """Generate parameters for the given parameterized pagination queries.

    Args:
        schema_info: QueryPlanningSchemaInfo
        parameterized_pagination_queries: ParameterizedPaginationQueries namedtuple, parameterized
                                          queries for which parameters are being generated.
        num_pages: int, number of pages to split the query into.

    Returns:
        two dicts:
            - dict, parameters with which to execute the page query. The next page query's
              parameters are generated such that only a page of the original query's result data is
              produced when executed.
            - dict, parameters with which to execute the remainder query. The remainder query
              parameters are generated such that they produce the remainder of the original query's
              result data when executed.
    """
    raise NotImplementedError()
