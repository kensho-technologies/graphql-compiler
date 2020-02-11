# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABC
from dataclasses import dataclass, field
from typing import Optional, Tuple

from graphql import DocumentNode

from ..global_utils import PropertyPath
from ..ast_manipulation import get_only_query_definition, get_only_selection_from_ast
from ..cost_estimation.analysis import QueryPlanningAnalysis
from ..cost_estimation.helpers import is_uuid4_type
from ..cost_estimation.int_value_conversion import field_supports_range_reasoning
from ..exceptions import GraphQLError
from ..schema.schema_info import QueryPlanningSchemaInfo


@dataclass
class PaginationAdvisory(ABC):
    message: str = field(init=False)


@dataclass
class PaginationFieldNotSpecified(PaginationAdvisory):
    vertex_name: str

    def __post_init__(self):
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

    def __post_init__(self):
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
    analysis: QueryPlanningAnalysis,
    query_ast: DocumentNode,
    number_of_pages: int,
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
        query_ast: GraphQL AST node describing the query being paginated
        number_of_pages: desired number of pages to attempt to paginate the query into

    Returns:
        tuple including a best-effort pagination plan together with a tuple of advisories describing
        any ways in which the pagination plan was less than ideal and how to resolve them
    """
    definition_ast = get_only_query_definition(query_ast, GraphQLError)

    if number_of_pages <= 0:
        raise AssertionError(
            u"The number of pages should be at least 1, but {} were requested.".format(
                number_of_pages
            )
        )
    elif number_of_pages == 1:
        return PaginationPlan(tuple()), tuple()

    # Select the root node as the only vertex to paginate on.
    # TODO(bojanserafimov): Make a better pagination plan. Selecting the root is not
    #                       a good idea if:
    #                       - The root node has no pagination_key
    #                       - The root node has a unique index
    #                       - There are only a few different vertices at the root
    #                         that this query select.
    #                       - The class count of the root is lower than the page count
    root_node = get_only_selection_from_ast(definition_ast, GraphQLError).name.value
    pagination_node = root_node
    pagination_field = analysis.schema_info.pagination_keys.get(pagination_node)
    if pagination_field is None:
        return None, (PaginationFieldNotSpecified(pagination_node),)

    vertex_path = (root_node,)
    property_path = PropertyPath(vertex_path, pagination_field)
    capacity = analysis.pagination_capacities[property_path]
    number_of_splits = int(min(capacity, number_of_pages))  # TODO int cast sketchy

    if number_of_splits <= 1:
        return PaginationPlan(tuple()), tuple()
    vertex_partition_plan = VertexPartitionPlan(vertex_path, pagination_field, number_of_splits)
    return PaginationPlan((vertex_partition_plan,)), tuple()  # TODO is this right?
