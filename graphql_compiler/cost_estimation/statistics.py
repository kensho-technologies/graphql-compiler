# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod

from frozendict import frozendict
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
        """Return a human-readable str representation of the Statistics object."""
        return self.__str__()

    @abstractmethod
    def get_class_count(self, class_name):
        """Return how many vertex or edge instances have, or inherit, the given class name.

        Args:
            class_name: str, either a vertex class name or an edge class name defined in the
                        GraphQL schema.

        Returns:
            - int, count of vertex or edge instances having, or inheriting, the given class name.

        Raises:
            AssertionError, if the count statistic for the given vertex/edge class does not exist.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_vertex_edge_vertex_count(
        self, vertex_source_class_name, edge_class_name, vertex_target_class_name
    ):
        """Return the count of edges of the given class connecting vertex_source to vertex_target.

        This statistic is optional, as the estimator can roughly predict this statistic using
        get_class_count(). In some cases of traversal between two vertices using an edge connecting
        the vertices' superclasses, the estimates generated using get_class_count() may be off by
        several orders of magnitude. In such cases, this statistic should be provided.

        Args:
            vertex_source_class_name: str, vertex class name.
            edge_class_name: str, edge class name.
            vertex_target_class_name: str, vertex class name.

        Returns:
            - int, count of edges of class edge_class with the two vertex classes as its endpoints
                   if the statistic exists.
            - None otherwise.
        """
        return None

    @abstractmethod
    def get_distinct_field_values_count(self, vertex_name, field_name):
        """Return the count of distinct values a vertex's property field has over all instances.

        This statistic helps estimate the result size of @filter directives used to filter
        values using equality operators like '=', '!=', and 'in_collection'.

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - int, count of distinct values of that vertex's property field if the statistic exists.
            - None otherwise.
        """
        return None


class LocalStatistics(Statistics):
    """Provides statistics using ones given at initialization."""
    def __init__(
        self, class_counts, vertex_edge_vertex_counts=None,
        distinct_field_values_counts=None
    ):
        """Initializes statistics with the given data.

        Args:
            class_counts: dict, str -> int, mapping vertex/edge class name to class count.
            vertex_edge_vertex_counts: optional dict, (str, str, str) -> int, mapping
                tuple of (vertex source class name, edge class name, vertex target class name) to
                count of edge instances of given class connecting instances of two vertex classes.
            distinct_field_values_counts: optional dict, (str, str) -> int, mapping vertex class
                name and property field name to the count of distinct values of that vertex class's
                property field.
        """
        if vertex_edge_vertex_counts is None:
            vertex_edge_vertex_counts = dict()
        if distinct_field_values_counts is None:
            distinct_field_values_counts = dict()

        self._class_counts = frozendict(class_counts)
        self._vertex_edge_vertex_counts = frozendict(vertex_edge_vertex_counts)
        self._distinct_field_values_counts = frozendict(distinct_field_values_counts)

    def get_class_count(self, class_name):
        """Return how many vertex or edge instances have, or inherit, the given class name.

        Args:
            class_name: str, either a vertex class name or an edge class name defined in the
                        GraphQL schema.

        Returns:
            - int, count of vertex or edge instances having, or inheriting, the given class name.

        Raises:
            AssertionError, if the count statistic for the given vertex/edge class does not exist.
        """
        if class_name not in self._class_counts:
            raise AssertionError(u'Class count statistic is required, but entry not found for: '
                                 u'{}'.format(class_name))
        return self._class_counts[class_name]

    def get_vertex_edge_vertex_count(
        self, vertex_source_class_name, edge_class_name, vertex_target_class_name
    ):
        """Return the count of edges of the given class connecting vertex_source to vertex_target.

        This statistic is optional, as the estimator can roughly predict this statistic using
        get_class_count(). In some cases of traversal between two vertices using an edge connecting
        the vertices' superclasses, the estimates generated using get_class_count() may be off by
        several orders of magnitude. In such cases, this statistic should be provided.

        Args:
            vertex_source_class_name: str, vertex class name.
            edge_class_name: str, edge class name.
            vertex_target_class_name: str, vertex class name.

        Returns:
            - int, count of edges of class edge_class with the two vertex classes as its endpoints
                   if the statistic exists.
            - None otherwise.
        """
        statistic_key = (vertex_source_class_name, edge_class_name, vertex_target_class_name)
        return self._vertex_edge_vertex_counts.get(statistic_key)

    def get_distinct_field_values_count(self, vertex_name, field_name):
        """Return the count of distinct values a vertex's property field has over all instances.

        This statistic helps estimate the result size of @filter directives used to filter
        values using equality operators like '=', '!=', and 'in_collection'.

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - int, count of distinct values of that vertex's property field if the statistic exists.
            - None otherwise.
        """
        statistic_key = (vertex_name, field_name)
        return self._distinct_field_values_counts.get(statistic_key)
