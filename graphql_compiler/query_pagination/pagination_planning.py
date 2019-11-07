# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from ..ast_manipulation import get_only_query_definition, get_only_selection_from_ast
from ..exceptions import GraphQLError


# The intent to split the query at a certain vertex into a certain number of pages.
VertexPartition = namedtuple(
    'VertexPartition', (
        'query_path',  # List[field name : str] leading to the field to be filtered
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
    query_path = [pagination_node.name.value]

    # Find the field to use on the pagination node, or return None if there are no viable ones
    field_name = schema_info.pagination_keys.get(pagination_node.name.value, None)
    if field_name is None:
        return None
    query_path.append(field_name)
    return PaginationPlan([
        VertexPartition(query_path, number_of_pages)
    ])
