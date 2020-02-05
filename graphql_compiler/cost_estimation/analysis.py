from .filter_selectivity_utils import get_integer_interval_for_filters_on_field, adjust_counts_for_filters
from ..cost_estimation.interval import Interval, measure_int_interval, intersect_int_intervals
from ..cost_estimation.int_value_conversion import convert_field_value_to_int, convert_int_to_field_value, MIN_UUID_INT, MAX_UUID_INT, field_supports_range_reasoning, is_uuid4_type
from ..schema import is_meta_field


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


def get_field_value_intervals(schema_info, query_metadata, parameters):
    """Map each (query_path, field) tuple to its field value interval or None if not supported."""
    field_value_intervals = {}
    for location, location_info in query_metadata.registered_locations:
        filter_infos = query_metadata.get_filter_infos(location)
        vertex_type_name = location_info.type.name

        # Group filters by field
        single_field_filters = {}
        for filter_info in filter_infos:
            if len(filter_info.fields) == 0:
                raise AssertionError(u"Got filter on 0 fields {} {}".format(filter_info, location_name))
            elif len(filter_info.fields) == 1:
                single_field_filters.setdefault(filter_info.fields[0], []).append(filter_info)
            else:
                pass  # We don't do anything for multi-field filters yet

        # Find field_value_interval for each field
        for field_name, filters_on_field in single_field_filters.items():
            filters_on_field = [
                filter_info
                for filter_info in filter_infos
                if filter_info.fields == (field_name,)
            ]

            integer_interval = get_integer_interval_for_filters_on_field(
                schema_info, filters_on_field, vertex_type_name, field_name, parameters)
            field_value_interval = _convert_int_interval_to_field_value_interval(
                schema_info, vertex_type_name, field_name, integer_interval)

            field_value_intervals[(location.query_path, field_name)] = field_value_interval
    return field_value_intervals


def get_distinct_result_set_estimates(schema_info, query_metadata, parameters):
    """Map each location to its max number of different results expected in the result."""
    distinct_result_set_estimates = {}
    for location, location_info in query_metadata.registered_locations:
        vertex_type_name = location_info.type.name
        filter_infos = query_metadata.get_filter_infos(location)
        class_count = schema_info.statistics.get_class_count(vertex_type_name)
        distinct_result_set_estimates[location.query_path] = adjust_counts_for_filters(
            schema_info, filter_infos, parameters, vertex_type_name, class_count)

    # TODO transfer along many-to-one edges

    return distinct_result_set_estimates



def get_pagination_capacities(schema_info, field_value_intervals, query_metadata, parameters):
    """Get the pagination capacity for each eligible pagination field.

    The pagination capacity of a field is defined as the maximum number of pages we can split
    the query results in by adding filters on this field with some confidence that the pages
    will have similar sizes. This reasoning is local: if a filter in a different location is
    correlated with the values on this field, the generated pages might turn out to have
    wildly different sizes. This problem is somewhat unavoidable.
    """
    pagination_capacities = {}
    for location, location_info in query_metadata.registered_locations:
        vertex_type_name = location_info.type.name

        # TODO Factor in the distinct_result_set_estimates. For instance, if a field has a
        #      unique filter on it, it's pagination capacity is 1.

        for field_name, field in location_info.type.fields.items():
            key = (location.query_path, field_name)
            if not is_meta_field(field_name):
                if is_uuid4_type(schema_info, vertex_type_name, field_name):
                    # TODO multiply by filter selectivity
                    pagination_capacities[key] = schema_info.statistics.get_class_count(vertex_type_name)
                elif field_supports_range_reasoning(schema_info, vertex_type_name, field_name):
                    # TODO write test for this case
                    field_value_interval = field_value_intervals.get(key, Interval(None, None))
                    quantiles = schema_info.statistics.get_field_quantiles(vertex_type_name, field_name)
                    if quantiles is not None:

                        # Since we can't be sure the minimum observed value is the
                        # actual minimum value, we treat values less than it as part
                        # of the first quantile. That's why we drop the minimum and
                        # maximum observed values from the quantile list.
                        proper_quantiles = quantiles[1:-1]

                        # Get the relevant quantiles (ones inside the field_value_interval)
                        min_quantile = 0
                        max_quantile = len(proper_quantiles)
                        if field_value_interval.lower_bound is not None:
                            min_quantile = bisect.bisect_left(proper_quantiles, field_value_interval.lower_bound)
                        if field_value_interval.upper_bound is not None:
                            max_quantile = bisect.bisect_left(proper_quantiles, field_value_interval.upper_bound)
                        relevant_quantiles = proper_quantiles[min_quantile:max_quantile]

                        # TODO take into account duplicate quantile values

                        pagination_capacities[key] = len(relevant_quantiles) + 1

    return pagination_capacities
