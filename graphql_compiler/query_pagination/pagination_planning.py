# Copyright 2019-present Kensho Technologies, LLC.
from typing import List, NamedTuple, Tuple

from graphql import DocumentNode

from ..ast_manipulation import get_only_query_definition, get_only_selection_from_ast
from ..cost_estimation.helpers import is_uuid4_type
from ..cost_estimation.int_value_conversion import field_supports_range_reasoning
from ..exceptions import GraphQLError
from ..schema.schema_info import QueryPlanningSchemaInfo


class PaginationWarning(object):
    def __init__(self, message):
        """Initialize a PaginationWarning with a custom message."""
        self.message = message


class PaginationFieldNotSpecified(PaginationWarning):
    def __init__(self, vertex_name):
        """Initialize a PaginationFieldNotSpecified PaginationWarning."""
        super(PaginationFieldNotSpecified, self).__init__(
            "Pagination field not specified for vertex {}".format(vertex_name)
        )
        self.vertex_name = vertex_name


class NotEnoughQuantiles(PaginationWarning):
    def __init__(self, vertex_name, field_name, current_resolution, desired_resolution):
        """Initialize a NotEnoughQuantiles PaginationWarning."""
        super(NotEnoughQuantiles, self).__init__(
            "Pagination would have been more successful if more quantiles were provided "
            "for {}.{}. Currently there are {}, ideally there should be {}".format(
                vertex_name, field_name, current_resolution, desired_resolution
            )
        )
        self.vertex_name = vertex_name
        self.field_name = field_name
        self.current_resolution = current_resolution
        self.desired_resolution = desired_resolution


class VertexPartition(NamedTuple):
    """Plan to split the query at a certain vertex into a certain number of pages."""

    # field names leading to the vertex to be split
    query_path: Tuple[str, ...]

    # field to use for pagination
    pagination_field: str

    # The number of subdivisions intended for this vertex
    number_of_splits: int


class PaginationPlan(NamedTuple):
    """Plan to split the query with a combination of VertexPartitions."""

    vertex_partitions: Tuple[VertexPartition, ...]


def get_pagination_plan(
    schema_info: QueryPlanningSchemaInfo, query_ast: DocumentNode, number_of_pages: int
) -> Tuple[PaginationPlan, List[PaginationWarning]]:
    """Make a PaginationPlan for the given query and number of desired pages if possible.

    Might paginate to fewer than the desired number of pages if no good pagination plan
    is found. This can happen when there's not enough data, or when the planner is not
    smart enough to find a good plan. In that case it will return along with the result
    a PaginationWarning that indicates why the pagination was not successful.
    """
    definition_ast = get_only_query_definition(query_ast, GraphQLError)

    if number_of_pages <= 0:
        raise AssertionError(
            u"The number of pages should be at least 1: {}".format(number_of_pages)
        )
    elif number_of_pages == 1:
        return PaginationPlan(tuple()), []

    # Select the root node as the only vertex to paginate on.
    # TODO(bojanserafimov): Make a better pagination plan. Selecting the root is not
    #                       a good idea if:
    #                       - The root node has no pagination_key
    #                       - The root node has a unique index
    #                       - There are only a few different vertices at the root
    pagination_node = get_only_selection_from_ast(definition_ast, GraphQLError).name.value

    pagination_field = schema_info.pagination_keys.get(pagination_node)
    if pagination_field is None:
        return PaginationPlan(tuple()), [PaginationFieldNotSpecified(pagination_node)]

    if is_uuid4_type(schema_info, pagination_node, pagination_field):
        return (
            PaginationPlan(
                (VertexPartition((pagination_node,), pagination_field, number_of_pages),)
            ),
            [],
        )
    elif field_supports_range_reasoning(schema_info, pagination_node, pagination_field):
        quantiles = schema_info.statistics.get_field_quantiles(pagination_node, pagination_field)

        # If the ratio len(quantiles) / number_of_pages is N, then the largest page is
        # expected to be (N + 1) / N times larger than the smallest page. So if N is 5,
        # (N + 1) / N = 1.2, which is not too bad.
        ideal_quantile_resolution = 5 * number_of_pages + 1

        if quantiles is None:
            return (
                PaginationPlan(tuple()),
                [
                    NotEnoughQuantiles(
                        pagination_node, pagination_field, 0, ideal_quantile_resolution
                    )
                ],
            )
        elif len(quantiles) - 1 < number_of_pages:
            return (
                PaginationPlan(
                    (VertexPartition((pagination_node,), pagination_field, len(quantiles) - 1),)
                ),
                [
                    NotEnoughQuantiles(
                        pagination_node, pagination_field, len(quantiles), ideal_quantile_resolution
                    )
                ],
            )
        elif len(quantiles) < ideal_quantile_resolution:
            return (
                PaginationPlan(
                    (VertexPartition((pagination_node,), pagination_field, number_of_pages),)
                ),
                [
                    NotEnoughQuantiles(
                        pagination_node, pagination_field, len(quantiles), ideal_quantile_resolution
                    )
                ],
            )
        else:
            return (
                PaginationPlan(
                    (VertexPartition((pagination_node,), pagination_field, number_of_pages),)
                ),
                [],
            )
    else:
        type_name = (
            schema_info.schema.get_type(pagination_node.name.value)
            .fields[pagination_field]
            .type.name
        )
        raise AssertionError(
            u"Cannot paginate on {}.{} because pagination on {} is not supported ".format(
                pagination_node.name.value, pagination_field, type_name
            )
        )
