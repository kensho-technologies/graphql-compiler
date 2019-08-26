# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple


# ParameterizedPaginationQueries namedtuple describes two query ASTs that have filters for
# pagination added with which the query result size can be controlled.
ParameterizedPaginationQueries = namedtuple(
    'ParameterizedPaginationQueries',
    (
        'next_page_query',          # Document, AST of query that will return the next page of
                                    # results when its parameterized filters have parameter values.

        'remainder_query',          # Document, AST of query that will return the remainder of
                                    # results when its parameterized filters have parameter values.

        'pagination_filters',       # List[PaginationFilter], filters usable for pagination. Note
                                    # that depending on if the filters chosen for pagination are
                                    # user-created or added by pagination, they might not have
                                    # parameter values. These can be generated using the
                                    # parameter_generator module.

        'user_parameters',          # dict, parameters that the user has defined for query filters.
                                    # The parameter values  may have been modified by the query
                                    # paginator for pagination purposes.
    ),
)

# PaginationFilter namedtuples document filters usable for pagination purposes within the larger
# context of a ParameterizedPaginationQueries namedtuple. These filters may either be added by the
# query parameterizer, or filters that the user has added whose parameter values may be modified for
# generating paginated queries.
PaginationFilter = namedtuple(
    'PaginationFilter',
    (
        'vertex_class',                 # str, vertex class to which the property field belongs to.
        'property_field',               # str, name of the property field being filtered.
        'next_page_query_filter',       # Directive, filter directive with '<' operator usable
                                        # for pagination in the next page query.
        'remainder_query_filter',       # Directive, filter directive with '>=' operator usable
                                        # for pagination in the remainder query.
        'related_filters',              # List[Directive], filter directives that are on the same
                                        # vertex and property field as the next page and remainder
                                        # queries' filters.
    ),
)


def generate_parameterized_queries(
    schema_graph, statistics, query_ast, parameters, filter_modifications
):
    """Generate two parameterized queries that can be used to paginate over a given query.

    In order to paginate arbitrary GraphQL queries, additional filters may need to be added to be
    able to limit the number of results in the original query. This function creates two new queries
    with additional filters stored as PaginationFilters with which the query result size can be
    controlled.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, query that is being paginated.
        parameters: dict, list of parameters for the given query.
        filter_modifications: List[FilterModification namedtuple], documenting modifications to be
                              made to the next page query and remainder query's filters.

    Returns:
        ParameterizedPaginationQueries namedtuple.
    """
    raise NotImplementedError()
