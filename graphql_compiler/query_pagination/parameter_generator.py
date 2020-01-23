# Copyright 2019-present Kensho Technologies, LLC.
import itertools
import bisect

from graphql.language.printer import print_ast

from ..compiler.compiler_frontend import graphql_to_ir
from ..compiler.helpers import Location
from ..cost_estimation.interval import Interval, measure_int_interval, intersect_int_intervals
from ..cost_estimation.helpers import is_int_field_type, is_uuid4_type
from ..cost_estimation.filter_selectivity_utils import get_integer_interval_for_filters_on_field
from ..cost_estimation.int_value_conversion import convert_field_value_to_int, convert_int_to_field_value, MIN_UUID_INT, MAX_UUID_INT, field_supports_range_reasoning


def _get_query_path_endpoint_type(schema, query_path):
    # TODO needs more care with:
    # - non-null types
    # - type coercions
    current_type = schema.get_type('RootSchemaQuery')
    for selection in query_path:
        current_type = current_type.fields[selection].type.of_type
    return current_type


def _sum_partition(number, num_splits):
    """Represent an integer as a sum of N almost equal integers, sorted in descending order.

    Example: _sum_partition(5, 3) = [2, 2, 1]
    """
    lower = number // num_splits
    num_high = number - lower * num_splits
    num_low = num_splits - num_high
    return itertools.accumulate(itertools.chain(
        itertools.repeat(lower + 1, num_high),
        itertools.repeat(lower, num_low - 1),
    ))


def _deduplicate_sorted_generator(gen):
    prev = object()
    for i in gen:
        if i != prev:
            yield i
        prev = i


def _convert_int_interval_to_field_value_interval(schema_info, vertex_type, field, interval):
    lower_bound = None
    upper_bound = None
    if interval.lower_bound is not None:
        lower_bound = convert_int_to_field_value(
            schema_info, vertex_type, field, interval.lower_bound)
    if interval.upper_bound is not None:
        upper_bound = convert_int_to_field_value(
            schema_info, vertex_type, field, interval.upper_bound)
    return Interval(lower_bound, upper_bound)


def _compute_parameters_for_uuid_field(
    schema_info, integer_interval, vertex_partition, vertex_type, field
):
    uuid_int_universe = Interval(MIN_UUID_INT, MAX_UUID_INT)
    integer_interval = intersect_int_intervals(integer_interval, uuid_int_universe)

    int_value_splits = (
        integer_interval.lower_bound + int(
            float(measure_int_interval(integer_interval) * i / vertex_partition.number_of_splits))
        for i in range(1, vertex_partition.number_of_splits)
    )
    return (
        convert_int_to_field_value(schema_info, vertex_type, field, int_value)
        for int_value in int_value_splits
    )


def _compute_parameters_for_non_uuid_field(
    schema_info, field_value_interval, vertex_partition, vertex_type, field
):
    quantiles = schema_info.statistics.get_field_quantiles(vertex_type, field)
    if quantiles is None or len(quantiles) <= vertex_partition.number_of_splits:
        raise AssertionError('Invalid vertex partition {}. Not enough quantile data.'
                             .format(vertex_partition))

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
        proper_quantiles[index]
        for index in _sum_partition(
            len(relevant_quantiles) + 1,
            vertex_partition.number_of_splits
        )
    )


def generate_parameters_for_vertex_partition(schema_info, query_ast, parameters, vertex_partition):
    """Return a generator of parameter values that realize the vertex partition.

    This function returns a generator of (vertex_partition.number_of_splits - 1) values that
    split the values at vertex_partition.pagination_field into vertex_partition.number_of_splits
    almost equal chunks.

    Composability guarantee: The values returned can be used to create
    vertex_partition.number_of_splits pages, or just the first value can be used to separate
    the first page from the remainder. Splitting the remainder recursively should produce
    the same results.
    """
    vertex_type = _get_query_path_endpoint_type(schema_info.schema, vertex_partition.query_path).name
    pagination_field = vertex_partition.pagination_field
    if vertex_partition.number_of_splits < 2:
        raise AssertionError('Invalid number of splits {}'.format(vertex_partition))

    # Find the FilterInfos on the pagination field
    graphql_query_string = print_ast(query_ast)
    query_metadata = graphql_to_ir(
        schema_info.schema,
        graphql_query_string,
        type_equivalence_hints=schema_info.type_equivalence_hints
    ).query_metadata_table
    filter_infos = query_metadata.get_filter_infos(Location(tuple(vertex_partition.query_path)))
    filters_on_field = [
        filter_info
        for filter_info in filter_infos
        if filter_info.fields == (pagination_field,)
    ]

    # Get the value interval currently imposed by existing filters
    integer_interval = get_integer_interval_for_filters_on_field(
        schema_info, filters_on_field, vertex_type, pagination_field, parameters)
    field_value_interval = _convert_int_interval_to_field_value_interval(
        schema_info, vertex_type, pagination_field, integer_interval)

    # Compute parameters
    if is_uuid4_type(schema_info, vertex_type, pagination_field):
        return _compute_parameters_for_uuid_field(
            schema_info, integer_interval, vertex_partition, vertex_type, pagination_field)
    else:
        return _compute_parameters_for_non_uuid_field(
            schema_info, field_value_interval, vertex_partition, vertex_type, pagination_field)


def generate_parameters_for_parameterized_query(
    schema_info, parameterized_pagination_queries, num_pages
):
    """Generate parameters for the given parameterized pagination queries.

    Args:
        schema_info: QueryPlanningSchemaInfo
        parameterized_pagination_queries: ParameterizedPaginationQueries namedtuple, parameterized
                                          queries for which parameters are being generated.
        num_pages: int, number of pages to split the query into.

    Returns:
        two dicts:
            - dict, parameters with which to execute the page query. The next page query's
              parameters are generated such that only a page of the original query's result data is
              produced when executed.
            - dict, parameters with which to execute the remainder query. The remainder query
              parameters are generated such that they produce the remainder of the original query's
              result data when executed.
    """
    # TODO(bojanserafimov): Replace this method with generate_parameters_for_vertex_partition. It's
    #                       api is simpler (no dependence on parameterization), and it uses the
    #                       VertexPartitionPlan.
    raise NotImplementedError()
