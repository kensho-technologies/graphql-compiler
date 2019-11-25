# Copyright 2019-present Kensho Technologies, LLC.
import itertools

from ..cost_estimation.helpers import is_int_field_type, is_uuid4_type
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

    # See what are the min and max values currently imposed by existing filters.
    # TODO(bojanserafimov): Assuming no existing filters for now.
    min_value = None
    max_value = None

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
        if quantiles is None or len(quantiles) < 10 * vertex_partition.number_of_splits:
            raise AssertionError('Invalid vertex partition {}. Not enough quantile data.'
                                 .format(vertex_partitions))

        # Since we can't be sure the minimum observed value is the
        # actual minimum value, we treat values less than it as part
        # of the first quantile. That's why we drop the minimum and
        # maximum observed values from the quantile list.
        proper_quantiles = quantiles[1:-1]
        return (
            proper_quantiles[index]
            for index in _sum_partition(len(proper_quantiles) + 1, vertex_partition.number_of_splits)
        )
    else:
        raise AssertionError()
