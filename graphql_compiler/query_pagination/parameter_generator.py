# Copyright 2019-present Kensho Technologies, LLC.
import bisect
import itertools
from typing import Any, Dict, Iterator, cast

from graphql import DocumentNode
from graphql.language.printer import print_ast

from ..compiler.compiler_frontend import graphql_to_ir
from ..compiler.helpers import Location
from ..cost_estimation.filter_selectivity_utils import get_integer_interval_for_filters_on_field
from ..cost_estimation.helpers import is_uuid4_type
from ..cost_estimation.int_value_conversion import (
    MAX_UUID_INT,
    MIN_UUID_INT,
    convert_int_to_field_value,
)
from ..cost_estimation.interval import Interval, intersect_int_intervals, measure_int_interval
from ..schema.schema_info import QueryPlanningSchemaInfo
from .pagination_planning import VertexPartitionPlan


def _sum_partition(number: int, num_splits: int) -> Iterator[int]:
    """Represent an integer as a sum of N almost equal integers, sorted in descending order.

    Example: _sum_partition(5, 3) = [2, 2, 1]

    Args:
        number: The number to be represented as a sum
        num_splits: The desired length of the output

    Retutns:
        generator of num_splits values that add up to the number. The values are descending,
        and the maximum difference between values is 1.
    """
    lower = number // num_splits
    num_high = number - lower * num_splits
    num_low = num_splits - num_high
    return itertools.accumulate(
        itertools.chain(
            itertools.repeat(lower + 1, num_high), itertools.repeat(lower, num_low - 1),
        )
    )


def _deduplicate_sorted_generator(generator: Iterator[Any]) -> Iterator[Any]:
    """Return a generator that skips repeated values in the given sorted generator."""
    prev = object()
    for i in generator:
        if i != prev:
            yield i
        prev = i


def _convert_int_interval_to_field_value_interval(
    schema_info: QueryPlanningSchemaInfo, vertex_type: str, field: str, interval: Interval[int]
) -> Interval[Any]:
    """Convert the endpoints of an interval. See int_value_conversion for the conversion spec."""
    lower_bound = None
    upper_bound = None
    if interval.lower_bound is not None:
        lower_bound = convert_int_to_field_value(
            schema_info, vertex_type, field, interval.lower_bound
        )
    if interval.upper_bound is not None:
        upper_bound = convert_int_to_field_value(
            schema_info, vertex_type, field, interval.upper_bound
        )
    return Interval(lower_bound, upper_bound)


def _compute_parameters_for_uuid_field(
    schema_info: QueryPlanningSchemaInfo,
    integer_interval: Interval[int],
    vertex_partition: VertexPartitionPlan,
    vertex_type: str,
    field: str,
) -> Iterator[Any]:
    """Return a generator of parameter values for the vertex partition at a uuid field.

    See generate_parameters_for_vertex_partition for more details.

    Args:
        schema_info: contains statistics and relevant schema information
        integer_interval: the interval of values for the field, constrained by existing filters
                          in the query, in int form. See the int_value_conversion module for
                          the definition of an int-equivalent of a uuid.
        vertex_partition: the pagination plan we are working on
        vertex_type: the name of the vertex type where the pagination field is
        field: the name of the pagination field

    Returns:
        generator of field values. See generate_parameters_for_vertex_partition for more details.
    """
    uuid_int_universe = Interval(MIN_UUID_INT, MAX_UUID_INT)
    integer_interval = intersect_int_intervals(integer_interval, uuid_int_universe)

    int_value_splits = (
        cast(int, integer_interval.lower_bound)
        + int(
            float(
                cast(int, measure_int_interval(integer_interval))
                * i
                // vertex_partition.number_of_splits
            )
        )
        for i in range(1, vertex_partition.number_of_splits)
    )
    return (
        convert_int_to_field_value(schema_info, vertex_type, field, int_value)
        for int_value in int_value_splits
    )


def _compute_parameters_for_non_uuid_field(
    schema_info: QueryPlanningSchemaInfo,
    field_value_interval: Interval[Any],
    vertex_partition: VertexPartitionPlan,
    vertex_type: str,
    field: str,
) -> Iterator[Any]:
    """Return a generator of parameter values for the vertex partition at a non-uuid field.

    See generate_parameters_for_vertex_partition for more details.

    Args:
        schema_info: contains statistics and relevant schema information
        field_value_interval: the interval of values for the field, constrained by existing filters
                              in the query
        vertex_partition: the pagination plan we are working on
        vertex_type: the name of the vertex type where the pagination field is
        field: the name of the pagination field

    Returns:
        generator of field values. See generate_parameters_for_vertex_partition for more details.
    """
    quantiles = schema_info.statistics.get_field_quantiles(vertex_type, field)
    if quantiles is None or len(quantiles) <= vertex_partition.number_of_splits:
        raise AssertionError(
            "Invalid vertex partition {}. Not enough quantile data.".format(vertex_partition)
        )

    # Since we can't be sure the minimum observed value is the
    # actual minimum value, we treat values less than it as part
    # of the first quantile. That's why we drop the minimum and
    # maximum observed values from the quantile list.
    proper_quantiles = quantiles[1:-1]

    # Get the relevant quantiles (ones inside the field_value_interval)
    # TODO(bojanserafimov): It's possible that the planner thought there are enough quantiles
    #                       to paginate, but didn't notice that there are filters that restrict
    #                       the range of values into a range for which there are not enough
    #                       quantiles. In this case, the pagination plan is not fully realized.
    #                       The generated query will have fewer pages than the plan specified.
    #
    #                       One solution is to push all the pagination capacity logic
    #                       into the cost estimator, and make it return along with the
    #                       cardinality estimate some other metadata that the paginator would
    #                       rely on.
    min_quantile = 0
    max_quantile = len(proper_quantiles)
    if field_value_interval.lower_bound is not None:
        min_quantile = bisect.bisect_left(proper_quantiles, field_value_interval.lower_bound)
    if field_value_interval.upper_bound is not None:
        max_quantile = bisect.bisect_left(proper_quantiles, field_value_interval.upper_bound)
    relevant_quantiles = proper_quantiles[min_quantile:max_quantile]

    # TODO(bojanserafimov): We deduplicate the results to make sure we don't generate pages
    #                       that are known to be empty. This can cause the number of generated
    #                       pages to be less than the desired number of pages.
    return _deduplicate_sorted_generator(
        relevant_quantiles[index]
        for index in _sum_partition(len(relevant_quantiles) + 1, vertex_partition.number_of_splits)
    )


def generate_parameters_for_vertex_partition(
    schema_info: QueryPlanningSchemaInfo,
    query_ast: DocumentNode,
    parameters: Dict[str, Any],
    vertex_partition: VertexPartitionPlan,
) -> Iterator[Any]:
    """Return a generator of parameter values that realize the vertex partition.

    Composability guarantee: The values returned can be used to create
    vertex_partition.number_of_splits pages, or just the first value can be used to separate
    the first page from the remainder. Splitting the remainder recursively should produce
    the same results.

    Args:
        schema_info: contains statistics and relevant schema information
        query_ast: the query for which we are generating parameters
        parameters: parameters for the query
        vertex_partition: the pagination plan we are working on

    Returns:
        Returns a generator of (vertex_partition.number_of_splits - 1) values that split the
        values at vertex_partition.pagination_field into vertex_partition.number_of_splits
        almost equal chunks.
        HACK(bojanserafimov): In some cases the number values returned is less than
                              (vertex_partition.number_of_splits - 1). This happens when the
                              pagination planner generates an impossible plan. This is obviously
                              not desirable. This flaw is not visible to the end user, but shold
                              be fixed ASAP. Fix coming in PR #738.
    """
    pagination_field = vertex_partition.pagination_field
    if vertex_partition.number_of_splits < 2:
        raise AssertionError("Invalid number of splits {}".format(vertex_partition))

    # Find the FilterInfos on the pagination field
    graphql_query_string = print_ast(query_ast)
    query_metadata = graphql_to_ir(
        schema_info.schema,
        graphql_query_string,
        type_equivalence_hints=schema_info.type_equivalence_hints,
    ).query_metadata_table
    query_location = Location(vertex_partition.query_path)
    vertex_type = query_metadata.get_location_info(query_location).type.name
    filter_infos = query_metadata.get_filter_infos(query_location)
    filters_on_field = [
        filter_info for filter_info in filter_infos if filter_info.fields == (pagination_field,)
    ]

    # Get the value interval currently imposed by existing filters
    integer_interval = get_integer_interval_for_filters_on_field(
        schema_info, filters_on_field, vertex_type, pagination_field, parameters
    )
    field_value_interval = _convert_int_interval_to_field_value_interval(
        schema_info, vertex_type, pagination_field, integer_interval
    )

    # Compute parameters
    if is_uuid4_type(schema_info, vertex_type, pagination_field):
        return _compute_parameters_for_uuid_field(
            schema_info, integer_interval, vertex_partition, vertex_type, pagination_field
        )
    else:
        return _compute_parameters_for_non_uuid_field(
            schema_info, field_value_interval, vertex_partition, vertex_type, pagination_field
        )
