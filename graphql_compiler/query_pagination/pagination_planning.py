# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from ..ast_manipulation import get_only_query_definition, get_only_selection_from_ast
from ..exceptions import GraphQLError


# The intent to split the query at a certain vertex into a certain number of pages.
VertexPartition = namedtuple(
    'VertexPartition', (
        'query_path',  # Tuple[field name : str] leading to the vertex to be split
        'number_of_splits',  # The number of subdivisions intended for this vertex
    )
)


# The intent to split the query with a combination of VertexPartitions
PaginationPlan = namedtuple(
    'PaginationPlan', (
        'vertex_partitions',  # List[VertexPartition]
    )
)


def get_pagination_plan(schema_info, query_ast, number_of_pages):
    """Make a PaginationPlan for the given query and number of desired pages."""
    definition_ast = get_only_query_definition(query_ast, GraphQLError)

    # Select the root node as the only vertex to paginate on.
    # TODO(bojanserafimov): Make a better pagination plan. Selecting the root is not
    #                       a good idea if:
    #                       - The root node has no pagination_key
    #                       - The root node has a unique index
    #                       - There are only a few different vertices at the root
    pagination_node = get_only_selection_from_ast(definition_ast, GraphQLError)

    pagination_field = schema_info.pagination_keys.get(pagination_node.name.value)
    if pagination_field is None:
        return None

    if is_uuid_field:
        pass
    elif is_int_field:
        quantiles = schema_info.pagination_keys.statistics.get_field_quantiles(
            pagination_node, pagination_field)
        if quantiles is None or len(quantiles) < 10 * number_of_pages:
            return None
    else:
        return None

    return PaginationPlan([VertexPartition([pagination_node], number_of_pages)])
