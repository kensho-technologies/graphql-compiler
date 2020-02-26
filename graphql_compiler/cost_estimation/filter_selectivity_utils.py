# Copyright 2019-present Kensho Technologies, LLC.
from __future__ import division

import bisect
from collections import namedtuple
import sys
from typing import Any, Dict, List

import six

from ..compiler.helpers import get_parameter_name, is_runtime_parameter
from ..compiler.metadata import FilterInfo
from ..schema.schema_info import QueryPlanningSchemaInfo
from .helpers import is_uuid4_type
from .int_value_conversion import (
    MAX_UUID_INT,
    MIN_UUID_INT,
    convert_field_value_to_int,
    convert_int_to_field_value,
    field_supports_range_reasoning,
)
from .interval import Interval, IntervalDomain, intersect_int_intervals, measure_int_interval


# The Selectivity represents the selectivity of a filter or a set of filters
Selectivity = namedtuple(
    "Selectivity",
    (
        "kind",  # string, the kind of selectivity, either absolute or fractional
        "value",  # float, either the maximum number of absolute results that pass the filter or the
        # fraction of results that pass the filter
    ),
)

ABSOLUTE_SELECTIVITY = "absolute"
FRACTIONAL_SELECTIVITY = "fractional"

INEQUALITY_OPERATORS = frozenset(["<", "<=", ">", ">=", "between"])


def _is_absolute(selectivity):
    """Return True if selectivity has kind absolute."""
    return selectivity.kind == ABSOLUTE_SELECTIVITY


def _is_fractional(selectivity):
    """Return True if selectivity has kind fractional."""
    return selectivity.kind == FRACTIONAL_SELECTIVITY


def _has_any_absolute(selectivities):
    """Return True if at least one selectivity has kind absolute."""
    for selectivity in selectivities:
        if _is_absolute(selectivity):
            return True
    return False


# TODO(bojanserafimov): The class name should be checked against the class name of the index.
# TODO(bojanserafimov): This is not correct for len(filter_fields) > 1.
def _are_filter_fields_uniquely_indexed(filter_fields, unique_indexes):
    """Return True if the field(s) being filtered are uniquely indexed."""
    # Filter fields are tuples, so cast as a frozenset for direct comparison with index fields.
    filter_fields_frozenset = frozenset(filter_fields)
    for unique_index in unique_indexes:
        if filter_fields_frozenset == unique_index.fields:
            return True
    return False


def _get_query_interval_of_binary_integer_inequality_filter(
    filter_operator: str, parameter_value: int
) -> Interval[int]:
    """Return interval of values passing through a binary integer inequality filter.

    Args:
        filter_operator: the binary inequality filter operation being performed.
        parameter_value: the one and only parameter value given to the filter

    Returns:
         interval of values that pass through the filter.

    Raises:
        ValueError if the number of parameter values is not exactly one.
    """
    lower_bound, upper_bound = None, None

    if filter_operator == ">":
        lower_bound = parameter_value + 1
    elif filter_operator == ">=":
        lower_bound = parameter_value
    elif filter_operator == "<":
        upper_bound = parameter_value - 1
    elif filter_operator == "<=":
        upper_bound = parameter_value
    else:
        raise AssertionError(
            u"Cost estimator found unsupported "
            u"binary integer inequality operator {}.".format(filter_operator)
        )

    return Interval[int](lower_bound, upper_bound)


def _get_query_interval_of_ternary_integer_inequality_filter(
    filter_operator: str, parameter_value_1: int, parameter_value_2: int
) -> Interval[int]:
    """Return interval of values passing through a ternary integer inequality filter.

    Args:
        filter_operator: the ternary inequality filter operation being performed.
        parameter_value_1: the first parameter value given to the filter
        parameter_value_2: the second parameter value given to the filter

    Returns:
        interval of values that pass through the filter.

    Raises:
        ValueError if the number of parameter values is not exactly two.
    """
    lower_bound, upper_bound = None, None

    if filter_operator == "between":
        lower_bound = parameter_value_1
        upper_bound = parameter_value_2
    else:
        raise AssertionError(
            u"Cost estimator found unsupported "
            u"ternary integer inequality operator {}.".format(filter_operator)
        )

    return Interval[int](lower_bound, upper_bound)


def _get_query_interval_of_integer_inequality_filter(
    parameter_values: List[int], filter_operator: str
) -> Interval[int]:
    """Return interval of values passing through a given integer inequality filter.

    Args:
        parameter_values: the parameters for the inequality filter.
        filter_operator: the inequality filter operation being performed.

    Returns:
        interval of values that pass through the filter.
    """
    if len(parameter_values) == 1:
        query_interval = _get_query_interval_of_binary_integer_inequality_filter(
            filter_operator, parameter_values[0]
        )
    elif len(parameter_values) == 2:
        query_interval = _get_query_interval_of_ternary_integer_inequality_filter(
            filter_operator, parameter_values[0], parameter_values[1]
        )
    else:
        raise AssertionError(
            u"Cost estimator found filter operator {} with parameter values {}. "
            u"Currently, an operator must have either one or two parameter values.".format(
                filter_operator, parameter_values
            )
        )

    return query_interval


# TODO(bojanserafimov): This function can be simplified, as len(filter_fields) is always 1.
def _estimate_filter_selectivity_of_equality(schema_info, location_name, filter_fields):
    """Calculate the selectivity of equality filter(s) at a given location.

    Using the available unique indexes and/or the distinct_field_values_count statistic, this
    function extracts the current location's selectivites, and then combines them, returning one
    Selectivity object.

    Args:
        schema_info: QueryPlanningSchemaInfo
        location_name: string, type of the location being filtered
        filter_fields: tuple of str, listing all the fields being filtered over

    Returns:
        Selectivity object, the selectivity of an specific equality filter at a given location.
    """
    all_selectivities = []

    unique_indexes = schema_info.schema_graph.get_unique_indexes_for_class(location_name)
    if _are_filter_fields_uniquely_indexed(filter_fields, unique_indexes):
        # TODO(evan): don't return a higher absolute selectivity than class counts.
        all_selectivities.append(Selectivity(kind=ABSOLUTE_SELECTIVITY, value=1.0))

    for field_name in filter_fields:
        statistics_result = schema_info.statistics.get_distinct_field_values_count(
            location_name, field_name
        )

        if statistics_result is not None:
            # Assumption: all distinct field values are distributed evenly among vertex instances,
            # so each distinct value occurs
            # (# of current location vertex instances) / (# of distinct field values) times.
            all_selectivities.append(
                Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0 / statistics_result)
            )

    result_selectivity = _combine_filter_selectivities(all_selectivities)
    return result_selectivity


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


def _get_selectivity_fraction_of_interval(
    interval: Interval[IntervalDomain], quantiles: List[IntervalDomain]
) -> float:
    """Get the fraction of values contained in an interval.

    We ignore the interval endpoint values, and only consider the quantile they
    are in. We treat the endpoints as uniform random variables within their quantile
    and compute the expected value of the length of the interval divided by the size
    of the whole domain.

    Args:
        interval: Interval[T] defining the range of values
        quantiles: a sorted list of N values of type T separating the values of the field
                   into N-1 groups of almost equal size. The first element of the list is the
                   smallest known value, and the last element is the largest known value.
                   The i-th element is a value greater than or equal to i/N of all present values.
                   N has to be at least 2.

    Returns:
        float, the fraction of the values contained in the interval.
    """
    if interval.is_empty():
        return 0.0

    if len(quantiles) < 2:
        raise AssertionError(u"Need at least 2 quantiles: {}".format(len(quantiles)))
    # Since we can't be sure the minimum observed value is the
    # actual minimum value, we treat values less than it as part
    # of the first quantile. That's why we drop the minimum and
    # maximum observed values from the quantile list.
    proper_quantiles = quantiles[1:-1]
    domain_interval_size = float(len(proper_quantiles) + 1)
    if interval.lower_bound is None and interval.upper_bound is None:
        interval_size = domain_interval_size
    elif interval.lower_bound is None:
        upper_bound_quantile = bisect.bisect_left(proper_quantiles, interval.upper_bound)
        interval_size = 0.5 + float(upper_bound_quantile)
    elif interval.upper_bound is None:
        lower_bound_quantile = bisect.bisect_left(proper_quantiles, interval.lower_bound)
        interval_size = 0.5 + float(len(proper_quantiles) - lower_bound_quantile)
    else:
        lower_bound_quantile = bisect.bisect_left(proper_quantiles, interval.lower_bound)
        upper_bound_quantile = bisect.bisect_left(proper_quantiles, interval.upper_bound)
        if lower_bound_quantile == upper_bound_quantile:
            # Average distance between two random points on a unit line segment:
            # https://math.stackexchange.com/questions/195245/
            interval_size = 1.0 / 3.0
        else:
            interval_size = upper_bound_quantile - lower_bound_quantile
    return float(interval_size) / domain_interval_size


def _filter_uses_only_runtime_parameters(filter_info: FilterInfo) -> bool:
    """Return whether the filter uses only runtime parameters."""
    for filter_argument in filter_info.args:
        if not is_runtime_parameter(filter_argument):
            return False
    return True


def get_integer_interval_for_filters_on_field(
    schema_info: QueryPlanningSchemaInfo,
    filters_on_field: List[FilterInfo],
    location_name: str,
    field_name: str,
    parameters: Dict[str, Any],
) -> Interval[int]:
    """Get the interval of possible values on this field, constrained by its inequality filters."""
    interval = Interval[int](None, None)
    for filter_info in filters_on_field:
        if not _filter_uses_only_runtime_parameters(filter_info):
            continue  # We can't reason about tagged parameters
        if filter_info.op_name in INEQUALITY_OPERATORS:
            parameter_values = [
                convert_field_value_to_int(
                    schema_info,
                    location_name,
                    field_name,
                    parameters[get_parameter_name(filter_argument)],
                )
                for filter_argument in filter_info.args
            ]

            filter_interval = _get_query_interval_of_integer_inequality_filter(
                parameter_values, filter_info.op_name
            )
            interval = intersect_int_intervals(interval, filter_interval)
    return interval


def get_selectivity_of_filters_at_vertex(schema_info, filter_infos, parameters, location_name):
    """Get the combined selectivity of all filters at the vertex.

    Args:
        schema_info: QueryPlanningSchemaInfo
        filter_infos: list of FilterInfos, filters on the location being filtered
        parameters: dict, parameters with which query will be executed
        location_name: string, type of the location being filtered
        counts: float, result count that we're adjusting for filters

    Returns:
        Selectivity object
    """
    # Group filters by field
    single_field_filters = {}
    for filter_info in filter_infos:
        if len(filter_info.fields) == 0:
            raise AssertionError(u"Got filter on 0 fields {} {}".format(filter_info, location_name))
        elif len(filter_info.fields) == 1:
            single_field_filters.setdefault(filter_info.fields[0], []).append(filter_info)
        else:
            pass  # We don't do anything for multi-field filters yet

    # Find the selectivity of filters on each field
    selectivities = []
    for field_name, filters_on_field in six.iteritems(single_field_filters):
        selectivity_at_field = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0)
        interval = Interval[int](None, None)

        # Process inequality filters
        if field_supports_range_reasoning(schema_info, location_name, field_name):
            interval = get_integer_interval_for_filters_on_field(
                schema_info, filters_on_field, location_name, field_name, parameters
            )

            if interval is None:
                selectivity_at_field = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=0.0)
            elif is_uuid4_type(schema_info, location_name, field_name):
                # uuid4 fields are uniformly distributed, so we simply divide the fraction of
                # the domain queried with the size of the domain.
                domain_interval = Interval[int](MIN_UUID_INT, MAX_UUID_INT)
                interval = intersect_int_intervals(interval, domain_interval)
                fraction_of_domain_queried = float(
                    measure_int_interval(interval)
                ) / measure_int_interval(domain_interval)
                selectivity = Selectivity(
                    kind=FRACTIONAL_SELECTIVITY, value=fraction_of_domain_queried
                )
                selectivity_at_field = _combine_filter_selectivities(
                    [selectivity_at_field, selectivity]
                )
            else:
                # Get value interval
                lower_bound, upper_bound = None, None
                if interval.lower_bound is not None:
                    lower_bound = convert_int_to_field_value(
                        schema_info, location_name, field_name, interval.lower_bound
                    )
                if interval.upper_bound is not None:
                    upper_bound = convert_int_to_field_value(
                        schema_info, location_name, field_name, interval.upper_bound
                    )
                value_interval = Interval(lower_bound, upper_bound)

                # Compute selectivity
                quantiles = schema_info.statistics.get_field_quantiles(location_name, field_name)
                if quantiles is not None:
                    selectivity = Selectivity(
                        kind=FRACTIONAL_SELECTIVITY,
                        value=_get_selectivity_fraction_of_interval(value_interval, quantiles),
                    )
                    selectivity_at_field = _combine_filter_selectivities(
                        [selectivity_at_field, selectivity]
                    )

        # Process in_collection filters
        for filter_info in filters_on_field:
            if filter_info.op_name == "in_collection":
                if not _filter_uses_only_runtime_parameters(filter_info):
                    continue  # We can't reason about tagged parameters

                # TODO(bojanserafimov): Check if the filter values are in the interval selected
                #                       by the inequality filters.
                collection = parameters[get_parameter_name(filter_info.args[0])]
                selectivity_per_entry_in_collection = _estimate_filter_selectivity_of_equality(
                    schema_info, location_name, filter_info.fields
                )

                # Assumption: the selectivity is proportional to the number of entries in
                # the collection. This will not hold in case of duplicates.
                if _is_absolute(selectivity_per_entry_in_collection):
                    selectivity = Selectivity(
                        kind=ABSOLUTE_SELECTIVITY,
                        value=float(len(collection)) * selectivity_per_entry_in_collection.value,
                    )
                elif _is_fractional(selectivity_per_entry_in_collection):
                    selectivity = Selectivity(
                        kind=FRACTIONAL_SELECTIVITY,
                        value=min(
                            float(len(collection)) * selectivity_per_entry_in_collection.value, 1.0
                        )
                        # The estimate may be above 1.0 in case of duplicates in the collection
                        # so we make sure the value is <= 1.0
                    )
                selectivity_at_field = _combine_filter_selectivities(
                    [selectivity_at_field, selectivity]
                )

        # Process equality filters
        for filter_info in filters_on_field:
            if filter_info.op_name == "=":
                # TODO(bojanserafimov): Check if the filter value is in the interval selected
                #                       by the inequality filters.
                selectivity = _estimate_filter_selectivity_of_equality(
                    schema_info, location_name, filter_info.fields
                )
                selectivity_at_field = _combine_filter_selectivities(
                    [selectivity_at_field, selectivity]
                )

        selectivities.append(selectivity_at_field)

    # Combine selectivities
    combined_selectivity = _combine_filter_selectivities(selectivities)
    return combined_selectivity


def adjust_counts_for_filters(schema_info, filter_infos, parameters, location_name, counts):
    """Adjust result counts for filters on a given location by calculating selectivities.

    Args:
        schema_info: QueryPlanningSchemaInfo
        filter_infos: list of FilterInfos, filters on the location being filtered
        parameters: dict, parameters with which query will be executed
        location_name: string, type of the location being filtered
        counts: float, result count that we're adjusting for filters

    Returns:
        float, counts updated for filter selectivities.
    """
    combined_selectivity = get_selectivity_of_filters_at_vertex(
        schema_info, filter_infos, parameters, location_name
    )
    adjusted_counts = counts
    if _is_absolute(combined_selectivity):
        adjusted_counts = combined_selectivity.value
    elif _is_fractional(combined_selectivity):
        adjusted_counts *= combined_selectivity.value

    return adjusted_counts
