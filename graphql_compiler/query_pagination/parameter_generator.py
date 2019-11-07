# Copyright 2019-present Kensho Technologies, LLC.


def generate_parameters_for_vertex_partition(schema_info, query_ast, parameters, vertex_partition):
    """ """
    vertex_type = TODO_get_from_(vertex_partition.query_path)
    pagination_field = schema_info.pagination_keys.get(vertex_type)

    # See what are the min and max values currently imposed by existing filters.
    # TODO(bojanserafimov): Assuming no existing filters for now.
    min_value = None
    max_value = None

    if is_uuid_field:
        pass  # XXX subdivide evenly
    elif is_int_field:
        quantiles = schema_info.pagination_keys.statistics.get_field_quantiles(
        # XXX use quantiles
    else:
        raise AssertionError()
