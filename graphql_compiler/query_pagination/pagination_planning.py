# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from ..ast_manipulation import get_only_query_definition, get_only_selection_from_ast
from ..cost_estimation.helpers import is_int_field_type, is_uuid4_type
from ..cost_estimation.int_value_conversion import field_supports_range_reasoning
from ..exceptions import GraphQLPaginationError, GraphQLError


# The intent to split the query at a certain vertex into a certain number of pages.
VertexPartition = namedtuple(
    'VertexPartition', (
        'query_path',  # Tuple[field name : str] leading to the vertex to be split
        'pagination_field',  # String, field to use for pagination
        'number_of_splits',  # The number of subdivisions intended for this vertex
    )
)


# The intent to split the query with a combination of VertexPartitions
PaginationPlan = namedtuple(
    'PaginationPlan', (
        'vertex_partitions',  # List[VertexPartition]
    )
)


# TODO(bojanserafimov): Make this function return a best effort pagination plan
#                       when a good one is not found instead of returning None.
def try_get_pagination_plan(schema_info, query_ast, number_of_pages, hints=None):
    """Make a PaginationPlan for the given query and number of desired pages if possible."""
    definition_ast = get_only_query_definition(query_ast, GraphQLError)

    if hints is not None:
        raise NotImplementedError()

    # Select the root node as the only vertex to paginate on.
    # TODO(bojanserafimov): Make a better pagination plan. Selecting the root is not
    #                       a good idea if:
    #                       - The root node has no pagination_key
    #                       - The root node has a unique index
    #                       - There are only a few different vertices at the root
    pagination_node = get_only_selection_from_ast(definition_ast, GraphQLError)

    pagination_field = schema_info.pagination_keys.get(pagination_node.name.value)
    if pagination_field is None:
        raise PaginationError(u'Cannot paginate because no pagination field is specified '
                              u'on the query root. The pagination planner is not good '
                              u'enough to consider other vertices.')

    if is_uuid4_type(schema_info, pagination_node.name.value, pagination_field):
        pass
    elif field_supports_range_reasoning(schema_info, pagination_node.name.value, pagination_field):
        quantiles = schema_info.statistics.get_field_quantiles(
            pagination_node.name.value, pagination_field)
        # We make sure there's more than enough quantiles because we don't interpolate.
        if quantiles is None:
            raise GraphQLPaginationError(u'Cannot paginate because no quantiles exist for {}.{}'
                                         .format(pagination_node.name.value, pagination_field))
        quantile_requirement_factor = 1.5  # XXX should be at least 10?
        if len(quantiles) < quantile_requirement_factor * number_of_pages:
            raise GraphQLPaginationError(u'Cannot paginate because there are not enought quantiles '
                                         u'for {}.{}. Found {}, but {} are needed to paginate {} pages'
                                         .format(pagination_node.name.value, pagination_field,
                                                 len(quantiles),
                                                 quantile_requirement_factor * number_of_pages,
                                                 number_of_pages))
    else:
        type_name = schema_info.schema.get_type(
            pagination_node.name.value).fields[pagination_field].type.name
        raise GraphQLPaginationError(u'Cannot paginate on {}.{} because pagination on {} is not supported '
                                     .format(pagination_node.name.value, pagination_field, type_name))

    return PaginationPlan([
        VertexPartition((pagination_node.name.value,), pagination_field, number_of_pages)
    ])
