# Copyright 2019-present Kensho Technologies, LLC.
import bisect
from dataclasses import dataclass
from typing import Any, Dict, List

from cached_property import cached_property

from ..compiler.compiler_frontend import graphql_to_ir
from ..compiler.metadata import FilterInfo, QueryMetadataTable
from ..cost_estimation.cardinality_estimator import estimate_query_result_cardinality
from ..cost_estimation.int_value_conversion import (
    convert_int_to_field_value,
    field_supports_range_reasoning,
    is_uuid4_type,
)
from ..cost_estimation.interval import Interval
from ..global_utils import PropertyPath, QueryStringWithParameters, VertexPath
from ..schema import is_meta_field
from ..schema.schema_info import QueryPlanningSchemaInfo
from .filter_selectivity_utils import (
    adjust_counts_for_filters,
    get_integer_interval_for_filters_on_field,
)


def _convert_int_interval_to_field_value_interval(
    schema_info: QueryPlanningSchemaInfo, vertex_type: str, field: str, interval: Interval[int]
) -> Interval[Any]:
    """Convert the integer interval endpoints to a type appropriate for the field.

    Args:
        schema_info: QueryPlanningSchemaInfo
        vertex_type: name of a vertex type
        field: name of a field on the vertex_type
        interval: interval to convert

    Returns:
        Interval with endpoints appropriate for the field on the vertex_type.
    """
    lower_bound = None
    upper_bound = None
    if interval.lower_bound is not None:
        lower_bound = convert_int_to_field_value(
            schema_info, vertex_type, field, interval.lower_bound
        )
    if interval.upper_bound is not None:
        upper_bound = convert_int_to_field_value(
            schema_info, vertex_type, field, interval.upper_bound
        )
    return Interval(lower_bound, upper_bound)


def get_field_value_intervals(
    schema_info: QueryPlanningSchemaInfo,
    query_metadata: QueryMetadataTable,
    parameters: Dict[str, Any],
) -> Dict[PropertyPath, Interval[Any]]:
    """Map the PropertyPath of each field in the query to its field value interval.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_metadata: representation of the query
        parameters: parameters used for the query

    Returns:
        Dict mapping some PropertyPaths to the interval of filtered values at that field.
    """
    field_value_intervals = {}
    for location, location_info in query_metadata.registered_locations:
        filter_infos = query_metadata.get_filter_infos(location)
        vertex_type_name = location_info.type.name

        # Group filters by field
        single_field_filters: Dict[str, List[FilterInfo]] = {}
        for filter_info in filter_infos:
            if len(filter_info.fields) == 0:
                raise AssertionError(f"Got filter on 0 fields {filter_info} on {vertex_type_name}")
            elif len(filter_info.fields) == 1:
                single_field_filters.setdefault(filter_info.fields[0], []).append(filter_info)
            else:
                pass  # We don't do anything for multi-field filters yet

        # Find field_value_interval for each field
        for field_name, filters_on_field in single_field_filters.items():
            integer_interval = get_integer_interval_for_filters_on_field(
                schema_info, filters_on_field, vertex_type_name, field_name, parameters
            )
            field_value_interval = _convert_int_interval_to_field_value_interval(
                schema_info, vertex_type_name, field_name, integer_interval
            )
            field_value_intervals[(location.query_path, field_name)] = field_value_interval
    return field_value_intervals


def get_distinct_result_set_estimates(
    schema_info: QueryPlanningSchemaInfo,
    query_metadata: QueryMetadataTable,
    parameters: Dict[str, Any],
) -> Dict[VertexPath, float]:
    """Map each VertexPath in the query to its distinct result set estimate.

    The distinct result set estimate for a query node is the expected number of different
    vertices that will appear under it in the result of the query.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_metadata: a representation of the query
        parameters: the query parameters

    Returns:
        the distinct result set estimate for each VertexPath
    """
    distinct_result_set_estimates = {}
    for location, location_info in query_metadata.registered_locations:
        vertex_type_name = location_info.type.name
        filter_infos = query_metadata.get_filter_infos(location)
        class_count = schema_info.statistics.get_class_count(vertex_type_name)
        distinct_result_set_estimates[location.query_path] = adjust_counts_for_filters(
            schema_info, filter_infos, parameters, vertex_type_name, class_count
        )

    # TODO(bojanserafimov): If there's a many-to-one edge from A to B in the query, the
    #                       distinct result set estimate for B cannot be greater than
    #                       the one for A. Taking this into account would make the results
    #                       more accurate.

    return distinct_result_set_estimates


def get_pagination_capacities(
    schema_info: QueryPlanningSchemaInfo,
    field_value_intervals: Dict[PropertyPath, Interval[Any]],
    distinct_result_set_estimates: Dict[VertexPath, float],
    query_metadata: QueryMetadataTable,
    parameters: Dict[str, Any],
) -> Dict[PropertyPath, float]:
    """Get the pagination capacity for each eligible pagination field.

    The pagination capacity of a field is defined as the maximum number of pages we can split
    the query results in by adding filters on this field with some confidence that the pages
    will have similar sizes. This reasoning is local: if a filter in a different location is
    correlated with the values on this field, the generated pages might turn out to have
    wildly different sizes. This problem is somewhat unavoidable.

    Args:
        schema_info: QueryPlanningSchemaInfo
        field_value_intervals: see get_field_value_intervals
        distinct_result_set_estimates: see get_distinct_result_set_estimates
        query_metadata: a representation of the query
        parameters: the query parameters

    Returns:
        The pagination capacity of each Property path
    """
    pagination_capacities = {}
    for location, location_info in query_metadata.registered_locations:
        vertex_type_name = location_info.type.name

        for field_name, _ in location_info.type.fields.items():
            key = (location.query_path, field_name)
            if not is_meta_field(field_name):
                if is_uuid4_type(schema_info, vertex_type_name, field_name):
                    pagination_capacities[key] = distinct_result_set_estimates[location.query_path]
                elif field_supports_range_reasoning(schema_info, vertex_type_name, field_name):
                    field_value_interval = field_value_intervals.get(key, Interval(None, None))
                    quantiles = schema_info.statistics.get_field_quantiles(
                        vertex_type_name, field_name
                    )
                    if quantiles is not None:

                        # Since we can't be sure the minimum observed value is the
                        # actual minimum value, we treat values less than it as part
                        # of the first quantile. Similarly, we treat values greater than the known
                        # maximum as part of the last quantile. That's why we drop the minimum and
                        # maximum observed values from the quantile list.
                        proper_quantiles = quantiles[1:-1]

                        # Get the relevant quantiles (ones inside the field_value_interval)
                        min_quantile = 0
                        max_quantile = len(proper_quantiles)
                        if field_value_interval.lower_bound is not None:
                            min_quantile = bisect.bisect_left(
                                proper_quantiles, field_value_interval.lower_bound
                            )
                        if field_value_interval.upper_bound is not None:
                            max_quantile = bisect.bisect_left(
                                proper_quantiles, field_value_interval.upper_bound
                            )
                        relevant_quantiles = proper_quantiles[min_quantile:max_quantile]

                        # TODO(bojanserafimov): If the relevant quantiles contain duplicates, the
                        #                       pagination capacity would be lower.

                        pagination_capacities[key] = min(
                            len(relevant_quantiles) + 1,
                            distinct_result_set_estimates[location.query_path],
                        )

    return pagination_capacities


@dataclass
class QueryPlanningAnalysis:
    """A cache for analysis passes over a fixed query and fixed schema_info."""

    schema_info: QueryPlanningSchemaInfo
    query: QueryStringWithParameters

    @cached_property
    def metadata_table(self):
        """Return the metadata table for this query."""
        return graphql_to_ir(
            self.schema_info.schema,
            self.query.query_string,
            type_equivalence_hints=self.schema_info.type_equivalence_hints,
        ).query_metadata_table

    @cached_property
    def cardinality_estimate(self) -> float:
        """Return the cardinality estimate for this query."""
        return estimate_query_result_cardinality(
            self.schema_info, self.query.query_string, self.query.parameters
        )

    @cached_property
    def field_value_intervals(self) -> Dict[PropertyPath, Interval[Any]]:
        """Return the field value intervals for this query."""
        return get_field_value_intervals(
            self.schema_info, self.metadata_table, self.query.parameters
        )

    @cached_property
    def distinct_result_set_estimates(self) -> Dict[VertexPath, float]:
        """Return the distinct result set estimates for this query."""
        return get_distinct_result_set_estimates(
            self.schema_info, self.metadata_table, self.query.parameters
        )

    @cached_property
    def pagination_capacities(self) -> Dict[PropertyPath, float]:
        """Return the pagination capacities for this query."""
        return get_pagination_capacities(
            self.schema_info,
            self.field_value_intervals,
            self.distinct_result_set_estimates,
            self.metadata_table,
            self.query.parameters,
        )
