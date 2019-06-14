# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod

import six


@six.python_2_unicode_compatible
@six.add_metaclass(ABCMeta)
class GraphQLStatistics(object):
    """Interface for statistics functions regarding GraphQL objects and vertex field values."""
    @abstractmethod
    def get_class_count(self, class_name):
        """Return how many objects have the given class name.

        Args:
            class_name: str, either a vertex class name or a edge class name defined in the
                        GraphQL schema.

        Returns:
            - Number of objects with given class name if the statistic exists
            - None otherwise
        """
        return None

    @abstractmethod
    def count_of_vertex_pair_links_using_edge(
        self, vertex_in_class_name, vertex_out_class_name, edge_class_name
    ):
        """Return number of edges of given type connecting two vertices of given types.

        Args:
            vertex_in_class_name: str, vertex class name.
            vertex_out_class_name: str, vertex class name.
            edge_class_name: str, edge class name.

        Returns:
            - The count of such links if the statistic exists
            - None otherwise
        """
        return None

    @abstractmethod
    def get_domain_count(self, vertex_name, field_name):
        """Return the number of distinct values the vertex field has.

        Preconditions:
        1. field_name must be a valid vertex field of vertex_name

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - Distinct value count if the statistic exists
            - None otherwise
        """
        return None

    @abstractmethod
    def get_histogram(self, vertex_name, field_name):
        """Return a histogram for the given vertex field.

        Preconditions:
        1. field_name must be a valid vertex field of vertex_name

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - A histogram as a list of tuples with 3 elements each if the statistic exists.
              Each tuple represents a bin as (start, end, elementCount), where start and end are
              the interval boundaries (inclusively), and elementCount is the bin element count.
            - None otherwise
        """
        return None


class LocalStatistics(GraphQLStatistics):
    """Provides statistics that were provided during initialization."""

    def __init__(self, class_count, count_of_vertex_pair_links_using_edge, domain_count, histogram):
        """Initializes the statistics class with the given data.

        Args:
            class_count: dict, mapping class name to class count statistic.
            count_of_vertex_pair_links_using_edge: dict, mapping tuple to number of vertex links
                                                   using given edge class.
            domain_count: dict, mapping tuple of vertex class name and vertex field name to domain
                          count.
            histogram: dict, mapping tuple of vertex class name and vertex field name to histogram.
        """
        self._class_count = class_count
        self._count_of_vertex_pair_links_using_edge = count_of_vertex_pair_links_using_edge
        self._domain_count = domain_count
        self._histogram = histogram

    def get_class_count(self, class_name):
        """Return how many objects have the given class name.

        Args:
            class_name: str, either a vertex class name or a edge class name defined in the
                        GraphQL schema.

        Returns:
            - Number of objects with given class name if the statistic exists
            - None otherwise
        """
        if class_name not in self._class_count:
            return None
        return self._class_count[class_name]

    def count_of_vertex_pair_links_using_edge(
        self, vertex_in_class_name, vertex_out_class_name, edge_class_name
    ):
        """Return number of edges of given type connecting two vertices of given types.

        Args:
            vertex_in_class_name: str, vertex class name.
            vertex_out_class_name: str, vertex class name.
            edge_class_name: str, edge class name.

        Returns:
            - The count of such links if the statistic exists
            - None otherwise
        """
        statistic_id = (vertex_in_class_name, vertex_out_class_name, edge_class_name)
        if statistic_id not in self._count_of_vertex_pair_links_using_edge:
            return None
        return self._count_of_vertex_pair_links_using_edge[statistic_id]

    def get_domain_count(self, vertex_name, field_name):
        """Return the number of distinct values the vertex field has.

        Preconditions:
        1. field_name must be a valid vertex field of vertex_name

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - Distinct value count if the statistic exists
            - None otherwise
        """
        statistic_id = (vertex_name, field_name)
        if statistic_id not in self._domain_count:
            return None
        return self._domain_count[statistic_id]

    def get_histogram(self, vertex_name, field_name):
        """Return a histogram for the given vertex field.

        Preconditions:
        1. field_name must be a valid vertex field of vertex_name

        Args:
            vertex_name: str, name of a vertex.
            field_name: str, name of a vertex field.

        Returns:
            - A histogram as a list of tuples with 3 elements each if the statistic exists.
              Each tuple represents a bin as (start, end, elementCount), where start and end are
              the interval boundaries (inclusively), and elementCount is the bin element count.
            - None otherwise
        """
        if vertex_name not in self._histogram or field_name not in self._histogram[vertex_name]:
            return None
        return self._histogram[vertex_name][field_name]
