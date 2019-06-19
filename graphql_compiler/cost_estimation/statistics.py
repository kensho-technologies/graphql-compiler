# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod

import six


@six.python_2_unicode_compatible
@six.add_metaclass(ABCMeta)
class Statistics(object):
    """Abstract class for statistics regarding GraphQL objects.

    For the purposes of cost estimation, we need statistics to provide estimates for costs of
    certain operations like edge traversal and @filter directive usage.
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
        """Return how many objects have, or inherit, the given class name.

        Args:
            class_name: str, either a vertex class name or an edge class name defined in the
                        GraphQL schema.

        Returns:
            - int, number of objects with, or inheriting the given class name

        Raises:
            AssertionError, if statistic for class_name does not exist.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_edge_count_between_vertex_pair(
        self, vertex_out_class_name, vertex_in_class_name, edge_class_name
    ):
        """Return number of edges of given class connecting two vertex types.

        For cost estimation, sometimes we need to predict traversal costs between two vertex types
        using an edge type that connects the vertices' abstract types. If this statistic isn't
        provided, it can be roughly estimated using multiple calls of get_class_count().

        Args:
            vertex_out_class_name: str, vertex class name.
            vertex_in_class_name: str, vertex class name.
            edge_class_name: str, edge class name.

        Returns:
            - int, the count of edges if the statistic exists
            - None otherwise
        """
        return None

    @abstractmethod
    def get_domain_count(self, vertex_name, field_name):
        """Return the number of distinct values the vertex field has over all vertex instances.

        This statistic helps estimate the result size of @filter directives used to restrict values
        using equality operators like '=', '!=', and 'in_collection'.

        Preconditions:
        1. field_name must be a valid vertex field of vertex_name

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - int, domain size of the vertex field's values if the statistic exists
            - None otherwise
        """
        return None

    @abstractmethod
    def get_histogram(self, vertex_name, field_name):
        """Return a histogram for the given vertex field, providing statistics about range values.

        This statistic helps estimate the result size of @filter directives used to restrict
        numbers using inequality operators like '>', '<', and 'between'.

        Preconditions:
        1. field_name must be a valid vertex field of vertex_name

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - list[tuple(int, int, int)], histogram as a list of tuples with 3 elements each if the
              statistic exists. Each tuple represents a bin as (start, end, elementCount), where
              [start, end) is the range of values in the bin, and elementCount is the bin element
              count.
            - None otherwise
        """
        return None


class LocalStatistics(Statistics):
    """Provides statistics using ones given at initialization."""
    def __init__(self, class_counts, edge_count_between_vertex_pairs, domain_counts, histograms):
        """Initializes statistics with the given data.

        Args:
            class_counts: dict, str -> int, mapping vertex/edge class name to class count.
            edge_count_between_vertex_pairs: dict, (str, str, str) -> int,
                mapping tuple of (vertex out class name, vertex in class name, edge class name) to
                count of edge type between vertex types.
            domain_counts: dict, (str, str) -> int, mapping vertex class and field on that
                vertex class to domain size.
            histograms: dict, (str, str) -> list[tuple(int, int, int)], mapping vertex class and
                field on that vertex class to histogram as list[tuple(int, int, int)].
        """
        self._class_counts = class_counts
        self._edge_count_between_vertex_pairs = edge_count_between_vertex_pairs
        self._domain_counts = domain_counts
        self._histograms = histograms

    def get_class_count(self, class_name):
        """Return how many objects have, or inherit, the given class name.

        Args:
            class_name: str, either a vertex class name or an edge class name defined in the
                        GraphQL schema.

        Returns:
            - int, number of objects with, or inheriting the given class name

        Raises:
            AssertionError, if statistic for class_name does not exist.
        """
        if class_name not in self._class_counts:
            raise AssertionError(u'Class count statistic is required, but entry not found for: '
                                 u'{}'.format(class_name))
        return self._class_counts[class_name]

    def get_edge_count_between_vertex_pair(
        self, vertex_out_class_name, vertex_in_class_name, edge_class_name
    ):
        """Return number of edges of given class connecting two vertex types.

        For cost estimation, sometimes we need to predict traversal costs between two vertex types
        using an edge type that connects the vertices' abstract types. If this statistic isn't
        provided, it can be roughly estimated using multiple calls of get_class_count().

        Args:
            vertex_out_class_name: str, vertex class name.
            vertex_in_class_name: str, vertex class name.
            edge_class_name: str, edge class name.

        Returns:
            - int, the count of edges if the statistic exists
            - None otherwise
        """
        statistic_key = (vertex_in_class_name, vertex_out_class_name, edge_class_name)
        if statistic_key not in self._edge_count_between_vertex_pairs:
            return None
        return self._edge_count_between_vertex_pairs[statistic_key]

    def get_domain_count(self, vertex_name, field_name):
        """Return the number of distinct values the vertex field has over all vertex instances.

        This statistic helps estimate the result size of @filter directives used to restrict
        values using equality operators like '=', '!=', and 'in_collection'.

        Preconditions:
        1. field_name must be a valid vertex field of vertex_name

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - int, domain size of the vertex field's values if the statistic exists
            - None otherwise
        """
        statistic_key = (vertex_name, field_name)
        if statistic_key not in self._domain_counts:
            return None
        return self._domain_counts[statistic_key]

    def get_histogram(self, vertex_name, field_name):
        """Return a histogram for the given vertex field, providing statistics about range values.

        This statistic helps estimate the result size of @filter directives used to restrict
        numbers using inequality operators like '>', '<', and 'between'.

        Preconditions:
        1. field_name must be a valid vertex field of vertex_name

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - list[tuple(int, int, int)], histogram as a list of tuples with 3 elements each if the
              statistic exists. Each tuple represents a bin as (start, end, elementCount), where
              [start, end) is the range of values in the bin, and elementCount is the bin element
              count.
            - None otherwise
        """
        histogram_key = (vertex_name, field_name)
        if histogram_key not in self._histogram:
            return None
        return self._histogram[histogram_key]
