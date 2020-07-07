# Copyright 2019-present Kensho Technologies, LLC.
from itertools import chain
from typing import Any, Dict

from ..compiler.helpers import (
    INBOUND_EDGE_DIRECTION,
    OUTBOUND_EDGE_DIRECTION,
    FoldScopeLocation,
    Location,
    get_edge_direction_and_name,
)
from ..compiler.metadata import QueryMetadataTable
from ..schema.schema_info import QueryPlanningSchemaInfo
from .filter_selectivity_utils import adjust_counts_for_filters


def _is_subexpansion_optional(query_metadata, parent_location, child_location):
    """Return True if child_location is the root of an optional subexpansion."""
    child_optional_depth = query_metadata.get_location_info(child_location).optional_scopes_depth
    parent_optional_depth = query_metadata.get_location_info(parent_location).optional_scopes_depth
    return child_optional_depth > parent_optional_depth


def _is_subexpansion_folded(location):
    """Return True if location is the root of a folded subexpansion."""
    return isinstance(location, FoldScopeLocation) and len(location.fold_path) == 1


def _is_subexpansion_recursive(query_metadata, parent_location, child_location):
    """Return True if child_location is the root of a recursive subexpansion."""
    edge_direction, edge_name = _get_last_edge_direction_and_name_to_location(child_location)
    for recurse_info in query_metadata.get_recurse_infos(parent_location):
        if recurse_info.edge_direction == edge_direction and recurse_info.edge_name == edge_name:
            return True
    return False


def _get_all_original_child_locations(query_metadata, start_location):
    """Get all original child Locations of a start Location and revisits to the start Location.

    Args:
        query_metadata: QueryMetadataTable object
        start_location: Location object, where we're looking for child Locations

    Returns:
        list of child Locations. Given start_location, get all revisits to start_location, then for
        all visits, get all child locations and return ones that are original visits.
    """
    child_locations = set()

    start_location_revisit_origin = [start_location]
    start_location_revisits = list(query_metadata.get_all_revisits(start_location))

    for location in chain(start_location_revisit_origin, start_location_revisits):
        for child_location in query_metadata.get_child_locations(location):
            child_location_revisit_origin = query_metadata.get_revisit_origin(child_location)
            if child_location_revisit_origin is None:
                # If child_location is not a revisit, set origin to child_location
                child_location_revisit_origin = child_location
            child_locations.add(child_location_revisit_origin)

    return list(child_locations)


def _get_last_edge_direction_and_name_to_location(location):
    """Get the direction and name of the last edge to a non-root BaseLocation object."""
    if isinstance(location, Location):
        edge_direction, edge_name = get_edge_direction_and_name(location.query_path[-1])
    elif isinstance(location, FoldScopeLocation):
        edge_direction, edge_name = location.fold_path[-1]
    else:
        raise AssertionError("Unexpected location encountered: {}".format(location))
    return edge_direction, edge_name


def _get_base_class_names_of_parent_and_child_from_edge(schema_graph, current_location):
    """Return the base class names of a location and its parent from last edge information."""
    edge_direction, edge_name = _get_last_edge_direction_and_name_to_location(current_location)
    edge_element = schema_graph.get_edge_schema_element_or_raise(edge_name)
    if edge_direction == INBOUND_EDGE_DIRECTION:
        parent_base_class_name = edge_element.base_out_connection
        child_base_class_name = edge_element.base_in_connection
    elif edge_direction == OUTBOUND_EDGE_DIRECTION:
        parent_base_class_name = edge_element.base_in_connection
        child_base_class_name = edge_element.base_out_connection
    else:
        raise AssertionError(
            "Expected edge direction to be either inbound or outbound."
            "Found: edge {} with direction {}".format(edge_name, edge_direction)
        )
    return parent_base_class_name, child_base_class_name


def _query_statistics_for_vertex_edge_vertex_count(
    statistics, query_metadata, parent_location, child_location
):
    """Query statistics for the count of edges connecting parent and child_location vertices.

    Given a parent location and a child location, there are three constraints on each edge directly
    connecting the two:
    1. The edge class must be the same as the target location's last traversed edge.
    2. The parent_location vertex class must inherit from the edge endpoint the traversal began at.
    3. The child_location vertex class must inherit from the edge endpoint the traversal ended at.
    Using get_vertex_edge_vertex_count(), we find the number of edges satisfying these three
    constraints.

    Args:
        statistics: Statistics object, used for querying over get_vertex_edge_vertex_count().
        query_metadata: QueryMetadataTable object.
        parent_location: BaseLocation, corresponding to the location the edge traversal begins from.
        child_location: BaseLocation, child of parent_location corresponding to the location the
                        edge traversal ends at.

    Returns:
        - int, count of edges connecting parent and child_location vertices if the statistic exists.
        - None otherwise.
    """
    edge_direction, edge_name = _get_last_edge_direction_and_name_to_location(child_location)
    parent_name_from_location = query_metadata.get_location_info(parent_location).type.name
    child_name_from_location = query_metadata.get_location_info(child_location).type.name

    # Since we need to provide the source vertex class and target vertex class in the same order
    # regardless of the direction of edge traversal, we first provide the class of the outbound
    # vertex (i.e. the vertex the edge starts from), then the class of the inbound vertex(i.e. the
    # vertex the edge ends at).
    if edge_direction == INBOUND_EDGE_DIRECTION:
        outbound_vertex_name = child_name_from_location
        inbound_vertex_name = parent_name_from_location
    elif edge_direction == OUTBOUND_EDGE_DIRECTION:
        outbound_vertex_name = parent_name_from_location
        inbound_vertex_name = child_name_from_location
    else:
        raise AssertionError(
            "Expected edge direction to be either inbound or outbound."
            "Found: edge {} with direction {}".format(edge_name, edge_direction)
        )

    query_result = statistics.get_vertex_edge_vertex_count(
        outbound_vertex_name, edge_name, inbound_vertex_name
    )
    return query_result


def _estimate_vertex_edge_vertex_count_using_class_count(
    schema_info, query_metadata, parent_location, child_location
):
    """Estimate the count of edges connecting parent_location and child_location vertices.

    Given a parent location of class A and a child location of class B, this function estimates the
    number of AB edges using class counts. If A and B are subclasses of the edge's endpoint classes
    (which we'll name C and D respectively), we only have statistics for CD edges. So estimates for
    the number of AB edges will be made using the assumption that CD edges are distributed
    independently of whether or not the vertex of class C is also of class A and likewise for D and
    B. In the general case, we estimate the statistic as
    (number of AB edges) = (number of CD edges) * (number of A vertices) / (number of C vertices) *
                                                  (number of B vertices) / (number of D vertices).

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_metadata: QueryMetadataTable object.
        parent_location: BaseLocation, corresponding to the location the edge traversal begins from.
        child_location: BaseLocation, child of parent_location corresponding to the location the
                        edge traversal ends at.

    Returns:
        float, estimate for number of edges connecting parent_location and child_location.
    """
    _, edge_name = _get_last_edge_direction_and_name_to_location(child_location)
    edge_counts = schema_info.statistics.get_class_count(edge_name)

    parent_name_from_location = query_metadata.get_location_info(parent_location).type.name
    child_name_from_location = query_metadata.get_location_info(child_location).type.name
    (
        parent_base_class_name,
        child_base_class_name,
    ) = _get_base_class_names_of_parent_and_child_from_edge(
        schema_info.schema_graph, child_location
    )

    # False-positive bug in pylint: https://github.com/PyCQA/pylint/issues/3039
    # pylint: disable=old-division
    #
    # Scale edge_counts if child_location's type is a subclass of the edge's endpoint type.
    if child_name_from_location != child_base_class_name:
        edge_counts *= float(
            schema_info.statistics.get_class_count(child_name_from_location)
        ) / schema_info.statistics.get_class_count(child_base_class_name)
    # Scale edge_counts if parent_location's type is a subclass of the edge's endpoint type.
    if parent_name_from_location != parent_base_class_name:
        edge_counts *= float(
            schema_info.statistics.get_class_count(parent_name_from_location)
        ) / schema_info.statistics.get_class_count(parent_base_class_name)
    # pylint: enable=old-division

    return edge_counts


def _estimate_edges_to_children_per_parent(
    schema_info, query_metadata, parameters, parent_location, child_location
):
    """Estimate the count of edges per parent_location that connect to child_location vertices.

    Given a parent location of type A and child location of type B, assume all AB edges are
    distributed evenly over A vertices, so the expected number of child edges per parent vertex is
    (number of AB edges) / (number of A vertices).

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_metadata: QueryMetadataTable object.
        parameters: dict, parameters with which query will be executed.
        parent_location: BaseLocation, corresponding to the location the edge traversal begins from.
        child_location: BaseLocation, child of parent_location corresponding to the location the
                        edge traversal ends at.

    Returns:
        float, expected number of edges per parent_location vertex that connect to child_location
        vertices.
    """
    edge_counts = _query_statistics_for_vertex_edge_vertex_count(
        schema_info.statistics, query_metadata, parent_location, child_location
    )

    if edge_counts is None:
        edge_counts = _estimate_vertex_edge_vertex_count_using_class_count(
            schema_info, query_metadata, parent_location, child_location
        )

    parent_name_from_location = query_metadata.get_location_info(parent_location).type.name
    # Count the number of parents, over which we assume the edges are uniformly distributed.
    parent_location_counts = schema_info.statistics.get_class_count(parent_name_from_location)

    # Anticipate division by zero
    if parent_location_counts == 0:
        # This implies that edge_counts is also 0. However, asserting that edge_counts is 0 is
        # too aggressive because we can't expect all statistics to be collected at the same time.
        return 0.0

    # False-positive bug in pylint: https://github.com/PyCQA/pylint/issues/3039
    # pylint: disable=old-division
    #
    # TODO(evan): edges are not necessarily uniformly distributed, so record more statistics
    child_counts_per_parent = float(edge_counts) / parent_location_counts
    # pylint: enable=old-division

    # TODO(evan): If edge is recursed over, we need a more detailed statistic
    # Recursion always starts with depth = 0, so we should treat the parent result set itself as a
    # child result set to be expanded (so add 1 to child_counts).
    is_recursive = _is_subexpansion_recursive(query_metadata, parent_location, child_location)
    if is_recursive:
        child_counts_per_parent += 1

    # Adjust the counts for filters at child_location.
    child_name_from_location = query_metadata.get_location_info(child_location).type.name
    child_filters = query_metadata.get_filter_infos(child_location)
    child_counts_per_parent = adjust_counts_for_filters(
        schema_info, child_filters, parameters, child_name_from_location, child_counts_per_parent
    )

    return child_counts_per_parent


def _estimate_subexpansion_cardinality(
    schema_info, query_metadata, parameters, parent_location, child_location
):
    """Estimate the cardinality associated with the subexpansion of a child_location vertex.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_metadata: QueryMetadataTable object
        parameters: dict, parameters with which query will be executed
        parent_location: BaseLocation object, location corresponding to the vertex being expanded
        child_location: BaseLocation object, child of parent_location corresponding to the
                        subexpansion root

    Returns:
        float, number of expected result sets found when a vertex corresponding to parent_location
        is expanded via child_location. For example, if parent_location (type A) has children (types
        B and C), the subexpansion results associated with the B-location are the result sets found
        when we expand an A-vertex over AB-edges and each subsequent B-vertex is fully expanded. We
        estimate this recursively as:
        (expected number of B-vertices) * (expected number of result sets per B-vertex).
    """
    child_counts_per_parent = _estimate_edges_to_children_per_parent(
        schema_info, query_metadata, parameters, parent_location, child_location
    )

    results_per_child = _estimate_expansion_cardinality(
        schema_info, query_metadata, parameters, child_location
    )

    subexpansion_cardinality = child_counts_per_parent * results_per_child

    # If child_location is the root of an optional or folded subexpansion, the empty result set will
    # be returned if no other result sets exist, so return at least 1.
    # TODO(evan): @filters on _x_count inside @folds can reduce result size.
    is_optional = _is_subexpansion_optional(query_metadata, parent_location, child_location)
    is_folded = _is_subexpansion_folded(child_location)
    if is_optional or is_folded:
        subexpansion_cardinality = max(subexpansion_cardinality, 1)

    return subexpansion_cardinality


def _estimate_expansion_cardinality(schema_info, query_metadata, parameters, current_location):
    """Estimate the cardinality of fully expanding a vertex corresponding to current_location.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_metadata: QueryMetadataTable object
        parameters: dict, parameters with which query will be executed
        current_location: BaseLocation object, corresponding to the vertex we're expanding

    Returns:
        float, expected cardinality associated with the full expansion of one current vertex.
    """
    expansion_cardinality = 1
    child_locations = _get_all_original_child_locations(query_metadata, current_location)
    for child_location in child_locations:
        # The expected cardinality per current vertex is the product of the expected cardinality for
        # each subexpansion (e.g. If we expect each current vertex to have 2 children of type A and
        # 3 children of type B, we'll return 6 distinct result sets per current vertex).
        subexpansion_cardinality = _estimate_subexpansion_cardinality(
            schema_info, query_metadata, parameters, current_location, child_location
        )
        expansion_cardinality *= subexpansion_cardinality
    return expansion_cardinality


def estimate_query_result_cardinality(
    schema_info: QueryPlanningSchemaInfo,
    query_metadata: QueryMetadataTable,
    parameters: Dict[str, Any],
) -> float:
    """Estimate the cardinality of a GraphQL query's result using database statistics.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_metadata: info on locations, inputs, outputs, and tags in the query
        parameters: dict, parameters with which query will be executed.

    Returns:
        float, expected query result cardinality. Equal to the number of root vertices multiplied by
        the expected number of result sets per full expansion of a root vertex.
    """
    root_location = query_metadata.root_location

    # First, count the vertices corresponding to the root location that pass relevant filters
    root_name = query_metadata.get_location_info(root_location).type.name
    root_counts = schema_info.statistics.get_class_count(root_name)
    root_counts = adjust_counts_for_filters(
        schema_info,
        query_metadata.get_filter_infos(root_location),
        parameters,
        root_name,
        root_counts,
    )

    # Next, find the number of expected result sets per root vertex when fully expanded
    results_per_root = _estimate_expansion_cardinality(
        schema_info, query_metadata, parameters, root_location
    )

    expected_query_result_cardinality = root_counts * results_per_root

    return expected_query_result_cardinality
