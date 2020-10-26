# Copyright 2019-present Kensho Technologies, LLC.
import bisect
from dataclasses import dataclass
from typing import Any, Dict, Set, Union

from graphql import GraphQLInterfaceType, GraphQLObjectType

from ..compiler.compiler_frontend import ast_to_ir
from ..compiler.helpers import (
    BaseLocation,
    FoldScopeLocation,
    Location,
    get_edge_direction_and_name,
)
from ..compiler.metadata import FilterInfo, QueryMetadataTable
from ..cost_estimation.cardinality_estimator import estimate_query_result_cardinality
from ..cost_estimation.int_value_conversion import (
    convert_int_to_field_value,
    field_supports_range_reasoning,
)
from ..cost_estimation.interval import Interval
from ..global_utils import (
    ASTWithParameters,
    PropertyPath,
    QueryStringWithParameters,
    VertexPath,
    cached_property,
)
from ..query_formatting.common import validate_arguments
from ..schema import is_meta_field
from ..schema.schema_info import EdgeConstraint, QueryPlanningSchemaInfo
from .filter_selectivity_utils import (
    Selectivity,
    adjust_counts_with_selectivity,
    filter_uses_only_runtime_parameters,
    get_integer_interval_for_filters_on_field,
    get_selectivity_of_filters_at_vertex,
)
from .helpers import is_uuid4_type


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


def _get_location_vertex_path(location: BaseLocation) -> VertexPath:
    """Get the VertexPath for a BaseLocation pointing at a vertex."""
    if location.field is not None:
        raise AssertionError(
            f"Location {location} represents a field. Expected a location pointing at a vertex."
        )

    if isinstance(location, Location):
        return location.query_path
    elif isinstance(location, FoldScopeLocation):
        return location.base_location.query_path + tuple(
            "{}_{}".format(direction, name) for direction, name in location.fold_path
        )
    raise AssertionError("Unexpected location encountered: {}".format(location))


def get_types(
    query_metadata: QueryMetadataTable,
) -> Dict[VertexPath, Union[GraphQLObjectType, GraphQLInterfaceType]]:
    """Find the type at each VertexPath.

    Fold scopes are not considered.

    Args:
        query_metadata: info on locations, inputs, outputs, and tags in the query

    Returns:
        dict mapping nodes to their type names
    """
    location_types = {}
    for location, location_info in query_metadata.registered_locations:
        location_types[_get_location_vertex_path(location)] = location_info.type
    return location_types


def get_filters(query_metadata: QueryMetadataTable) -> Dict[VertexPath, Set[FilterInfo]]:
    """Get the filters at each VertexPath."""
    filters: Dict[VertexPath, Set[FilterInfo]] = {}
    for location, _ in query_metadata.registered_locations:
        filter_infos = query_metadata.get_filter_infos(location)
        filters.setdefault(_get_location_vertex_path(location), set()).update(filter_infos)

    return filters


def get_fold_scope_roots(query_metadata: QueryMetadataTable) -> Dict[VertexPath, VertexPath]:
    """Map each VertexPath in the query that's inside a fold to the VertexPath of the fold."""
    fold_scope_roots: Dict[VertexPath, VertexPath] = {}
    for location, _ in query_metadata.registered_locations:
        if isinstance(location, FoldScopeLocation):
            fold_scope_roots[
                _get_location_vertex_path(location)
            ] = location.base_location.query_path
    return fold_scope_roots


def get_single_field_filters(
    filters: Dict[VertexPath, Set[FilterInfo]],
) -> Dict[PropertyPath, Set[FilterInfo]]:
    """Find the single field filters for each field.

    Filters that apply to multiple fields, like name_or_alias, are ignored.

    Args:
        filters: the set of filters at each node

    Returns:
        dict mapping fields to their set of filters.
    """
    single_field_filters = {}
    for vertex_path, filter_infos in filters.items():
        # Group filters by field
        single_field_filters_for_vertex: Dict[str, Set[FilterInfo]] = {}
        for filter_info in filter_infos:
            if len(filter_info.fields) == 0:
                raise AssertionError(f"Got filter on 0 fields {filter_info} on {vertex_path}")
            elif len(filter_info.fields) == 1:
                single_field_filters_for_vertex.setdefault(filter_info.fields[0], set()).add(
                    filter_info
                )
            else:
                pass

        for field_name, field_filters in single_field_filters_for_vertex.items():
            property_path = PropertyPath(vertex_path, field_name)
            single_field_filters[property_path] = field_filters

    return single_field_filters


def get_fields_eligible_for_pagination(
    schema_info: QueryPlanningSchemaInfo,
    types: Dict[VertexPath, Union[GraphQLObjectType, GraphQLInterfaceType]],
    single_field_filters: Dict[PropertyPath, Set[FilterInfo]],
    fold_scope_roots: Dict[VertexPath, VertexPath],
) -> Set[PropertyPath]:
    """Return all the fields we can consider for pagination."""
    fields_eligible_for_pagination = set()
    for vertex_path, vertex_type in types.items():
        vertex_type_name = vertex_type.name
        if vertex_path in fold_scope_roots:
            continue
        for field_name, _ in vertex_type.fields.items():
            property_path = PropertyPath(vertex_path, field_name)
            filters: Set[FilterInfo] = single_field_filters.get(property_path, set())
            eligible_for_pagination = True
            if not field_supports_range_reasoning(schema_info, vertex_type_name, field_name):
                eligible_for_pagination = False
            for filter_info in filters:
                if not filter_uses_only_runtime_parameters(filter_info):
                    eligible_for_pagination = False
            if is_meta_field(field_name):
                eligible_for_pagination = False
            if eligible_for_pagination:
                fields_eligible_for_pagination.add(property_path)

    return fields_eligible_for_pagination


def get_field_value_intervals(
    schema_info: QueryPlanningSchemaInfo,
    types: Dict[VertexPath, Union[GraphQLObjectType, GraphQLInterfaceType]],
    single_field_filters: Dict[PropertyPath, Set[FilterInfo]],
    parameters: Dict[str, Any],
) -> Dict[PropertyPath, Interval[Any]]:
    """Map the PropertyPath of each supported field with filters to its field value interval.

    This method only considers fields on which we have range reasoning
    (see field_supports_range_reasoning) that are not inside folds.

    Args:
        schema_info: QueryPlanningSchemaInfo
        types: the type at each node
        single_field_filters: the set of filters at each node
        parameters: parameters used for the query

    Returns:
        dict mapping some PropertyPath objects to their interval of allowed values
    """
    field_value_intervals = {}
    for vertex_path, vertex_type in types.items():
        vertex_type_name = vertex_type.name
        for field_name, _ in vertex_type.fields.items():
            property_path = PropertyPath(vertex_path, field_name)
            filters_on_field: Set[FilterInfo] = single_field_filters.get(property_path, set())
            if not filters_on_field:
                continue

            if field_supports_range_reasoning(schema_info, vertex_type_name, field_name):
                integer_interval = get_integer_interval_for_filters_on_field(
                    schema_info, filters_on_field, vertex_type_name, field_name, parameters
                )
                field_value_interval = _convert_int_interval_to_field_value_interval(
                    schema_info, vertex_type_name, field_name, integer_interval
                )
                property_path = PropertyPath(vertex_path, field_name)
                field_value_intervals[property_path] = field_value_interval
    return field_value_intervals


def get_selectivities(
    schema_info: QueryPlanningSchemaInfo,
    types: Dict[VertexPath, Union[GraphQLObjectType, GraphQLInterfaceType]],
    filters: Dict[VertexPath, Set[FilterInfo]],
    parameters: Dict[str, Any],
) -> Dict[VertexPath, Selectivity]:
    """Get the combined selectivities of filters at each vertex."""
    selectivities = {}
    for vertex_path, vertex_type in types.items():
        vertex_type_name = vertex_type.name
        filter_infos = filters[vertex_path]
        # TODO(bojanserafimov) use precomputed field_value_intervals
        #                      inside this method instead of recomputing it
        selectivity = get_selectivity_of_filters_at_vertex(
            schema_info, filter_infos, parameters, vertex_type_name
        )
        selectivities[vertex_path] = selectivity
    return selectivities


def get_distinct_result_set_estimates(
    schema_info: QueryPlanningSchemaInfo,
    types: Dict[VertexPath, Union[GraphQLObjectType, GraphQLInterfaceType]],
    selectivities: Dict[VertexPath, Selectivity],
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
        types: the type at each node
        selectivities: the selectivities at each VertexPath
        parameters: the query parameters

    Returns:
        the distinct result set estimate for each VertexPath
    """
    distinct_result_set_estimates = {}
    for vertex_path, vertex_type in types.items():
        vertex_type_name = vertex_type.name
        class_count = schema_info.statistics.get_class_count(vertex_type_name)
        distinct_result_set_estimates[vertex_path] = adjust_counts_with_selectivity(
            class_count, selectivities[vertex_path]
        )

    single_destination_traversals = set()
    for vertex_path, _ in types.items():
        if len(vertex_path) > 1:
            from_path = vertex_path[:-1]
            to_path = vertex_path
            edge_direction, edge_name = get_edge_direction_and_name(vertex_path[-1])
            no_constraints = EdgeConstraint(0)  # unset all bits of the flag
            edge_constraints = schema_info.edge_constraints.get(edge_name, no_constraints)
            if edge_direction == "in":
                from_path, to_path = to_path, from_path

            if EdgeConstraint.AtMostOneDestination in edge_constraints:
                single_destination_traversals.add((from_path, to_path))
            if EdgeConstraint.AtMostOneSource in edge_constraints:
                single_destination_traversals.add((to_path, from_path))

    # Make sure there's no path of many-to-one traversals leading to a node with higher
    # distinct_result_set_estimate.
    max_path_length = len(single_destination_traversals)
    for _ in range(max_path_length):
        for from_path, to_path in single_destination_traversals:
            distinct_result_set_estimates[to_path] = min(
                distinct_result_set_estimates[to_path], distinct_result_set_estimates[from_path]
            )

    return distinct_result_set_estimates


def get_pagination_capacities(
    schema_info: QueryPlanningSchemaInfo,
    types: Dict[VertexPath, Union[GraphQLObjectType, GraphQLInterfaceType]],
    fields_eligible_for_pagination: Set[PropertyPath],
    field_value_intervals: Dict[PropertyPath, Interval[Any]],
    distinct_result_set_estimates: Dict[VertexPath, float],
) -> Dict[PropertyPath, int]:
    """Get the pagination capacity for each eligible pagination field.

    The pagination capacity of a field is defined as the maximum number of pages we can split
    the query results in by adding filters on this field with some confidence that the pages
    will have similar sizes. This reasoning is local: if a filter in a different location is
    correlated with the values on this field, the generated pages might turn out to have
    wildly different sizes. This problem is somewhat unavoidable.

    Args:
        schema_info: QueryPlanningSchemaInfo
        types: the type at each node
        field_value_intervals: see get_field_value_intervals
        distinct_result_set_estimates: see get_distinct_result_set_estimates

    Returns:
        the pagination capacity of each PropertyPath
    """
    pagination_capacities = {}
    for vertex_path, vertex_type in types.items():
        vertex_type_name = vertex_type.name
        for field_name, _ in vertex_type.fields.items():
            property_path = PropertyPath(vertex_path, field_name)
            if property_path not in fields_eligible_for_pagination:
                continue

            if is_uuid4_type(schema_info, vertex_type_name, field_name):
                pagination_capacities[property_path] = int(
                    distinct_result_set_estimates[vertex_path]
                )
            elif field_supports_range_reasoning(schema_info, vertex_type_name, field_name):
                field_value_interval = field_value_intervals.get(
                    property_path, Interval(None, None)
                )
                quantiles = schema_info.statistics.get_field_quantiles(vertex_type_name, field_name)
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
                        int(distinct_result_set_estimates[vertex_path]),
                    )

    return pagination_capacities


@dataclass
class QueryPlanningAnalysis:
    """A cache for analysis passes over a fixed query and fixed schema_info."""

    schema_info: QueryPlanningSchemaInfo
    ast_with_parameters: ASTWithParameters

    @cached_property
    def query_string_with_parameters(self) -> QueryStringWithParameters:
        """Return the query in string form."""
        return QueryStringWithParameters.from_ast_with_parameters(self.ast_with_parameters)

    @cached_property
    def metadata_table(self) -> QueryMetadataTable:
        """Return the metadata table for this query."""
        ir_and_metadata = ast_to_ir(
            self.schema_info.schema,
            self.ast_with_parameters.query_ast,
            type_equivalence_hints=self.schema_info.type_equivalence_hints,
        )
        validate_arguments(ir_and_metadata.input_metadata, self.ast_with_parameters.parameters)
        return ir_and_metadata.query_metadata_table

    @cached_property
    def types(self) -> Dict[VertexPath, Union[GraphQLObjectType, GraphQLInterfaceType]]:
        """Find the type at each VertexPath."""
        return get_types(self.metadata_table)

    @cached_property
    def classes_with_missing_counts(self) -> Set[str]:
        """Return classes that don't have count statistics."""
        classes_with_missing_counts = set()
        for vertex_path, vertex_type in self.types.items():
            if self.schema_info.statistics.get_class_count(vertex_type.name) is None:
                classes_with_missing_counts.add(vertex_type.name)
            if len(vertex_path) > 1:
                _, edge_name = get_edge_direction_and_name(vertex_path[-1])
                if self.schema_info.statistics.get_class_count(edge_name) is None:
                    classes_with_missing_counts.add(edge_name)
        return classes_with_missing_counts

    @cached_property
    def cardinality_estimate(self) -> float:
        """Return the cardinality estimate for this query."""
        # TODO use selectivity analysis pass instead of recomputing it
        return estimate_query_result_cardinality(
            self.schema_info, self.metadata_table, self.ast_with_parameters.parameters
        )

    @cached_property
    def filters(self) -> Dict[VertexPath, Set[FilterInfo]]:
        """Get the filters at each VertexPath."""
        return get_filters(self.metadata_table)

    @cached_property
    def fold_scope_roots(self) -> Dict[VertexPath, VertexPath]:
        """Map each VertexPath in the query that's inside a fold to the VertexPath of the fold."""
        return get_fold_scope_roots(self.metadata_table)

    @cached_property
    def single_field_filters(self) -> Dict[PropertyPath, Set[FilterInfo]]:
        """Find the single field filters for each field. Filters like name_or_alias are excluded."""
        return get_single_field_filters(self.filters)

    @cached_property
    def fields_eligible_for_pagination(self) -> Set[PropertyPath]:
        """Return all the fields we can consider for pagination."""
        return get_fields_eligible_for_pagination(
            self.schema_info,
            self.types,
            self.single_field_filters,
            self.fold_scope_roots,
        )

    @cached_property
    def field_value_intervals(self) -> Dict[PropertyPath, Interval[Any]]:
        """Return the field value intervals for this query."""
        return get_field_value_intervals(
            self.schema_info,
            self.types,
            self.single_field_filters,
            self.ast_with_parameters.parameters,
        )

    @cached_property
    def selectivities(self) -> Dict[VertexPath, Selectivity]:
        """Get the combined selectivities of filters at each vertex."""
        return get_selectivities(
            self.schema_info, self.types, self.filters, self.ast_with_parameters.parameters
        )

    @cached_property
    def distinct_result_set_estimates(self) -> Dict[VertexPath, float]:
        """Return the distinct result set estimates for this query."""
        return get_distinct_result_set_estimates(
            self.schema_info, self.types, self.selectivities, self.ast_with_parameters.parameters
        )

    @cached_property
    def pagination_capacities(self) -> Dict[PropertyPath, int]:
        """Return the pagination capacities for this query."""
        return get_pagination_capacities(
            self.schema_info,
            self.types,
            self.fields_eligible_for_pagination,
            self.field_value_intervals,
            self.distinct_result_set_estimates,
        )


def analyze_query_string(
    schema_info: QueryPlanningSchemaInfo, query_with_params: QueryStringWithParameters
) -> QueryPlanningAnalysis:
    """Create a QueryPlanningAnalysis object for the given query string and parameters."""
    ast_with_params = ASTWithParameters.from_query_string_with_parameters(query_with_params)
    return analyze_query_ast(schema_info, ast_with_params)


def analyze_query_ast(
    schema_info: QueryPlanningSchemaInfo, ast_with_params: ASTWithParameters
) -> QueryPlanningAnalysis:
    """Create a QueryPlanningAnalysis object for the given query AST and parameters."""
    # This function exists for the sake of parity with "analyze_query_string()" as
    # the analysis operations in question work just as well over ASTs as over query strings.
    # Even though this function is just a proxy for the QueryPlanningAnalysis constructor,
    # this is not something that would be obvious to the reader. What we are trying to avoid
    # is a situation where someone doesn't realize QueryPlanningAnalysis can be made from an AST,
    # so they print the AST into a query string, only to parse it again with analyze_query_string().
    return QueryPlanningAnalysis(schema_info, ast_with_params)
