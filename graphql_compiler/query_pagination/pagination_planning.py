# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABC
from dataclasses import dataclass, field
from typing import Optional, Tuple

from graphql import DocumentNode

from ..ast_manipulation import get_only_query_definition, get_only_selection_from_ast
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


def get_best_vertex_partition_plan(
    schema_info: QueryPlanningSchemaInfo, pagination_node: str, number_of_pages: int
) -> Tuple[Optional[VertexPartitionPlan], Tuple[PaginationAdvisory, ...]]:
    """Get the best available VertexPartitionPlan on this node or None if no plan exists."""
    pagination_field = schema_info.pagination_keys.get(pagination_node)
    if pagination_field is None:
        return None, (PaginationFieldNotSpecified(pagination_node),)

    # Specifying an unsupported pagination_field is a compiler bug
    if not field_supports_range_reasoning(schema_info, pagination_node, pagination_field):
        vertex_type = schema_info.schema.get_type(pagination_node)
        field_type_name = vertex_type.fields[pagination_field].type.name
        raise AssertionError(
            u"Cannot paginate on {}.{} because pagination on {} is not supported ".format(
                pagination_node, pagination_field, field_type_name
            )
        )

    # Ideally, we paginate into the desired number of pages, and don't advise for any changes.
    # These two variables are updated in the code below if this vertex is not ideal in any way.
    page_capacity = number_of_pages
    advisories: Tuple[PaginationAdvisory, ...] = tuple()
    if is_uuid4_type(schema_info, pagination_node, pagination_field):
        # UUIDs are uniformly distributed, but it is not wise to make more pages than
        # there are values.
        class_count = schema_info.statistics.get_class_count(pagination_node)
        page_capacity = min(page_capacity, class_count)
    else:
        # If the ratio len(quantiles) // number_of_pages is N, then the largest page is
        # expected to be (N + 1) / N times larger than the smallest page. This is because
        # if we assume that quantiles divide the domain into equal chunks, some pages will
        # span over N + 1 chunks, and some will span over N chunks. So if N is 5,
        # (N + 1) / N = 1.2, which is not too bad.
        ideal_min_num_quantiles_per_page = 5
        ideal_quantile_resolution = ideal_min_num_quantiles_per_page * number_of_pages + 1

        quantiles = schema_info.statistics.get_field_quantiles(pagination_node, pagination_field)
        if quantiles is None:
            # If there are no quantiles, we don't paginate. We could try to assume an uniform
            # value distribution and make some pagination plan with more than 1 page, but
            # the cost estimator would need to match the behavior and assume uniform value
            # distribution when estimating the selectivity of range filters.
            page_capacity = 1
        elif len(quantiles) - 1 < number_of_pages:
            # If we have some quantiles but not enough, we generate a page for each chunk
            # of values separated by the quantiles. N quantiles split the domain into N - 1 chunks:
            # the 0% and 100% quantiles capture the min and max values in the domain, and the
            # remaining N - 2 describe the distribution in between.
            page_capacity = len(quantiles) - 1

        # If we have fewer than the ideal number of quantiles, we advise creating more.
        if quantiles is None or len(quantiles) < ideal_quantile_resolution:
            current_quantile_resolution = 0 if quantiles is None else len(quantiles)
            advisories = (
                InsufficientQuantiles(
                    pagination_node,
                    pagination_field,
                    current_quantile_resolution,
                    ideal_quantile_resolution,
                ),
            )

    # Construct and return the plan and advisories.
    if page_capacity <= 1:
        return None, advisories
    plan = VertexPartitionPlan((pagination_node,), pagination_field, page_capacity)
    return plan, advisories


def get_pagination_plan(
    schema_info: QueryPlanningSchemaInfo, query_ast: DocumentNode, number_of_pages: int
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
        schema_info: query planning information, including quantile statistics for pagination
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
    vertex_partition_plan, advisories = get_best_vertex_partition_plan(
        schema_info, pagination_node, number_of_pages
    )

    if vertex_partition_plan is None:
        return PaginationPlan(tuple(),), advisories
    else:
        return PaginationPlan((vertex_partition_plan,)), advisories
