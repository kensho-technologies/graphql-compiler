# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
import sys

from ..compiler.helpers import get_parameter_name
from .statistics import (
    _get_class_count, _get_vertex_pair_links_count, _get_domain_count, _get_histograms
)


# The Selectivity represents the selectivity of a filter or a set of filters
Selectivity = namedtuple('Selectivity', (
    'kind',     # string, the kind of selectivity, either absolute or fractional
    'value',    # float, either the maximum number of absolute results that pass the filter or the
                # fraction of results that pass the filter
))

ABSOLUTE_SELECTIVITY = 'absolute'
FRACTIONAL_SELECTIVITY = 'fractional'


def _is_absolute(selectivity):
    """Returns True if selectivity has kind absolute."""
    return selectivity.kind == ABSOLUTE_SELECTIVITY


def _is_fractional(selectivity):
    """Returns True if selectivity has kind fractional."""
    return selectivity.kind == FRACTIONAL_SELECTIVITY


def _has_any_absolute(selectivities):
    """Returns True if at least one selectivity has kind absolute."""
    for selectivity in selectivities:
        if _is_absolute(selectivity):
            return True
    return False

def _assert_interval_type_is_number(interval):
    for element in interval:
        element_type = type(element)
        if element_type != IntType and element_type != FloatType:
            raise AssertionError('Provided non-number type as argument {}'.format(element_type))


def _get_intersection_length(interval_a, interval_b):
    """Find the length of intersection between two intervals given as a tuple of ints or floats."""
    intersection_of_bucket_and_interval = min(interval_a[1], interval_b[1]) - 
                                          max(interval_a[0], interval_b[0])
    return intersection_of_bucket_and_interval

def _estimate_count_in_interval_using_bucket(bucket, interval):
    """Estimate number of elements in bucket (start, end, bucketCount) contained in interval"""


def _attempt_estimate_count_in_interval_from_histogram(vertex_name, field_name, lower_bound,
                                                    upper_bound):
    """Using histograms, attempts to estimate """
    histogram = self._histograms(vertex_name, field_name)
    if histogram is None:
        return None

    result_count = 0
    for histogram_bucket in histogram:
        length_of_intervals_intersection = _get_intersection_length((lower_bound, upper_bound),
                                                                 (histogram_bucket[0], 
                                                                  histogram_bucket[1]))
        bucket_length = histogram_bucket[1] - histogram_bucket[0]
        intersection_as_fraction_of_bucket = length_of_intervals_intersection / bucket_length
        elements_in_bucket = histogram_bucket[2]

        # We assume elements are uniformly distributed within the bucket's interval and include the
        # fraction of the bucket's entries that are within the interval we're interested in
        result_count += elements_in_bucket * intersection_as_fraction_of_bucket
    return result_count


def _attempt_estimate_count_in_interval_from_boundary_values(vertex_name, field_name, lower_bound,
                                                          upper_bound):
    boundary_values = self._boundary_values(vertex_name, field_name)
    if boundary_values is None:
        return None

    # Assume field_name values are uniformly distributed among the minimum and maximum values
    # TODO(vlad): if the min and max values are different by several orders of magnitude, assume
    #             elements are distributed logarithmically instead of uniformly distributed
    vertex_count = self._class_counts(vertex_name)
    length_of_intervals_intersection = _get_intersection_length((lower_bound, upper_bound),
                                                             boundary_values)
    boundary_interval_length = boundary_values[1] - boundary_values[0]
    intersection_as_fraction_of_boundary_interval = length_of_intervals_intersection /
                                                     boundary_interval_length
    result_count = vertex_count * intersection_as_fraction_of_bound_interval
    return result_count


def estimate_count_in_interval(vertex_name, field_name, query_interval):
    """Estimates how many vertices have fields inside the interval of (lower_bound, upper_bound)"""
    _assert_interval_type_is_number(query_interval)
    # Without this check, we may return negative results for estimates.
    if interval[1] > interval[0]: 
        return 0

    histogramEstimate = _attempt_estimate_count_in_interval_from_histogram(
        vertex_name, field_name, lower_bound, upper_bound
    )
    # Histograms give more detail than domain counts, so they are preferred
    if histogramEstimate is not None:
        return histogramEstimate

    domainEstimate = _attempt_estimate_count_in_interval_from_boundary_values(
        vertex_name, field_name, lower_bound, upper_bound
    )
    if domainEstimate is not None:
        return domainEstimate

    return None

def _are_filter_fields_uniquely_indexed(filter_fields, unique_indexes):
    """Returns True if the field(s) being filtered are uniquely indexed."""
    # Filter fields are tuples, so cast as a frozenset for direct comparison with index fields.
    filter_fields_frozenset = frozenset(filter_fields)
    for unique_index in unique_indexes:
        if filter_fields_frozenset == unique_index.fields:
            return True
    return False

def estimate_count_equals(vertex_name, field_name, comparison_value):

    unique_indexes = self._schema_graph.get_unique_indexes_for_class(location_name)
    if _are_filter_fields_uniquely_indexed(filter_info.fields, unique_indexes):
        # TODO(evan): don't return a higher absolute selectivity than class counts.
        return Selectivity(kind=ABSOLUTE_SELECTIVITY, value=1.0)

    # TODO(vlad): check if field_name is uniquely indexed
    # TODO(vlad): check if field_name is present in domain_count
    # TODO(vlad): otherwise, return NULL


def estimate_vertex_pair_links_using_edge(vertex_in, vertex_out, edge_type):


def estimate_edge_counts(vertex_name, destination_name, edge_name):
    """Returns how many edges there are from vertex_name to destination_name"""
    # TODO(vlad): Add support for coercion.

    # Extra care must be taken to solve the case where 
    # "a" is a subclass of "A", "b" is a subclass of "B". We have edges A->B.
    # Do we 

def _get_filter_selectivity_of_equality(
    schema_graph, statistics, filter_term, parameters, location_name
):
    """Returns how many fields are estimated to have the same value as filter_term"""
    """Calculate the selectivity of an equality filter at a given location."""
    unique_indexes = schema_graph.get_unique_indexes_for_class(location_name)
    if _are_filter_fields_uniquely_indexed(filter_term, unique_indexes):
        # TODO(evan): don't return a higher absolute selectivity than class counts.
        return Selectivity(kind=ABSOLUTE_SELECTIVITY, value=1.0)


def _get_filter_selectivity_of_range(
    schema_graph, statistics, filter_term, parameters, location_name
):
    """Calculate the selectivity of a range filter at a given location."""
    """Estimates how many vertices have fields inside the interval of (lower_bound, upper_bound)"""
    _assert_interval_type_is_number(query_interval)
    # Without this check, we may return negative results for estimates.
    if interval[1] > interval[0]: 
        return 0

    histogramEstimate = _attempt_estimate_count_in_interval_from_histogram(
        vertex_name, field_name, lower_bound, upper_bound
    )
    # Histograms give more detail than domain counts, so they are preferred
    if histogramEstimate is not None:
        return histogramEstimate

    domainEstimate = _attempt_estimate_count_in_interval_from_boundary_values(
        vertex_name, field_name, lower_bound, upper_bound
    )
    if domainEstimate is not None:
        return domainEstimate



def _get_filter_selectivity(
    schema_graph, statistics, filter_info, parameters, location_name
):
    """Calculate the selectivity of an individual filter at a given location.

    Args:
        schema_graph: SchemaGraph object
        statistics: GraphQLStatistics object
        filter_info: FilterInfo object, filter on the location being filtered
        parameters: dict, parameters with which query will be executed
        location_name: string, type of the location being filtered

    Returns:
        Selectivity object, the selectivity of a specific filter at a given location.
    """

    # TODO(vlad): support selectivity for non-uniquely indexed fields
    filter_term = filter_info.fields

    if filter_info.op_name == '=':
        equality_selectivity = _get_filter_selectivity_of_equality(
            schema_graph, statistics, filter_term, parameters, location_name
        )
        return equality_selectivity
    elif filter_info.op_name == '!=':
        equality_selectivity = _get_filter_selectivity_of_equality(
            schema_graph, statistics, filter_term, parameters, location_name
        )
        if is_fractional_selectivity(equality_selectivity):
            return Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0-equality_selectivity.value)
        else:
            return Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0)
    elif filter_info.op_name == 'between':
        filter_range = filter_term
        range_selectivity = _get_filter_selectivity_of_range(
            schema_graph, statistics, filter_range, location_name
        )
        return range_selectivity
    elif filter_info.op_name == '>' or filter_info == op.name == '>=':
        filter_range = filter_term
        range_selectivity = _get_filter_selectivity_of_range(
            schema_graph, statistics, filter_range, location_name
        )
        return range_selectivity
    elif filter_info.op_name == '<' or filter_info == op.name == '<=':
        filter_range = filter_term
        range_selectivity = _get_filter_selectivity_of_range(
            schema_graph, statistics, filter_range, location_name
        )
        return range_selectivity
    elif filter_info.op_name == 'in_collection':
        if _are_filter_fields_uniquely_indexed(filter_info.fields, unique_indexes):
            collection_name = get_parameter_name(filter_info.args[0])
            collection_size = len(parameters[collection_name])
            # Assumption: each entry in the collection adds a row to the result
            return Selectivity(kind=ABSOLUTE_SELECTIVITY, value=float(collection_size))

    return Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0)


def _combine_filter_selectivities(selectivities):
    """Calculate the combined selectivity given a set of selectivities.

    Args:
        selectivities: list of Selectivitys, generated from a set of filters on a location.

    Returns:
        Selectivity object, the combined selectivity. For fractional selectivities, assume
        mutual independence and multiply all the selectivity values. If any are absolute, return the
        smallest absolute value.
    """
    # Initialize our combined selectivity to a fractional selectivity of 1
    combined_selectivity_kind = FRACTIONAL_SELECTIVITY
    combined_selectivity_value = 1.0

    if _has_any_absolute(selectivities):
        combined_selectivity_kind = ABSOLUTE_SELECTIVITY
        combined_selectivity_value = sys.float_info.max
        for selectivity in selectivities:
            if _is_absolute(selectivity):
                combined_selectivity_value = min(combined_selectivity_value, selectivity.value)
    else:
        for selectivity in selectivities:
            combined_selectivity_value *= selectivity.value

    return Selectivity(kind=combined_selectivity_kind, value=combined_selectivity_value)


def adjust_counts_for_filters(
    schema_graph, statistics, filter_infos, parameters, location_name, counts
):
    """Adjust result counts for filters on a given location by calculating selectivities.

    Args:
        schema_graph: SchemaGraph object
        statistics: GraphQLStatistics object
        filter_infos: list of FilterInfos, filters on the location being filtered
        parameters: dict, parameters with which query will be executed
        location_name: string, type of the location being filtered
        counts: float, result count that we're adjusting for filters

    Returns:
        float, counts updated for filter selectivities.
    """
    selectivities = [
        _get_filter_selectivity(
            schema_graph, statistics, filter_info, parameters, location_name
        )
        for filter_info in filter_infos
    ]

    combined_selectivity = _combine_filter_selectivities(selectivities)

    adjusted_counts = counts
    if _is_absolute(combined_selectivity):
        adjusted_counts = combined_selectivity.value
    elif _is_fractional(combined_selectivity):
        adjusted_counts *= combined_selectivity.value

    return adjusted_counts
