from itertools import chain
from typing import Any, Dict, List, Set, Tuple, cast

from ..compiler.helpers import BaseLocation, Location, get_edge_direction_and_name
from ..compiler.metadata import FilterInfo, QueryMetadataTable
from .typedefs import EdgeInfo, InterpreterHints, NeighborHint


def construct_hints_for_location(
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    location: Location,
) -> InterpreterHints:
    result: InterpreterHints = {
        "runtime_arg_hints": dict(query_arguments),  # defensive copy
        "used_property_hints": frozenset(),
        "filter_hints": [],
        "neighbor_hints": [],
    }

    equivalent_locations: Set[BaseLocation] = {location}
    equivalent_locations.update(query_metadata_table.get_all_revisits(location))

    filter_hints: List[FilterInfo] = list(
        chain.from_iterable(
            query_metadata_table.get_filter_infos(equivalent_location)
            for equivalent_location in equivalent_locations
        )
    )

    used_properties: Set[str] = set()
    for _, info_object in chain(query_metadata_table.outputs, query_metadata_table.tags):
        used_location = info_object.location.at_vertex()
        used_property_field = info_object.location.field
        if used_location in equivalent_locations:
            if used_property_field is None:
                raise AssertionError(
                    f"Invalid location {used_location} without field component found in metadata "
                    f"object {info_object}. This should never happen, and is a bug."
                )
            used_properties.add(used_property_field)

    for filter_info in filter_hints:
        used_properties.update(filter_info.fields)

    neighbor_hints: List[Tuple[EdgeInfo, NeighborHint]] = []
    for equivalent_location in equivalent_locations:
        for child_location in query_metadata_table.get_child_locations(equivalent_location):
            if isinstance(child_location, Location):
                edge_info = cast(
                    # TODO(predrag): Refactor the code to make this cast unnecessary.
                    EdgeInfo,
                    get_edge_direction_and_name(child_location.query_path[-1]),
                )
                neighbor_hints.append((edge_info, None))
            else:
                # TODO(predrag): Fill this in once the interpreter supports folds.
                raise NotImplementedError(f"{child_location} is not supported.")

    result["filter_hints"] = filter_hints
    result["used_property_hints"] = frozenset(used_properties)
    result["neighbor_hints"] = neighbor_hints

    return result


def get_hints_for_location_via_readthrough_cache(
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    per_query_hint_cache: Dict[BaseLocation, InterpreterHints],
    location: BaseLocation,
) -> InterpreterHints:
    hints = per_query_hint_cache.get(location, None)
    if hints is None:
        if isinstance(location, Location):
            hints = construct_hints_for_location(query_metadata_table, query_arguments, location)
        else:
            # TODO(predrag): This will need to be updated when the interpreter supports @fold
            raise AssertionError(f"Unsupported location type: {location}")

        per_query_hint_cache[location] = hints

    return hints
