# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple


RESERVED_PARAMETER_PREFIX = '__paged_'

# FilterModification namedtuples document pagination filters that will be added or modified in the
# given query. They contain all the information of a PaginationFilter, but are designed for storing
# the information of what needs to be modified in a given query to obtain the next page query and
# the remainder query.
FilterModification = namedtuple(
    'FilterModification',
    (
        'vertex',                   # Document, AST of the vertex instance in the query having its
                                    # filters modified.
        'property_field',           # str, name of the property field being filtered.
        'next_page_query_filter',   # Directive, '<' filter directive that will be used to generate
                                    # the next page query.
        'remainder_query_filter',   # Directive, '>=' filter directive that will be used to generate
                                    # the remainder query. This filter may
    )
)


def get_modifications_for_pagination(schema_graph, statistics, query_ast, parameters):
    """Return FilterModification namedtuples for parameterizing and paging the given query.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, AST of the GraphQL query that will be split.
        parameters: dict, parameters with which query will be estimated.

    Returns:
        List[FilterModification], changes to be done to the query to allow pagination over the given
        query.
    """
    raise NotImplementedError()
