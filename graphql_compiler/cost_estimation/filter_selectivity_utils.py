# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
import sys

from ..compiler.helpers import get_parameter_name


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


def _are_filter_fields_uniquely_indexed(filter_fields, unique_indexes):
    """Returns True if the field(s) being filtered are uniquely indexed."""
    # Filter fields are tuples, so cast as a frozenset for direct comparison with index fields.
    filter_fields_frozenset = frozenset(filter_fields)
    for unique_index in unique_indexes:
        if filter_fields_frozenset == unique_index.fields:
            return True
    return False


def _estimate_filter_selectivity_of_equality(
    schema_graph, statistics, location_name, filter_fields
):
    """Calculate the selectivity of equality filter(s) at a given location.

    Using the available unique indexes, and the distinct-field-values-count statistic, this function
    extracts the current location's selectivites, and then combines them, returning one Selectivity
    object.

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
        # TODO(evan): don't return a higher absolute selectivity than vertex counts.
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
