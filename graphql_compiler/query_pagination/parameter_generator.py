# Copyright 2019-present Kensho Technologies, LLC.
from ..cost_estimation.helpers import is_int_field_type, is_uuid4_type
from ..cost_estimation.filter_selectivity_utils import convert_uuid_string_to_int, convert_int_to_uuid_string, MIN_UUID_INT, MAX_UUID_INT


# XXX merge plan:
# - copy _convert_int_to_field_value and _convert_field_value_to_int from query-pagination branch
# - implement _get_query_path_endpoint_type properly
# - land to this PR
# - find existing filters on the pagination_key
# - Implement int field paging


def _get_query_path_endpoint_type(schema, query_path):
    current_type = schema.get_type('RootSchemaQuery')
    for selection in query_path:
        current_type = current_type.fields[selection].type.of_type
    return current_type


def generate_parameters_for_vertex_partition(schema_info, query_ast, parameters, vertex_partition):
    """Return a generator"""
    vertex_type = _get_query_path_endpoint_type(schema_info.schema, vertex_partition.query_path)
    pagination_field = schema_info.pagination_keys[vertex_type.name]
    if vertex_partition.number_of_splits < 2:
        raise AssertionError('Invalid number of splits {}'.format(vertex_partition))

    # See what are the min and max values currently imposed by existing filters.
    # TODO(bojanserafimov): Assuming no existing filters for now.
    min_value = None
    max_value = None

    if is_uuid4_type(schema_info, vertex_type.name, pagination_field):
        min_int = convert_uuid_string_to_int(min_value) if min_value else MIN_UUID_INT
        max_int = convert_uuid_string_to_int(max_value) if max_value else MAX_UUID_INT
        int_value_splits = (
            min_int + int(float(max_int - min_int) * i / vertex_partition.number_of_splits)
            for i in range(1, vertex_partition.number_of_splits)
        )
        return (convert_int_to_uuid_string(int_value) for int_value in int_value_splits)
    elif is_int_field_type(schema_info, vertex_type.name, pagination_field):
        quantiles = schema_info.pagination_keys.statistics.get_field_quantiles(
            vertex_type.name, pagination_field)
        if quantiles is None or len(quantiles) < 10 * vertex_partition.number_of_splits:
            raise AssertionError('Invalid vertex partition {}. Not enough quantile data.'
                                 .format(vertex_partitions))
        raise NotImplementedError('Parameter generation for int fields is not implemeneted.')
    else:
        raise AssertionError()


def generate_parameters_for_parameterized_query(schema_info, query, parameters):
    raise NotImplementedError()
