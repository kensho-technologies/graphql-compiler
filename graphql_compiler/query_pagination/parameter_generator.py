# Copyright 2019-present Kensho Technologies, LLC.
import itertools
import bisect

from graphql.language.printer import print_ast

from ..compiler.compiler_frontend import graphql_to_ir
from ..compiler.helpers import Location
from ..cost_estimation.helpers import is_int_field_type, is_uuid4_type
from ..cost_estimation.filter_selectivity_utils import get_integer_interval_for_filters_on_field
from ..cost_estimation.int_value_conversion import convert_field_value_to_int, convert_int_to_field_value, MIN_UUID_INT, MAX_UUID_INT, field_supports_range_reasoning


# TODO needs more care
def _get_query_path_endpoint_type(schema, query_path):
    current_type = schema.get_type('RootSchemaQuery')
    for selection in query_path:
        current_type = current_type.fields[selection].type.of_type
    return current_type


def _sum_partition(number, num_splits):
    lower = number // num_splits
    num_high = number - lower * num_splits
    num_low = num_splits - num_high
    return itertools.accumulate(itertools.chain(
        itertools.repeat(lower + 1, num_high),
        itertools.repeat(lower, num_low - 1),
    ))


def generate_parameters_for_vertex_partition(schema_info, query_ast, parameters, vertex_partition):
    """Return a generator"""
    vertex_type = _get_query_path_endpoint_type(schema_info.schema, vertex_partition.query_path)
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

    # See what are the min and max values currently imposed by existing filters.
    integer_interval = get_integer_interval_for_filters_on_field(
        schema_info, filters_on_field, vertex_type.name, pagination_field, parameters)
    min_int = integer_interval.lower_bound
    max_int = integer_interval.upper_bound
    min_value = None
    max_value = None
    if min_int is not None:
        min_value = convert_int_to_field_value(schema_info, vertex_type.name, pagination_field, min_int)
    if max_int is not None:
        max_value = convert_int_to_field_value(schema_info, vertex_type.name, pagination_field, max_int)

    # Compute parameters
    if is_uuid4_type(schema_info, vertex_type.name, pagination_field):
        min_int, max_int = MIN_UUID_INT, MAX_UUID_INT
        if min_value is not None:
            min_int = convert_field_value_to_int(schema_info, vertex_type.name, pagination_field, min_value)
        if max_value is not None:
            max_int = convert_field_value_to_int(schema_info, vertex_type.name, pagination_field, max_value)
        int_value_splits = (
            min_int + int(float(max_int - min_int) * i / vertex_partition.number_of_splits)
            for i in range(1, vertex_partition.number_of_splits)
        )
        return (
            convert_int_to_field_value(schema_info, vertex_type.name, pagination_field, int_value)
            for int_value in int_value_splits
        )
    elif field_supports_range_reasoning(schema_info, vertex_type.name, pagination_field):
        quantiles = schema_info.statistics.get_field_quantiles(
            vertex_type.name, pagination_field)
        quantile_requirement_factor = 1.5  # XXX should be at least 10?
        if quantiles is None or len(quantiles) < quantile_requirement_factor * vertex_partition.number_of_splits:
            raise AssertionError('Invalid vertex partition {}. Not enough quantile data.'
                                 .format(vertex_partition))

        # Since we can't be sure the minimum observed value is the
        # actual minimum value, we treat values less than it as part
        # of the first quantile. That's why we drop the minimum and
        # maximum observed values from the quantile list.
        proper_quantiles = quantiles[1:-1]

        # Discard quantiles below min_value and above max_value
        min_quantile = 0
        max_quantile = len(proper_quantiles)
        if min_value is not None:
            min_quantile = bisect.bisect_left(proper_quantiles, min_value)
        if max_value is not None:
            max_quantile = bisect.bisect_left(proper_quantiles, max_value)
        relevant_quantiles = proper_quantiles[min_quantile:max_quantile]

        return (
            proper_quantiles[index]
            for index in _sum_partition(
                len(relevant_quantiles) + 1,
                vertex_partition.number_of_splits
            )
        )
    else:
        raise AssertionError()
