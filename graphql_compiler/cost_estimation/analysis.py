# Copyright 2019-present Kensho Technologies, LLC.
import bisect
from dataclasses import dataclass
from typing import Any, Dict, List

from cached_property import cached_property
from graphql.language.printer import print_ast

from ..ast_manipulation import safe_parse_graphql
from ..compiler.compiler_frontend import graphql_to_ir
from ..compiler.helpers import Location, get_edge_direction_and_name
from ..compiler.metadata import FilterInfo, QueryMetadataTable
from ..cost_estimation.cardinality_estimator import estimate_query_result_cardinality
from ..cost_estimation.int_value_conversion import (
    convert_int_to_field_value,
    field_supports_range_reasoning,
    is_uuid4_type,
)
from ..cost_estimation.interval import Interval
from ..global_utils import ASTWithParameters, PropertyPath, QueryStringWithParameters, VertexPath
from ..schema import is_meta_field
from ..schema.schema_info import EdgeConstraint, QueryPlanningSchemaInfo
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
    """Map the PropertyPath of each supported field with filters to its field value interval.

    This method only considers fields on which we have range reasoning
    (see field_supports_range_reasoning) that are not inside folds.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_metadata: info on locations, inputs, outputs, and tags in the query
        parameters: parameters used for the query

    Returns:
        dict mapping some PropertyPath objects to their interval of allowed values
    """
    field_value_intervals = {}
    for location, location_info in query_metadata.registered_locations:
        if not isinstance(location, Location):
            continue  # We don't paginate inside folds.

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
            if field_supports_range_reasoning(schema_info, vertex_type_name, field_name):
                integer_interval = get_integer_interval_for_filters_on_field(
                    schema_info, filters_on_field, vertex_type_name, field_name, parameters
                )
                field_value_interval = _convert_int_interval_to_field_value_interval(
                    schema_info, vertex_type_name, field_name, integer_interval
                )
                property_path = PropertyPath(location.query_path, field_name)
                field_value_intervals[property_path] = field_value_interval
    return field_value_intervals


def get_distinct_result_set_estimates(
    schema_info: QueryPlanningSchemaInfo,
    query_metadata: QueryMetadataTable,
    parameters: Dict[str, Any],
) -> Dict[VertexPath, float]:
    """Map each VertexPath in the query to its distinct result set estimate.

    VertexPaths that lead into a fold scope are omitted.

    The distinct result set estimate for vertex query node is the expected number of
    different instances of the vertex type that will appear in the result set of the
    query. For instance, suppose a query that included an edge traversal from A to B
    that also included a unique filter on A. In this case, the distinct result estimate
    for A is 1 even though the cardinality of the result set might be quite large.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_metadata: info on locations, inputs, outputs, and tags in the query
        parameters: the query parameters

    Returns:
        the distinct result set estimate for each VertexPath
    """
    distinct_result_set_estimates = {}
    for location, location_info in query_metadata.registered_locations:
        if not isinstance(location, Location):
            continue  # We don't paginate inside folds.
        vertex_type_name = location_info.type.name
        filter_infos = query_metadata.get_filter_infos(location)
        class_count = schema_info.statistics.get_class_count(vertex_type_name)
        distinct_result_set_estimates[location.query_path] = adjust_counts_for_filters(
            schema_info, filter_infos, parameters, vertex_type_name, class_count
        )

    single_destination_traversals = set()
    for location, _ in query_metadata.registered_locations:
        if not isinstance(location, Location):
            # TODO(bojanserafimov): We currently ignore FoldScopeLocations. However, a unique
            #                       filter on a FoldScopeLocation also uniquely filters the
            #                       enclosing scope.
            continue

        if len(location.query_path) > 1:
            from_path = location.query_path[:-1]
            to_path = location.query_path
            edge_direction, edge_name = get_edge_direction_and_name(location.query_path[-1])
            no_constraints = EdgeConstraint(0)  # unset all bits of the flag
            edge_constraints = schema_info.edge_constraints.get(edge_name, no_constraints)
            if edge_direction == "in":
                from_path, to_path = to_path, from_path

            if EdgeConstraint.AtMostOneDestination in edge_constraints:
                single_destination_traversals.add((from_path, to_path))
            if EdgeConstraint.AtMostOneSource in edge_constraints:
                single_destination_traversals.add((to_path, from_path))

    # Make sure there's no path of many-to-one traversals leading to a node with lower
    # distinct_result_set_estimate.
    max_path_length = len(single_destination_traversals)
    for _ in range(max_path_length):
        for from_path, to_path in single_destination_traversals:
            distinct_result_set_estimates[from_path] = min(
                distinct_result_set_estimates[from_path], distinct_result_set_estimates[to_path]
            )

    return distinct_result_set_estimates


def get_pagination_capacities(
    schema_info: QueryPlanningSchemaInfo,
    field_value_intervals: Dict[PropertyPath, Interval[Any]],
    distinct_result_set_estimates: Dict[VertexPath, float],
    query_metadata: QueryMetadataTable,
    parameters: Dict[str, Any],
) -> Dict[PropertyPath, int]:
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
        query_metadata: info on locations, inputs, outputs, and tags in the query
        parameters: the query parameters

    Returns:
        the pagination capacity of each PropertyPath
    """
    pagination_capacities = {}
    for location, location_info in query_metadata.registered_locations:
        vertex_type_name = location_info.type.name
        if not isinstance(location, Location):
            continue  # We don't paginate inside folds.

        for field_name, _ in location_info.type.fields.items():
            property_path = PropertyPath(location.query_path, field_name)
            if not is_meta_field(field_name):
                if is_uuid4_type(schema_info, vertex_type_name, field_name):
                    pagination_capacities[property_path] = int(
                        distinct_result_set_estimates[location.query_path]
                    )
                elif field_supports_range_reasoning(schema_info, vertex_type_name, field_name):
                    field_value_interval = field_value_intervals.get(
                        property_path, Interval(None, None)
                    )
                    quantiles = schema_info.statistics.get_field_quantiles(
                        vertex_type_name, field_name
                    )
                    if quantiles is not None:

                        # The first and last values of the quantiles are the minimum and maximum
                        # observed values. We call all other values the proper quantiles. We don't
                        # directly use the minimum and maximum values as page boundaries since we
                        # will most likely generate empty pages.
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

                        pagination_capacities[property_path] = min(
                            len(relevant_quantiles) + 1,
                            int(distinct_result_set_estimates[location.query_path]),
                        )

    return pagination_capacities


@dataclass
class QueryPlanningAnalysis:
    """A cache for analysis passes over a fixed query and fixed schema_info."""

    schema_info: QueryPlanningSchemaInfo
    ast_with_parameters: ASTWithParameters

    @cached_property
    def query_string_with_parameters(self):
        """Return the query in string form."""
        query_string = print_ast(self.ast_with_parameters.query_ast)
        return QueryStringWithParameters(query_string, self.ast_with_parameters.parameters)

    @cached_property
    def metadata_table(self):
        """Return the metadata table for this query."""
        return graphql_to_ir(
            self.schema_info.schema,
            self.query_string_with_parameters.query_string,
            type_equivalence_hints=self.schema_info.type_equivalence_hints,
        ).query_metadata_table

    @cached_property
    def cardinality_estimate(self) -> float:
        """Return the cardinality estimate for this query."""
        return estimate_query_result_cardinality(
            self.schema_info, self.metadata_table, self.ast_with_parameters.parameters
        )

    @cached_property
    def field_value_intervals(self) -> Dict[PropertyPath, Interval[Any]]:
        """Return the field value intervals for this query."""
        return get_field_value_intervals(
            self.schema_info, self.metadata_table, self.ast_with_parameters.parameters
        )

    @cached_property
    def distinct_result_set_estimates(self) -> Dict[VertexPath, float]:
        """Return the distinct result set estimates for this query."""
        return get_distinct_result_set_estimates(
            self.schema_info, self.metadata_table, self.ast_with_parameters.parameters
        )

    @cached_property
    def pagination_capacities(self) -> Dict[PropertyPath, int]:
        """Return the pagination capacities for this query."""
        return get_pagination_capacities(
            self.schema_info,
            self.field_value_intervals,
            self.distinct_result_set_estimates,
            self.metadata_table,
            self.ast_with_parameters.parameters,
        )


def analyze_query_string(
    schema_info: QueryPlanningSchemaInfo, query: QueryStringWithParameters
) -> QueryPlanningAnalysis:
    """Create a QueryPlanningAnalysis object for the given query."""
    query_ast = safe_parse_graphql(query.query_string)
    return QueryPlanningAnalysis(schema_info, ASTWithParameters(query_ast, query.parameters))
