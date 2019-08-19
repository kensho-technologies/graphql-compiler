# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple


RESERVED_PARAMETER_PREFIX = '_paged_'

ParameterizedPaginationQuery = namedtuple(
    'ParameterizedPaginationQuery',
    (
        'next_page_query',          # Document, AST of query that will return the next page of
                                    # results when hydrated with pagination parameters.
        'continuation_query',       # Document, AST of query that will return the remainder of
                                    # results when hydrated with pagination parameters.
        'pagination_filters',       # List[PaginationFilter], filters usable for pagination.
        'user_parameters',          # dict, parameters that the user has defined for other filters.
    ),
)

PaginationFilter = namedtuple(
    'PaginationFilter',
    (
        'vertex_field',                 # str, vertex class to which the property field belongs to.
        'property_field',               # str, name of the property field filtering is done over.
        'next_page_query_filter',       # Directive, filter usable for pagination in the
                                        # next page query.
        'continuation_query_filter',    # Directive, filter usable for pagination in the
                                        # continuation query.
        'related_filters',              # List[Directive], filter directives that are on the same
                                        # vertex and property field.
    ),
)


def generate_parameterized_queries(schema_graph, statistics, query_ast, parameters):
    """Generate two parameterized queries that can be hydrated to paginate over the original query.

    In order to paginate arbitrary GraphQL queries, additional filters may need to be added to be
    able to limit the number of results in the original query. This function creates two new queries
    with additional filters stored as PaginationFilters with which the query result size can be
    controlled.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, query that is being paginated.
        parameters: dict, list of parameters for the given query.

    Returns:
        ParameterizedPaginationQuery namedtuple, describing two new query ASTs that have additional
        filters stored as PaginationFilters with which the query result size can be controlled.
        Note that these filters are returned parameterized i.e. values for the filters' parameters
        have yet to be generated. Additionally, a dict containing user-defined parameters is stored.
        Since this function may modify the user parameters to ensure better pagination, the
        user_parameters dict may differ from the one provided as an argument to this function.
    """
    raise NotImplementedError()
