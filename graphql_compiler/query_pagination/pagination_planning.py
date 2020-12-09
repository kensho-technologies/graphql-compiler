# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABC
from dataclasses import dataclass, field
from typing import Tuple

from ..ast_manipulation import get_only_query_definition, get_only_selection_from_ast
from ..cost_estimation.analysis import QueryPlanningAnalysis
from ..exceptions import GraphQLError
from ..global_utils import PropertyPath


@dataclass
class PaginationAdvisory(ABC):
    message: str = field(init=False)


@dataclass
class MissingClassCount(PaginationAdvisory):
    class_name: str

    def __post_init__(self) -> None:
        """Initialize a human-readable message."""
        self.message = (
            f"Class count statistics for the vertices and edges mentioned in the query "
            f"are required for pagination. Class {self.class_name} had no counts."
        )


@dataclass
class PaginationFieldNotSpecified(PaginationAdvisory):
    vertex_name: str

    def __post_init__(self) -> None:
        """Initialize a human-readable message."""
        self.message = (
            "Specifying a pagination field for vertex {} in the QueryPlanningSchemaInfo "
            "would have made this vertex eligible for pagination, and enabled a better "
            "pagination plan.".format(self.vertex_name)
        )


@dataclass
class InsufficientQuantiles(PaginationAdvisory):
    vertex_name: str
    field_name: str
    current_resolution: int
    desired_resolution: int

    def __post_init__(self) -> None:
        """Initialize a human-readable message."""
        self.message = (
            "Pagination would have been more successful if more quantiles were provided "
            "for {}.{}. Currently there are {}, ideally there should be {}".format(
                self.vertex_name, self.field_name, self.current_resolution, self.desired_resolution
            )
        )


@dataclass(frozen=True)
class VertexPartitionPlan:
    """Plan to split the query at a certain vertex into a certain number of pages."""

    # field names leading to the vertex to be split
    query_path: Tuple[str, ...]

    # field to use for pagination
    pagination_field: str

    # The number of subdivisions intended for this vertex
    number_of_splits: int


@dataclass(frozen=True)
class PaginationPlan:
    """Plan to split the query with a combination of VertexPartitionPlans."""

    vertex_partitions: Tuple[VertexPartitionPlan, ...]


def get_plan_page_count(plan: PaginationPlan) -> int:
    """Return the number of pages that a PaginationPlan would generate."""
    number_of_pages = 0
    for vertex_partition in plan.vertex_partitions:
        number_of_pages *= vertex_partition.number_of_splits
    return number_of_pages


def get_pagination_plan(
    query_analysis: QueryPlanningAnalysis, number_of_pages: int
) -> Tuple[PaginationPlan, Tuple[PaginationAdvisory, ...]]:
    """Make a best-effort PaginationPlan and advise on how to improve statistics.

    Might paginate to fewer than the desired number of pages if unable to find a more satisfactory
    plan, and may even return plans with only a single page. For example, this can happen when
    the captured statistics are insufficient, or when the planner is not smart enough to find a
    good plan.

    If the issue can be fixed, the return value will also contain a tuple of PaginationAdvisory
    objects that indicate why the desired pagination was not possible. Each PaginationAdvisory
    states the necessary step that may be taken to avoid it in the future.

    Args:
        query_analysis: the query with any query analysis needed for pagination
        number_of_pages: desired number of pages to attempt to paginate the query into

    Returns:
        tuple including a best-effort pagination plan together with a tuple of advisories describing
        any ways in which the pagination plan was less than ideal and how to resolve them
    """
    definition_ast = get_only_query_definition(
        query_analysis.ast_with_parameters.query_ast, GraphQLError
    )

    if number_of_pages <= 0:
        raise AssertionError(
            "The number of pages should be at least 1, but {} were requested.".format(
                number_of_pages
            )
        )
    elif number_of_pages == 1:
        return PaginationPlan(tuple()), tuple()

    # TODO(bojanserafimov): Make a better pagination plan. A non-root vertex might have a
    #                       higher pagination capacity than the root does.
    root_node = get_only_selection_from_ast(definition_ast, GraphQLError).name.value
    pagination_node = root_node

    # If there is a range filter on a field on this vertex that might be correlated with other
    # fields, it's best to paginate on it to prevent empty pages. After applying this rule,
    # we use the order given by schema_info.pagination_keys to resolve ties.
    pagination_keys = query_analysis.schema_info.pagination_keys.get(pagination_node, tuple())
    range_filtered_pagination_keys = [
        key
        for key in pagination_keys
        if PropertyPath((root_node,), key) in query_analysis.field_value_intervals
    ]
    if range_filtered_pagination_keys:
        pagination_field = range_filtered_pagination_keys[0]
    elif pagination_keys:
        pagination_field = pagination_keys[0]
    else:
        return PaginationPlan(tuple()), (PaginationFieldNotSpecified(pagination_node),)

    # Get the pagination capacity
    vertex_path = (root_node,)
    property_path = PropertyPath(vertex_path, pagination_field)
    capacity = query_analysis.pagination_capacities.get(property_path)
    # If the pagination capacity is None, then there must be no quantiles for this property.
    if capacity is None:
        # If we have more quantiles than desired pages, we can create the desired number of pages.
        # However, if we don't have 5 times as much, those pages might differ in size by a factor
        # of 2.
        ideal_min_num_quantiles_per_page = 5
        ideal_quantile_resolution = ideal_min_num_quantiles_per_page * number_of_pages + 1
        return (
            PaginationPlan(tuple()),
            (
                InsufficientQuantiles(
                    pagination_node, pagination_field, 0, ideal_quantile_resolution
                ),
            ),
        )

    # Construct and return plan
    number_of_splits = min(capacity, number_of_pages)
    if number_of_splits <= 1:
        return PaginationPlan(tuple()), tuple()
    vertex_partition_plan = VertexPartitionPlan(vertex_path, pagination_field, number_of_splits)
    return PaginationPlan((vertex_partition_plan,)), tuple()
