from itertools import chain
from typing import Any, Dict, List, Set, cast

from ..compiler.helpers import BaseLocation, Location, get_edge_direction_and_name
from ..compiler.metadata import FilterInfo, QueryMetadataTable
from .typedefs import EdgeInfo, InterpreterHints, NeighborHint


def construct_hints_for_location(
    query_metadata_table: QueryMetadataTable,
    query_arguments: Dict[str, Any],
    location: BaseLocation,
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

    # TODO(predrag): Memoize and optimize this, it's inefficient.
    #                We can probably reuse most if not all of the hints object for a set location.
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
