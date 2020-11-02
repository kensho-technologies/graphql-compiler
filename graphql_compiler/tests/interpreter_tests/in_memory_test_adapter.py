from itertools import chain, repeat
from typing import Any, Collection, Iterable, Mapping, Optional, Tuple

from ...compiler.helpers import get_parameter_name, is_runtime_parameter
from ...interpreter import DataContext, EdgeInfo, FilterInfo, InterpreterAdapter


vertices = {
    "Animal": [
        {"name": "Scooby Doo", "uuid": "1001", "__typename": "Animal"},
        {"name": "Hedwig", "uuid": "1002", "__typename": "Animal"},
        {"name": "Beethoven", "uuid": "1003", "__typename": "Animal"},
        # 101 Dalmatians and sequels
        {"name": "Pongo", "uuid": "1004", "__typename": "Animal"},
        {"name": "Perdy", "uuid": "1005", "__typename": "Animal"},
        {"name": "Dipstick", "uuid": "1006", "__typename": "Animal"},
        {"name": "Dottie", "uuid": "1007", "__typename": "Animal"},
        {"name": "Domino", "uuid": "1008", "__typename": "Animal"},
        {"name": "Little Dipper", "uuid": "1009", "__typename": "Animal"},
        {"name": "Oddball", "uuid": "1010", "__typename": "Animal"},
    ],
}
edges = {
    "Animal_ParentOf": [
        ("1004", "1006"),
        ("1005", "1006"),
        ("1006", "1008"),
        ("1006", "1009"),
        ("1006", "1010"),
        ("1007", "1008"),
        ("1007", "1009"),
        ("1007", "1010"),
    ],
}
subtypes_by_type = {
    "Animal": ["Animal"],
    "Entity": ["Entity", "Animal"],
    "UniquelyIdentifiable": ["UniquelyIdentifiable", "Animal"],
}
vertices_by_uuid = {vertex["uuid"]: vertex for vertex in chain.from_iterable(vertices.values())}


class InMemoryTestAdapter(InterpreterAdapter[dict]):
    """A simple adapter over in-memory data and the standard test schema.

    The DataToken type here is a simple dict() containing all the vertex data.
    """

    def get_tokens_of_type(
        self,
        type_name: str,
        runtime_arg_hints: Optional[Mapping[str, Any]] = None,
        filter_hints: Optional[Collection[FilterInfo]] = None,
        **hints: Any,
    ) -> Iterable[dict]:
        """Return an iterable of vertices of the given type."""
        equals_uuids: Optional[Collection[str]] = None
        if filter_hints is not None:
            for filter_hint in filter_hints:
                if filter_hint.fields == ("uuid",) and len(filter_hint.args) > 0:
                    first_argument = filter_hint.args[0]
                    if is_runtime_parameter(first_argument):
                        first_argument_name = get_parameter_name(first_argument)
                        if filter_hint.op_name == "=":
                            equals_uuids = [runtime_arg_hints[first_argument_name]]
                            break
                        elif filter_hint.op_name == "in_collection":
                            equals_uuids = runtime_arg_hints[first_argument_name]
                            break

        if equals_uuids is not None:
            # Use the provided hints to optimize loading vertices:
            # only yield vertices with matching uuids.
            expected_types = frozenset(subtypes_by_type.get(type_name, []))
            vertex: Optional[dict] = None
            for equals_uuid in equals_uuids:
                vertex = vertices_by_uuid.get(equals_uuid, None)
                if vertex["__typename"] not in expected_types:
                    # The vertex by that uuid exists, but is not of appropriate type to be returned.
                    vertex = None

                if vertex is not None:
                    yield vertex
        else:
            # We were not able to use hints, yield all vertices of the given type.
            for subtype_name in subtypes_by_type.get(type_name, []):
                # Vertex types without specified data have no instances, hence the .get() calls.
                yield from vertices.get(subtype_name, [])

    def project_property(
        self,
        data_contexts: Iterable[DataContext],
        current_type_name: str,
        field_name: str,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext, Any]]:
        """Look up and return the property value for each given DataContext."""
        for data_context in data_contexts:
            current_token = data_context.current_token
            current_value = (
                current_token.get(field_name, None)  # fields without specified data are None
                if current_token is not None
                else None
            )
            yield (data_context, current_value)

    def project_neighbors(
        self,
        data_contexts: Iterable[DataContext],
        current_type_name: str,
        edge_info: EdgeInfo,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext, Iterable[dict]]]:
        """Look up and return the neighbor tokens for the given edge of each DataContext."""
        direction, edge_name = edge_info
        edge_data = edges.get(edge_name, [])  # edge types without specified data have no instances

        for data_context in data_contexts:
            neighbor_tokens = []
            current_token = data_context.current_token
            if current_token is not None:
                uuid = current_token["uuid"]
                if direction == "out":
                    neighbor_tokens = [
                        vertices_by_uuid[destination_uuid]
                        for source_uuid, destination_uuid in edge_data
                        if source_uuid == uuid
                    ]
                elif direction == "in":
                    neighbor_tokens = [
                        vertices_by_uuid[source_uuid]
                        for source_uuid, destination_uuid in edge_data
                        if destination_uuid == uuid
                    ]
                else:
                    raise AssertionError()

            yield (data_context, neighbor_tokens)

    def can_coerce_to_type(
        self,
        data_contexts: Iterable[DataContext],
        current_type_name: str,
        coerce_to_type_name: str,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext, bool]]:
        """Return whether the specified type coercion may be performed on each DataContext."""
        return zip(data_contexts, repeat(False))  # there currently is no inheritance
