from itertools import chain, repeat
from typing import Any, Iterable, Tuple

from ...interpreter import DataContext, EdgeInfo, InterpreterAdapter


vertices = {
    'Animal': [
        {'name': 'Scooby Doo', 'uuid': '1001'},
        {'name': 'Hedwig', 'uuid': '1002'},
        {'name': 'Beethoven', 'uuid': '1003'},

        # 101 Dalmatians and sequels
        {'name': 'Pongo', 'uuid': '1004'},
        {'name': 'Perdy', 'uuid': '1005'},
        {'name': 'Dipstick', 'uuid': '1006'},
        {'name': 'Dottie', 'uuid': '1007'},
        {'name': 'Domino', 'uuid': '1008'},
        {'name': 'Little Dipper', 'uuid': '1009'},
        {'name': 'Oddball', 'uuid': '1010'},
    ],
}
edges = {
    'Animal_ParentOf': [
        ('1004', '1006'),
        ('1005', '1006'),
        ('1006', '1008'),
        ('1006', '1009'),
        ('1006', '1010'),
        ('1007', '1008'),
        ('1007', '1009'),
        ('1007', '1010'),
    ],
}
vertices_by_uuid = {
    vertex['uuid']: vertex
    for vertex in chain.from_iterable(vertices.values())
}


class InMemoryTestAdapter(InterpreterAdapter[dict]):
    """A simple adapter over in-memory data and the standard test schema.

    The DataToken type here is a simple dict() containing all the vertex data.
    """

    def get_tokens_of_type(
        self,
        type_name: str,
        **hints,
    ) -> Iterable[dict]:
        """Return an iterable of vertices of the given type."""
        return vertices.get(type_name, [])  # vertex types without specified data have no instances

    def project_property(
        self,
        data_contexts: Iterable[DataContext],
        current_type_name: str,
        field_name: str,
        **hints,
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
        **hints,
    ) -> Iterable[Tuple[DataContext, Iterable[dict]]]:
        """Look up and return the neighbor tokens for the given edge of each DataContext."""
        direction, edge_name = edge_info
        edge_data = edges.get(edge_name, [])  # edge types without specified data have no instances

        for data_context in data_contexts:
            neighbor_tokens = []
            current_token = data_context.current_token
            if current_token is not None:
                uuid = current_token['uuid']
                if direction == 'out':
                    neighbor_tokens = [
                        vertices_by_uuid[destination_uuid]
                        for source_uuid, destination_uuid in edge_data
                        if source_uuid == uuid
                    ]
                elif direction == 'in':
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
        **hints,
    ) -> Iterable[Tuple[DataContext, bool]]:
        """Return whether the specified type coercion may be performed on each DataContext."""
        return zip(data_contexts, repeat(False))  # there currently is no inheritance
