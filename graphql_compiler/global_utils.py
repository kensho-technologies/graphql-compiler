# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict
from itertools import chain

import six


def _get_vertices_in_reverse_topological_order(dag):
    """Return the vertices in the directed acyclic graph in reverse topological order.

    In other words, in the resulting iterable   , each vertex will appear after every vertex it has an
    edge to.

    Args:
        dag: dict, string -> set of strings, mapping each vertex in the directed acyclic graph to
             the set of vertices it has a directed edge to. This function does not regard
             reflexive edges as cycles.

    Returns:
        iterable of strings, representing the vertices in the directed acyclic graph in reverse
        topological order.
    """
    def traverse_vertex_subgraph(vertex_name, processed_vertices, current_trace):
        """Traverse a vertex and its edges recursively in a depth-first-search manner.

        Args:
            vertex_name: string, the name of the vertex whose subgraph is traversed.
            processed_vertices: set of strings, a set of vertices that have already been visited.
                                May be mutated by this function.
            current_trace: set of strings, set of vertices visited during the traversal.
                           May be mutated by this function.

        Returns:
            iterable of strings, representing the set of vertices that have been first visited in
            this traversal ordered in the reverse order in which they were visited.
        """
        if vertex_name in processed_vertices:
            return []

        if vertex_name in current_trace:
            raise AssertionError(
                'Encountered self-reference in dependency chain of {}'.format(vertex_name))

        vertices_in_reverse_topological_order = []

        current_trace.add(vertex_name)
        for adjacent_vertex_name in dag[vertex_name]:
            # Disregard reflexive edges.
            if adjacent_vertex_name != vertex_name:
                vertices_in_reverse_topological_order.extend(traverse_vertex_subgraph(
                    adjacent_vertex_name, processed_vertices, current_trace)
                )
        current_trace.remove(vertex_name)
        vertices_in_reverse_topological_order.append(vertex_name)
        processed_vertices.add(vertex_name)

        return vertices_in_reverse_topological_order

    return chain.from_iterable(
        traverse_vertex_subgraph(vertex_name, set(), set())
        for vertex_name in dag
    )


def get_transitive_closure(dag):
    """Return a dict representing the transitive closure of the directed acyclic graph.

    Used to compute the transitive subclass or superclass sets of classes in the GraphQL
    schema and the SchemaGraph.

    Args:
        dag: dict, string -> set of strings, mapping each vertex in the directed acyclic graph to
             the set of vertices it has a directed edge to. This function does not regard
             reflexive edges as cycles.

    Returns:
        dict, string -> frozenset of strings, representing the transitive closure of the directed
        acyclic graph.
    """
    transitive_closure = dict()
    for vertex_name in _get_vertices_in_reverse_topological_order(dag):
        adjacent_vertices = dag[vertex_name]
        transitive_closure[vertex_name] = set()
        transitive_closure[vertex_name].update(adjacent_vertices)
        transitive_closure[vertex_name].update(set(chain.from_iterable(
            transitive_closure[adjacent_vertex_name]
            for adjacent_vertex_name in adjacent_vertices
        )))
        transitive_closure[vertex_name] = frozenset(transitive_closure[vertex_name])
    return transitive_closure
