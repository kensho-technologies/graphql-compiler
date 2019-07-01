# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod

import six


@six.python_2_unicode_compatible
@six.add_metaclass(ABCMeta)
class Statistics(object):
    """Abstract class for statistics regarding GraphQL objects.

    For the purposes of query cardinality estimation, we need statistics to provide better
    cardinality estimates when operations like edge traversal or @filter directives are used.
    All statistics except get_class_count() are optional, so if the statistic doesn't exist, a
    value of None should be returned.
    """
    def __str__(self):
        """Return a human-readable unicode representation of the Statistics object."""
        raise NotImplementedError()

    def __repr__(self):
        """Return a human-readable str representation of the CompilerEntity object."""
        return self.__str__()

    @abstractmethod
    def get_class_count(self, class_name):
        """Return how many vertex or edge instances have, or inherit, the given class name.

        Args:
            class_name: str, either a vertex class name or an edge class name defined in the
                        GraphQL schema.

        Returns:
            - int, the count of vertex or edge instances with, or inheriting the given class name

        Raises:
            AssertionError, if statistic for the given vertex/edge class does not exist.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_edge_count_between_vertex_pair(
        self, vertex_source_class_name, edge_class_name, vertex_target_class_name
    ):
        """Return the count of edges connecting two vertices.

        This statistic is optional, as the estimator can roughly predict this cost using
        get_class_count(). In some cases of traversal between two vertices using an edge connecting
        the vertices' superclasses, the estimates generated using get_class_count() may be off by
        several orders of magnitude. In such cases, this statistic should be provided.

        Args:
            vertex_source_class_name: str, vertex class name.
            edge_class_name: str, edge class name.
            vertex_target_class_name: str, vertex class name.

        Returns:
            - int, the count of edges if the statistic exists
            - None otherwise
        """
        return None


class LocalStatistics(Statistics):
    """Provides statistics using ones given at initialization."""
    def __init__(self, class_counts, *, edge_count_between_vertex_pairs=None):
        """Initializes statistics with the given data.

        Args:
            class_counts: dict, str -> int, mapping vertex/edge class name to class count.
            edge_count_between_vertex_pairs: optional dict, (str, str, str) -> int, mapping
                tuple of (vertex source class name, edge class name, vertex target class name) to
                count of edge instances of given class connecting instances of two vertex classes.
        """
        if edge_count_between_vertex_pairs is None:
            edge_count_between_vertex_pairs = dict()

        self._class_counts = class_counts
        self._edge_count_between_vertex_pairs = edge_count_between_vertex_pairs

    def get_class_count(self, class_name):
        """Return how many vertex or edge instances have, or inherit, the given class name.

        Args:
            class_name: str, either a vertex class name or an edge class name defined in the
                        GraphQL schema.

        Returns:
            - int, the count of vertex or edge instances with, or inheriting the given class name

        Raises:
            AssertionError, if statistic for the given vertex/edge class does not exist.
        """
        if class_name not in self._class_counts:
            raise AssertionError(u'Class count statistic is required, but entry not found for: '
                                 u'{}'.format(class_name))
        return self._class_counts[class_name]

    def get_edge_count_between_vertex_pair(
        self, vertex_source_class_name, edge_class_name, vertex_target_class_name
    ):
        """Return the count of edges connecting two vertices.

        This statistic is optional, as the estimator can roughly predict this cost using
        get_class_count(). In some cases of traversal between two vertices using an edge connecting
        the vertices' superclasses, the estimates generated using get_class_count() may be off by
        several orders of magnitude. In such cases, this statistic should be provided.

        Args:
            vertex_source_class_name: str, vertex class name.
            edge_class_name: str, edge class name.
            vertex_target_class_name: str, vertex class name.

        Returns:
            - int, the count of edges if the statistic exists
            - None otherwise
        """
        statistic_key = (vertex_source_class_name, edge_class_name, vertex_target_class_name)
        return self._edge_count_between_vertex_pairs.get(statistic_key)
