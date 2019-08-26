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
    'lower_bound',    # int or None, inclusive lower bound of integers in the interval.
                      # Intervals that do not have a lower bound denote this by using None.
    'upper_bound',    # int or None, inclusive upper bound of integers in the interval.
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


def _are_filter_fields_uniquely_indexed(filter_fields, unique_indexes):
    """Return True if the field(s) being filtered are uniquely indexed."""
    # Filter fields are tuples, so cast as a frozenset for direct comparison with index fields.
    filter_fields_frozenset = frozenset(filter_fields)
    for unique_index in unique_indexes:
        if filter_fields_frozenset == unique_index.fields:
            return True
    return False


def _convert_uuid_string_to_int(uuid_string):
    """Return the integer representation of a UUID string."""
    return UUID(uuid_string).int


def _create_integer_interval(lower_bound, upper_bound):
    """Return IntegerInterval for the given bounds, or None if the interval is empty.

    Args:
        lower_bound: int or None, describing the inclusive lower bound of the integer interval.
                     If the bound does not exist, the argument value should be None.
        upper_bound: int or None, describing the inclusive upper bound of the integer interval.
                     If the bound does not exist, the argument value should be None.

    Returns:
        - IntegerInterval namedtuple, describing the non-empty interval of integers between the two
          bounds.
        - None if the interval defined by the bounds is empty.
    """
    # If the lower bound is greater than the upper bound, then the interval is empty, which we
    # indicate by returning None.
    if lower_bound is not None and upper_bound is not None and lower_bound > upper_bound:
        interval = None
    else:
        interval = IntegerInterval(lower_bound, upper_bound)

    return interval


def _get_stronger_lower_bound(lower_bound_a, lower_bound_b):
    """Return the larger bound of the two given lower bounds.

    Args:
        lower_bound_a: int or None, describing one of the lower bounds. If the bound does not exist,
                       the argument value should be None.
        lower_bound_b: int or None, describing one of the lower bounds. If the bound does not exist,
                       the argument value should be None.

    Returns:
        - int, the larger of the two lower bounds, if one or more lower bounds have an integer
          value.
        - None if both lower bounds have a value of None.
    """
    stronger_lower_bound = None
    if lower_bound_a is not None and lower_bound_b is not None:
        stronger_lower_bound = max(lower_bound_a, lower_bound_b)
    elif lower_bound_a is not None:
        stronger_lower_bound = lower_bound_a
    elif lower_bound_b is not None:
        stronger_lower_bound = lower_bound_b

    return stronger_lower_bound


def _get_stronger_upper_bound(upper_bound_a, upper_bound_b):
    """Return the smaller bound of the two given upper bounds.

    Args:
        upper_bound_a: int or None, describing one of the upper bounds. If the bound does not exist,
                       the argument value should be None.
        upper_bound_b: int or None, describing one of the upper bounds. If the bound does not exist,
                       the argument value should be None.

    Returns:
        - int, the smaller of the two upper bounds, if one or more upper bounds have an integer
          value.
        - None if both upper bounds have a value of None.
    """
    stronger_upper_bound = None
    if upper_bound_a is not None and upper_bound_b is not None:
        stronger_upper_bound = min(upper_bound_a, upper_bound_b)
    elif upper_bound_a is not None:
        stronger_upper_bound = upper_bound_a
    elif upper_bound_b is not None:
        stronger_upper_bound = upper_bound_b

    return stronger_upper_bound


def _get_intersection_of_intervals(interval_a, interval_b):
    """Return the intersection of two IntegerIntervals, or None if the intervals are disjoint.

    Args:
        interval_a: IntegerInterval namedtuple.
        interval_b: IntegerInterval namedtuple.

    Returns:
        - IntegerInterval namedtuple, intersection of the two given IntegerIntervals, if the
          intersection is not empty.
        - None otherwise.
    """
    strong_lower_bound = _get_stronger_lower_bound(interval_a.lower_bound, interval_b.lower_bound)
    strong_upper_bound = _get_stronger_upper_bound(interval_a.upper_bound, interval_b.upper_bound)

    intersection = _create_integer_interval(strong_lower_bound, strong_upper_bound)
    return intersection


def _get_query_interval_of_binary_integer_inequality_filter(
    parameter_values, filter_operator
):
    """Return IntegerInterval or None of values passing through a binary integer inequality filter.

    Args:
        parameter_values: List[int], describing the parameters for the inequality filter.
        filter_operator: str, describing the binary inequality filter operation being performed.

    Returns:
        - IntegerInterval namedtuple, non-empty interval of values that pass through the filter.
        - None if the interval is empty.

    Raises:
        ValueError if the number of parameter values is not exactly one.
    """
    if len(parameter_values) != 1:
        raise ValueError(u'Binary inequality filter should have '
                         u'exactly one parameter value: {} {}'
                         .format(parameter_values, filter_operator))

    lower_bound, upper_bound = None, None

    parameter_value = parameter_values[0]
    if filter_operator == '>':
        lower_bound = parameter_value + 1
    elif filter_operator == '>=':
        lower_bound = parameter_value
    elif filter_operator == '<':
        upper_bound = parameter_value - 1
    elif filter_operator == '<=':
        upper_bound = parameter_value
    else:
        raise AssertionError(u'Cost estimator found unsupported '
                             u'binary integer inequality operator {}.'
                             .format(filter_operator))

    query_interval = _create_integer_interval(lower_bound, upper_bound)
    return query_interval


def _get_query_interval_of_ternary_integer_inequality_filter(
    parameter_values, filter_operator
):
    """Return IntegerInterval or None of values passing through a ternary integer inequality filter.

    Args:
        parameter_values: List[int], describing the parameters for the inequality filter.
        filter_operator: str, describing the ternary inequality filter operation being performed.

    Returns:
        - IntegerInterval namedtuple, non-empty interval of values that pass through the filter.
        - None if the interval is empty.

    Raises:
        ValueError if the number of parameter values is not exactly two.
    """
    if len(parameter_values) != 2:
        raise ValueError(u'Ternary inequality filter should have '
                         u'exactly two parameter values: {} {}'
                         .format(parameter_values, filter_operator))

    lower_bound, upper_bound = None, None

    if filter_operator == 'between':
        lower_bound = parameter_values[0]
        upper_bound = parameter_values[1]
    else:
        raise AssertionError(u'Cost estimator found unsupported '
                             u'ternary integer inequality operator {}.'
                             .format(filter_operator))

    query_interval = _create_integer_interval(lower_bound, upper_bound)
    return query_interval


def _get_query_interval_of_integer_inequality_filter(parameter_values, filter_operator):
    """Return IntegerInterval or None of values passing through a given integer inequality filter.

    Args:
        parameter_values: List[int], describing the parameters for the inequality filter.
        filter_operator: str, describing the inequality filter operation being performed.

    Returns:
        - IntegerInterval namedtuple, non-empty interval of values that pass through the filter.
        - None if the interval is empty.
    """
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

    Args:
        domain_interval: IntegerInterval namedtuple, describing the finite non-empty interval
                         of integers being filtered.
        parameter_values: List[int], describing the parameters for the inequality filter.
        filter_operator: str, describing the inequality filter operation being performed.

    Returns:
        Selectivity object, describing the selectivity of the integer inequality filter.

    Raises:
        ValueError if:
            - The domain interval's lower or upper bound is not defined.
            - The domain interval is empty i.e. its lower bound is greater than its upper bound.
    """
    if domain_interval.lower_bound is None or domain_interval.upper_bound is None:
        raise ValueError(u'Expected domain interval {} to have both a lower and upper bound.'
                         .format(domain_interval))
    if domain_interval.lower_bound > domain_interval.upper_bound:
        raise ValueError(u'Received empty domain interval {}.'.format(domain_interval))

    query_interval = _get_query_interval_of_integer_inequality_filter(
        parameter_values, filter_operator
    )

    if query_interval is None:
        field_selectivity = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=0.0)
        return field_selectivity

    intersection = _get_intersection_of_intervals(domain_interval, query_interval)

    # If the interval of values passing through the filters is empty, no results will be
    # returned. This happens if the interval's upper bound is smaller than the lower bound.
    if intersection is None:
        field_selectivity = Selectivity(kind=ABSOLUTE_SELECTIVITY, value=0.0)
        return field_selectivity

    if (
        not domain_interval.lower_bound <= intersection.lower_bound <=
            intersection.upper_bound <= domain_interval.upper_bound
    ):
        raise AssertionError(u'Intersection between domain interval and query interval {} is not '
                             u'a subset of the given domain interval {}.'
                             .format(intersection, domain_interval))

    # Assumption: the values of the integers being filtered are evenly distributed among the domain
    # of valid values.
    intersection_size = intersection.upper_bound - intersection.lower_bound + 1
    domain_interval_size = domain_interval.upper_bound - domain_interval.lower_bound + 1

    # False-positive bug in pylint: https://github.com/PyCQA/pylint/issues/3039
    # pylint: disable=old-division
    #
    fraction_of_domain_queried = float(intersection_size) / domain_interval_size
    # pylint: enable=old-division

    field_selectivity = Selectivity(kind=FRACTIONAL_SELECTIVITY, value=fraction_of_domain_queried)
    return field_selectivity


def _estimate_inequality_filter_selectivity(
    schema_graph, statistics, filter_info, parameters, location_name
):
    """Calculate the selectivity of a specific inequality filter at a given location.

    Args:
        schema_graph: SchemaGraph object
        statistics: Statistics object
        filter_info: FilterInfo object, inequality filter on the location being filtered
        parameters: dict, parameters with which query will be executed
        location_name: string, type of the location being filtered

    Returns:
        Selectivity object, the selectivity of a specific inequality filter at a given location.

    Raises:
        ValueError if the received filter is not an inequality filter.
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
        # TODO(vlad): Since we assume each filter is independent, we don't consider the correlation
        #             inequality filters often have. For example, a 'between' filter and an
        #             equivalent pair of '>=' and '<=' are estimated differently. Consult the
        #             FilterSelectivityTests/test_inequality_filters_on_uuid function for further
        #             information.
        result_selectivity = _estimate_inequality_filter_selectivity(
            schema_graph, statistics, filter_info, parameters, location_name
        )

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
