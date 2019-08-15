# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
import sys
from uuid import UUID

from ..compiler.helpers import get_parameter_name


# The Selectivity represents the selectivity of a filter or a set of filters
Selectivity = namedtuple('Selectivity', (
    'kind',     # string, the kind of selectivity, either absolute or fractional
    'value',    # float, either the maximum number of absolute results that pass the filter or the
                # fraction of results that pass the filter
))

# IntegerInterval is used to denote a continuous non-empty interval of integers.
IntegerInterval = namedtuple('IntegerInterval', (
    'lower_bound',    # optional int, inclusive lower bound of integers in the interval.
                      # Intervals that do not have a lower bound denote this by using None.
    'upper_bound',    # optional int, inclusive upper bound of integers in the interval.
                      # Intervals that do not have an upper bound denote this by using None.
))

ABSOLUTE_SELECTIVITY = 'absolute'
FRACTIONAL_SELECTIVITY = 'fractional'

INEQUALITY_OPERATORS = frozenset(['<', '<=', '>', '>=', 'between'])

# UUIDs are defined in RFC-4122 as a 128-bit identifier. This means that the minimum UUID value
# (represented as a natural number) is 0, and the maximal value is 2^128-1.
MIN_UUID_INT = 0
MAX_UUID_INT = 2**128 - 1


def _is_absolute(selectivity):
    """Returns True if selectivity has kind absolute."""
    return selectivity.kind == ABSOLUTE_SELECTIVITY


def _is_fractional(selectivity):
    """Returns True if selectivity has kind fractional."""
    return selectivity.kind == FRACTIONAL_SELECTIVITY


def _get_intersection_of_IntegerIntervals(interval_a, interval_b):
    """Return the intersection of two IntegerIntervals, or None if the intervals are disjoint."""
    intersection = IntegerInterval(None, None)

    if interval_a.lower_bound is not None and interval_b.lower_bound is not None:
        intersection = max(interval_a.lower_bound, interval_b.lower_bound)
    elif interval_a.lower_bound is not None or interval_b.lower_bound is not None:
        intersection = interval_a.lower_bound or interval_b.lower_bound

    if interval_a.upper_bound is not None and interval_b.upper_bound is not None:
        intersection = min(interval_a.upper_bound, interval_b.upper_bound)
    elif interval_a.upper_bound is not None or interval_b.upper_bound is not None:
        intersection = interval_a.upper_bound or interval_b.upper_bound

    # If the intersection's lower bound is larger than its upper bound, then the intersection of the
    # two intervals is empty, so we return None to indicate an empty set.
    if (
        intersection.lower_bound is not None and
        intersection.upper_bound is not None and
        intersection.lower_bound > intersection.upper_bound
    ):
        intersection = None

    return intersection


def _has_any_absolute(selectivities):
    """Returns True if at least one selectivity has kind absolute."""
    for selectivity in selectivities:
        if _is_absolute(selectivity):
            return True
    return False


def _are_filter_fields_uniquely_indexed(filter_fields, unique_indexes):
    """Returns True if the field(s) being filtered are uniquely indexed."""
    # Filter fields are tuples, so cast as a frozenset for direct comparison with index fields.
    filter_fields_frozenset = frozenset(filter_fields)
    for unique_index in unique_indexes:
        if filter_fields_frozenset == unique_index.fields:
            return True
    return False


def _convert_uuid_string_to_int(uuid_string):
    """Return the integer representation of a UUID string."""
    return UUID(uuid_string).int


def _get_query_interval_of_binary_integer_inequality_filter(
    parameter_values, filter_operator
):
    """Return IntegerInterval of values passing through a binary integer inequality filter."""
    if len(parameter_values) != 1:
        raise ValueError(u'Binary inequality filter should have '
                         u'exactly one parameter value: {} {}'
                         .format(parameter_values, filter_operator))

    parameter_value = parameter_values[0]
    query_interval = IntegerInterval(None, None)
    if filter_operator == '>':
        # This (exclusively) constrains the lower bound of the values passing through the filter.
        query_interval.lower_bound = parameter_value + 1
    elif filter_operator == '>=':
        # This (inclusively) constrains the lower bound of the values passing through the filter.
        query_interval.lower_bound = parameter_value
    elif filter_operator == '<':
        # This (exclusively) constrains the upper bound of the values passing through the filter.
        query_interval.upper_bound = parameter_value - 1
    elif filter_operator == '<=':
        # This (inclusively) constrains the upper bound of the values passing through the filter.
        query_interval.upper_bound = parameter_value
    else:
        raise AssertionError(u'Cost estimator found unsupported '
                             u'binary integer inequality operator {}.'
                             .format(filter_operator))

    return query_interval


def _get_query_interval_of_ternary_integer_inequality_filter(
    parameter_values, filter_operator
):
    """Return IntegerInterval of values passing through a ternary integer inequality filter."""
    if len(parameter_values) != 2:
        raise ValueError(u'Ternary inequality filter should have '
                         u'exactly two parameter values: {} {}'
                         .format(parameter_values, filter_operator))

    query_interval = IntegerInterval(None, None)
    if filter_operator == 'between':
        # This (inclusively) constrains the lower and upper bounds of the
        # values passing through the filter.
        query_interval.lower_bound = parameter_values[0]
        query_interval.upper_bound = parameter_values[1]
    else:
        raise AssertionError(u'Cost estimator found unsupported '
                             u'ternary integer inequality operator {}.'
                             .format(filter_operator))

    return query_interval


def _get_query_interval_of_integer_inequality_filter(parameter_values, filter_operator):
    """Return IntegerInterval of values passing through a given integer inequality filter."""
    if len(parameter_values) == 1:
        query_interval = _get_query_interval_of_binary_integer_inequality_filter(
            parameter_values, filter_operator
        )
    elif len(parameter_values) == 2:
        query_interval = _get_query_interval_of_ternary_integer_inequality_filter(
            parameter_values, filter_operator
        )
    else:
        raise AssertionError(u'Cost estimator found filter operator {} with parameter values {}. '
                             u'Currently, an operator must have either one or two parameter values.'
                             .format(filter_operator, parameter_values))

    return query_interval


def _get_selectivity_of_integer_inequality_filter(
    domain_interval, parameter_values, filter_operator
):
    """Return the selectivity of a given integer inequality filter filtering over a given interval.

    First, we represent the filter being done in terms of the set of numbers that pass through the
    given filter as an IntegerInterval. If a lower or upper bound does not exist, this is indicated
    using None in the interval representation. For example, a '<' filter with a parameter value of 4
    would be represented as (None, 4).
    After this, we find the intersection of the domain being filtered and the filter interval.
    The larger the intersection relative to the domain interval, the higher the selectivity. For
    example, if the intersection is half as big as the domain interval, this will correspond to a
    Fractional Selectivity with a selectivity factor of 0.5 (i.e. roughly 50% of elements pass
    through the filter).

    Preconditions:
        1. domain_interval is a finite interval i.e. it has a lower and an upper bound.

    Args:
        domain_interval: IntegerInterval namedtuple, describing the finite interval of integers
                         being filtered.
        parameter_values: List[int], describing the parameters for the inequality filter.
        filter_operator: str, describing the inequality filter operation being performed.

    Returns:
        Selectivity object, describing the selectivity of the integer inequality filter.
    """
    # Inequality filters on integers can also be represented by an interval for the subset of values
    # that pass through the filter. By representing the filter as an interval, we avoid considering
    # the operators separately. If a lower or upper bound does not exist, we denote it using None.
    query_interval = _get_query_interval_of_integer_inequality_filter(
        parameter_values, filter_operator
    )

    intersection = _get_intersection_of_IntegerIntervals(domain_interval, query_interval)

    # If the interval of values passing through the filters is empty, no results will be
    # returned. This happens if the interval's upper bound is smaller than the lower bound.
    if intersection is None:
        field_selectivity = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=0.0)
        return field_selectivity

    if not domain_interval[0] <= intersection[0] <= intersection[1] <= domain_interval[1]:
        raise AssertionError(u'Query interval {} is not '
                             u'a subset of the given domain interval {}.'
                             .format(intersection, domain_interval))

    # Assumption: the values of the integers being filtered are evenly distributed among the domain
    # of valid values.
    intersection_size = intersection[1] - intersection[0] + 1
    domain_interval_size = domain_interval[1] - domain_interval[0] + 1
    fraction_of_domain_queried = intersection_size / domain_interval_size

    field_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=fraction_of_domain_queried)
    return field_selectivity


def _estimate_inequality_filter_selectivity(
    schema_graph, statistics, filter_info, parameters, location_name
):
    """Calculate the selectivity of a specific inequality filter at a given location.

    Args:
        schema_graph: SchemaGraph object
        statistics: Statistics object
        filter_info: FilterInfo object, filter on the location being filtered
        parameters: dict, parameters with which query will be executed
        location_name: string, type of the location being filtered

    Returns:
        Selectivity object, the selectivity of a specific inequality filter at a given location.
    """
    filter_operator = filter_info.op_name
    if filter_operator not in INEQUALITY_OPERATORS:
        raise ValueError(u'Inequality filter selectivity estimator received a filter '
                         u'with non-inequality filter operator {}: {} {}'
                         .format(filter_operator, filter_info, location_name))

    all_selectivities = []
    for field_name in filter_info.fields:
        field_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0)

        # TODO(vlad): Improve inequality estimation by implementing histograms.
        # HACK(vlad): Currently, each UUID is assumed to have a name of 'uuid'. Using the schema
        #             graph for knowledge about UUID fields would generalize better.
        if field_name == 'uuid':
            uuid_domain = IntegerInterval(MIN_UUID_INT, MAX_UUID_INT)

            # Instead of working with UUIDs, we convert each occurence of UUID to its corresponding
            # integer representation.
            parameter_values_as_integers = []
            for filter_argument in filter_info.args:
                parameter_name = get_parameter_name(filter_argument)
                parameter_value = parameters[parameter_name]
                parameter_value_as_integer = _convert_uuid_string_to_int(parameter_value)
                parameter_values_as_integers.append(parameter_value_as_integer)

            # Assumption: UUID values are uniformly distributed among the set of valid UUIDs.
            # This implies e.g. if the query interval is half the size of the set of all valid
            # UUIDs, the Selectivity will be Fractional with a selectivity value of 0.5.
            field_selectivity = _get_selectivity_of_integer_inequality_filter(
                uuid_domain, parameter_values_as_integers, filter_operator
            )

        all_selectivities.append(field_selectivity)

    result_selectivity = _combine_filter_selectivities(all_selectivities)
    return result_selectivity


def _estimate_filter_selectivity_of_equality(
    schema_graph, statistics, location_name, filter_fields
):
    """Calculate the selectivity of equality filter(s) at a given location.

    Using the available unique indexes and/or the distinct_field_values_count statistic, this
    function extracts the current location's selectivites, and then combines them, returning one
    Selectivity object.

    Args:
        schema_graph: SchemaGraph object
        statistics: Statistics object
        location_name: string, type of the location being filtered
        filter_fields: tuple of str, listing all the fields being filtered over

    Returns:
        Selectivity object, the selectivity of an specific equality filter at a given location.
    """
    all_selectivities = []

    unique_indexes = schema_graph.get_unique_indexes_for_class(location_name)
    if _are_filter_fields_uniquely_indexed(filter_fields, unique_indexes):
        # TODO(evan): don't return a higher absolute selectivity than class counts.
        all_selectivities.append(Selectivity(kind=ABSOLUTE_SELECTIVITY, value=1.0))

    for field_name in filter_fields:
        statistics_result = statistics.get_distinct_field_values_count(location_name, field_name)

        if statistics_result is not None:
            # Assumption: all distinct field values are distributed evenly among vertex instances,
            # so each distinct value occurs
            # (# of current location vertex instances) / (# of distinct field values) times.
            all_selectivities.append(Selectivity(
                kind=FRACTIONAL_SELECTIVITY, value=1.0 / statistics_result
            ))

    result_selectivity = _combine_filter_selectivities(all_selectivities)
    return result_selectivity


def _get_filter_selectivity(
    schema_graph, statistics, filter_info, parameters, location_name
):
    """Calculate the selectivity of an individual filter at a given location.

    Args:
        schema_graph: SchemaGraph object
        statistics: Statistics object
        filter_info: FilterInfo object, filter on the location being filtered
        parameters: dict, parameters with which query will be executed
        location_name: string, type of the location being filtered

    Returns:
        Selectivity object, the selectivity of a specific filter at a given location.
    """
    result_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=1.0)
    # TODO(vlad): Support for inequality operators like '>', '<', 'between' using histograms
    # TODO(vlad): Support for other filters like '!='

    if filter_info.op_name == '=':
        result_selectivity = _estimate_filter_selectivity_of_equality(
            schema_graph, statistics, location_name, filter_info.fields
        )
    elif filter_info.op_name == 'in_collection':
        collection_name = get_parameter_name(filter_info.args[0])
        collection_size = len(parameters[collection_name])

        selectivity_per_entry_in_collection = _estimate_filter_selectivity_of_equality(
            schema_graph, statistics, location_name, filter_info.fields
        )

        # Assumption: the selectivity is proportional to the number of entries in the collection.
        # This will not hold in case of duplicates.
        if _is_absolute(selectivity_per_entry_in_collection):
            result_selectivity = Selectivity(
                kind=ABSOLUTE_SELECTIVITY,
                value=float(collection_size) * selectivity_per_entry_in_collection.value
            )
        elif _is_fractional(selectivity_per_entry_in_collection):
            result_selectivity = Selectivity(
                kind=FRACTIONAL_SELECTIVITY,
                value=min(float(collection_size) * selectivity_per_entry_in_collection.value,
                          1.0)
                # The estimate may be above 1.0 in case of duplicates in the collection
                # so we make sure the value is <= 1.0
            )
    elif filter_info.op_name in INEQUALITY_OPERATORS:
        result_selectivity = _estimate_inequality_filter_selectivity(
            schema_graph, statistics, filter_info, parameters, location_name)

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


def adjust_counts_for_filters(
    schema_graph, statistics, filter_infos, parameters, location_name, counts
):
    """Adjust result counts for filters on a given location by calculating selectivities.

    Args:
        schema_graph: SchemaGraph object
        statistics: Statistics object
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
