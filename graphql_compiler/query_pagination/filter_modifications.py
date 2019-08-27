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
        'vertex',                   # Field, AST of the vertex instance in the query having its
                                    # filters modified.
        'property_field',           # str, name of the property field being filtered.
        'next_page_query_filter',   # Directive, '<' filter directive that will be used to generate
                                    # the next page query.
        'remainder_query_filter',   # Directive, '>=' filter directive that will be used to generate
                                    # the remainder query. This filter may
    )
)


def get_vertices_for_pagination(statistics, query_ast):
    """Return a list of nodes usable for pagination belonging to the given AST node.

    Args:
        statistics: Statistics object.
        query_ast: Document, AST of the GraphQL query that is being paginated.

    Returns:
        List[Field], field instances of vertices belonging to the given query documenting where to
        add pagination filters.
    """
    raise NotImplementedError()


def get_modifications_needed_to_vertices_for_paging(
    schema_graph, statistics, query_ast, parameters, pagination_vertices
):
    """Return FilterModification namedtuples for parameterizing and paging the given query.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, AST of the GraphQL query that will be split.
        parameters: dict, parameters with which query will be estimated.
        pagination_vertices: List[Field], field instances of vertices belonging to the given query
        documenting where to add pagination filters.

    Returns:
        List[FilterModification], changes to be done to the query to allow pagination over the given
        vertices.
    """
    raise NotImplementedError()
