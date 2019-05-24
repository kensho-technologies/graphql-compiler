from itertools import chain

from ..compiler.compiler_frontend import graphql_to_ir
from ..compiler.helpers import FoldScopeLocation, Location, get_edge_direction_and_name
from ..schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from ..schema_generation.orientdb.schema_properties import (
    EDGE_DESTINATION_PROPERTY_NAME, EDGE_SOURCE_PROPERTY_NAME
)
from .filter_selectivity_utils import adjust_counts_for_filters


def _get_all_original_child_locations(query_metadata, start_location):
    """Get all original child Locations of a start Location and revisits to the start Location.

    Args:
        query_metadata: QueryMetadataTable object
        start_location: Location object, where we're looking for children

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
        raise AssertionError(u'Unexpected location encountered: {}'.format(location))
    return edge_direction, edge_name


def _estimate_child_edges_per_parent(
    schema_graph, lookup_class_counts, query_metadata, child_location
):
    """Estimate the number of edges per parent_location that connect to child_location vertices.

    Given a parent location of type A and child location of type B, assume that all AB edges are
    distributed evenly on A vertices, so the expected number of child edges per parent vertex is
    (# of AB edges) / (# of A vertices). If A and B are subclasses of C and D respectively, we only
    have access to CD edges, so in general, we'll use (# of CD edges) / (# of C vertices), but since
    we're only interested in edges to Bs, we'll scale this result by the fraction of Bs over Ds.

    Args:
        schema_graph: SchemaGraph object
        lookup_class_counts: function, string -> int, that accepts a class name and returns the
                             total number of instances plus subclass instances
        query_metadata: QueryMetadataTable object
        child_location: BaseLocation object

    Returns:
        float, expected number of child_location vertices connected to each parent_location vertex.
    """
    # Get direction and name of edge between parent and child location and its base endpoint names.
    edge_direction, edge_name = _get_last_edge_direction_and_name_to_location(child_location)
    edge_element = schema_graph.get_edge_schema_element_or_raise(edge_name)
    if edge_direction == EDGE_DESTINATION_PROPERTY_NAME:
        parent_name_from_edge = edge_element.base_out_connection
        child_name_from_edge = edge_element.base_in_connection
    elif edge_direction == EDGE_SOURCE_PROPERTY_NAME:
        parent_name_from_edge = edge_element.base_in_connection
        child_name_from_edge = edge_element.base_out_connection

    # TODO(evan): If edge is recursed over, we need a more detailed statistic
    edge_counts = lookup_class_counts(edge_name)

    # Scale edge_counts if child_location's type is a subclass of the edge's endpoint type.
    child_name_from_location = query_metadata.get_location_info(child_location).type.name
    if child_name_from_edge != child_name_from_location:
        edge_counts *= (
            float(lookup_class_counts(child_name_from_location)) /
            lookup_class_counts(child_name_from_edge)
        )

    parent_counts = lookup_class_counts(parent_name_from_edge)

    # TODO(evan): edges are not necessarily uniformly distributed, so record more statistics
    child_edges_per_parent = float(edge_counts) / parent_counts

    return child_edges_per_parent


def _is_subexpansion_optional(query_metadata, child_location, parent_location):
    """Return True if child_location is the root of an optional subexpansion."""
    child_optional_depth = query_metadata.get_location_info(child_location).optional_scopes_depth
    parent_optional_depth = query_metadata.get_location_info(parent_location).optional_scopes_depth
    return child_optional_depth > parent_optional_depth


def _is_subexpansion_folded(location):
    """Return True if location is the root of a folded subexpansion."""
    return isinstance(location, FoldScopeLocation) and len(location.fold_path) == 1


def _is_subexpansion_recursive(query_metadata, child_location, parent_location):
    """Return True if child_location is the root of a recursive subexpansion."""
    edge_direction, edge_name = _get_last_edge_direction_and_name_to_location(child_location)
    for recurse_info in query_metadata.get_recurse_infos(parent_location):
        if recurse_info.edge_direction == edge_direction and recurse_info.edge_name == edge_name:
            return True
    return False


def _estimate_subexpansion_results(
    schema_graph, lookup_class_counts, query_metadata, parameters, child_location, parent_location
):
    """Estimate the number of result sets in the subexpansion associated with child_location.

    Args:
        schema_graph: SchemaGraph object
        lookup_class_counts: function, string -> int, that accepts a class name and returns the
                             total number of instances plus subclass instances
        query_metadata: QueryMetadataTable object
        parameters: dict, parameters with which query will be executed
        child_location: BaseLocation object, child of parent_location corresponding to the
                        subexpansion root
        parent_location: BaseLocation object, location corresponding to the type of vertex being
                         expanded

    Returns:
        float, number of expected result sets found when a vertex corresponding to parent_location
        is expanded via child_location. For example, if parent_location (type A) has children (types
        B and C), the subexpansion results associated with the B-location are the result sets found
        when we expand an A-vertex over AB-edges and each subsequent B-vertex is fully expanded. We
        estimate this recursively as:
        (expected number of B-vertices) * (expected number of result sets per B-vertex).
    """
    child_counts = _estimate_child_edges_per_parent(
        schema_graph, lookup_class_counts, query_metadata, child_location
    )

    # Recursion always starts with depth = 0, so we should treat the parent result set itself as a
    # child result set to be expanded (so add 1 to child_counts).
    is_recursive = _is_subexpansion_recursive(query_metadata, child_location, parent_location)
    if is_recursive:
        child_counts += 1

    child_counts = adjust_counts_for_filters(
        schema_graph, lookup_class_counts, query_metadata.get_filter_infos(child_location),
        parameters, query_metadata.get_location_info(child_location).type.name, child_counts
    )

    results_per_child = 1
    grandchild_locations = _get_all_original_child_locations(query_metadata, child_location)
    for grandchild_location in grandchild_locations:
        subsubexpansion_results = _estimate_subexpansion_results(
            schema_graph, lookup_class_counts, query_metadata, parameters, grandchild_location,
            child_location
        )
        results_per_child *= subsubexpansion_results

    subexpansion_results = child_counts * results_per_child

    # If child_location is the root of an optional or folded subexpansion, the empty result set will
    # be returned if no other result sets exist, so return at least 1.
    # TODO(evan): @filters on _x_count inside @folds can reduce result size.
    is_optional = _is_subexpansion_optional(query_metadata, child_location, parent_location)
    is_folded = _is_subexpansion_folded(child_location)
    if is_optional or is_folded:
        subexpansion_results = max(subexpansion_results, 1)

    return subexpansion_results


def estimate_query_result_cardinality(
    schema_graph, lookup_class_counts, graphql_query, parameters,
    class_to_field_type_overrides=None, hidden_classes=None
):
    """Estimate the cardinality of a GraphQL query's result using database statistics.

    Args:
        schema_graph: SchemaGraph object
        lookup_class_counts: function, string -> int, that accepts a class name and returns the
                             total number of instances plus subclass instances
        graphql_query: string, a valid GraphQL query
        parameters: dict, parameters with which query will be executed
        class_to_field_type_overrides: optional dict, class name -> {field name -> field type},
                                       (string -> {string -> GraphQLType}). Used to override the
                                       type of a field in the class where it's first defined and all
                                       the class's subclasses.
        hidden_classes: optional set of strings, classes to not include in the GraphQL schema.

    Returns:
        float, expected query result cardinality. Equal to the number of root vertices multiplied by
        the expected number of result sets per full expansion of a root vertex.
    """
    # TODO(evan): replace lookup_class_counts with statistics class so we can use more stats
    if class_to_field_type_overrides is None:
        class_to_field_type_overrides = dict()
    if hidden_classes is None:
        hidden_classes = set()

    graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(
        schema_graph, class_to_field_type_overrides, hidden_classes
    )
    query_metadata = graphql_to_ir(
        graphql_schema, graphql_query, type_equivalence_hints=type_equivalence_hints
    ).query_metadata_table

    root_location = query_metadata.root_location

    # First, count the vertices corresponding to the root location that pass relevant filters
    root_name = query_metadata.get_location_info(root_location).type.name
    root_counts = lookup_class_counts(root_name)
    root_counts = adjust_counts_for_filters(
        schema_graph, lookup_class_counts, query_metadata.get_filter_infos(root_location),
        parameters, root_name, root_counts
    )

    # Next, find the number of expected result sets per root vertex when fully expanded
    results_per_root = 1
    child_locations = _get_all_original_child_locations(query_metadata, root_location)
    for child_location in child_locations:
        # The number of expected result sets found per root vertex is the product of the expected
        # result sets in each subexpansion (e.g. If we expect each root vertex to have 2 children of
        # type A and 3 children of type B, we'll return 6 distinct result sets per root vertex).
        subexpansion_results = _estimate_subexpansion_results(
            schema_graph, lookup_class_counts, query_metadata, parameters, child_location,
            root_location
        )
        results_per_root *= subexpansion_results

    expected_query_result_cardinality = root_counts * results_per_root

    return expected_query_result_cardinality
