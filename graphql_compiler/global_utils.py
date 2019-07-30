# Copyright 2019-present Kensho Technologies, LLC.
import six
from itertools import chain
from collections import OrderedDict


def _get_dag_with_keys_in_reverse_topological_order(dag):
    """Return an OrderedDict representing a DAG with keys ordered in reversed topological order.

    Args:
        dag: dict, string -> set of strings, mapping each vertex in the directed acyclic graph to
             the set of vertices it has a directed edge to.

    Returns:
        OrderedDict, str -> str, representing a directed acyclic graph (DAG) with keys ordered in
        reversed topological order.
    """
    def traverse_vertex_subgraph(vertex_name, processed_vertices, current_trace):
        """Transverse a vertex and its edges recursively in a depth-first-search manner.

        Args:
            vertex_name: string, the name of the vertex whose subgraph is transversed.
            processed_vertices: set of strings, a set of vertices that have already been visited.
                                May be mutated by this function.
            current_trace: list of strings, list of vertices visited during the traversal.
                           May be mutated by this function.

        Returns:
            list of strings, representing the set of vertices that have been visited first in this
            traversal ordered in the reverse order they were visited.
        """
        if vertex_name in processed_vertices:
            return []

        if vertex_name in current_trace:
            raise AssertionError(
                'Encountered self-reference in dependency chain of {}'.format(vertex_name))

        vertex_list = []

        current_trace.add(vertex_name)
        for adjacent_vertex_name in dag[vertex_name]:
            vertex_list.extend(traverse_vertex_subgraph(
                adjacent_vertex_name, processed_vertices, current_trace)
            )
        current_trace.remove(vertex_name)
        vertex_list.append(vertex_name)
        processed_vertices.add(vertex_name)

        return vertex_list

    toposorted = []
    for name in dag.keys():
        toposorted.extend(traverse_vertex_subgraph(name, set(), set()))
    return OrderedDict((class_name, dag[class_name])
                       for class_name in toposorted)


def get_transitive_closure(dag):
    """Return a dict representing the transitive closure of the directed acyclic graph.

    Used to compute the transitive subclass or superclass sets of classes in the GraphQL
    schema and the SchemaGraph.

    Args:
        dag: dict, string -> set of strings, mapping each vertex in the directed acyclic graph to
        the set of vertices it has a directed edge to.

    Returns:
        dict, string -> set of strings, representing the transitive closure of the directed
        acyclic graph.
    """
    reversed_toposorted_dag = _get_dag_with_keys_in_reverse_topological_order(dag)
    print(reversed_toposorted_dag)
    transitive_closure = dict()
    for vertex_name, adjacent_vertices in six.iteritems(reversed_toposorted_dag):
        transitive_closure[vertex_name] = set(chain.from_iterable(
            transitive_closure[adjacent_vertex_name]
            for adjacent_vertex_name in adjacent_vertices
        ))
    return transitive_closure
