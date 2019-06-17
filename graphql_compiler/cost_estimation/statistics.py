# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod

import six


@six.python_2_unicode_compatible
@six.add_metaclass(ABCMeta)
class Statistics(object):
    """Abstract class for statistics regarding GraphQL objects and vertex field values.

    For the purposes of cost estimation, we need statistics to provide estimates for costs of
    certain operations like edge traversal and @filter directive usage.
    This class provides an interface for these statistics.
    All statistics except get_class_count are optional, so if the statistic doesn't exist, a
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
            - Number of objects with, or inheriting the given class name

        Raises:
            AssertionError, if statistic for class_name was not provided.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_edge_count_between_vertex_pair(
        self, vertex_out_class_name, vertex_in_class_name, edge_class_name
    ):
        """Return the edge count between two vertices of a given type using an edge of a given type.

        Edge traversal cost between two vertices using an edge that connects the vertices' using
        their abstract inherited types is difficult to estimate, so we provide an interface for
        this statistic.

        Args:
            vertex_out_class_name: str, vertex class name.
            vertex_in_class_name: str, vertex class name.
            edge_class_name: str, edge class name.

        Returns:
            - The count of edges if the statistic exists
            - None otherwise
        """
        return None

    @abstractmethod
    def get_domain_count(self, vertex_name, field_name):
        """Return the number of distinct values the vertex field has over all vertex instances.

        This statistics helps estimate the result size of @filter directives used to restrict
        values using equality operators like '=', '!=', and 'in_collection'.

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
        """Return a histogram for the given vertex field, providing statistics about range values.

        This statistics helps estimate the result size of @filter directives used to restrict
        numbers using inequality operators like '>', '<', and 'between'.

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


class LocalStatistics(Statistics):
    """Provides statistics using ones given at initialization."""
    def __init__(self, class_count, edge_count_between_vertex_pair, domain_count, histogram):
        """Initializes statistics with the given data.

        Args:
            class_count: dict, vertex/edge class name -> class count.
            edge_count_between_vertex_pair: dict,
                (str, str, str) -> count of edge type between vertex types.
            domain_count: dict, (str, str) -> domain size.
            histogram: dict, (str, str) -> histogram as list[tuple(int, int, int)]
        """
        self._class_count = class_count
        self._edge_count_between_vertex_pair = edge_count_between_vertex_pair
        self._domain_count = domain_count
        self._histogram = histogram

    def get_class_count(self, class_name):
        """Return how many objects have, or inherit, the given class name.

        Args:
            class_name: str, either a vertex class name or an edge class name defined in the
                        GraphQL schema.

        Returns:
            - Number of objects with, or inheriting the given class name

        Raises:
            AssertionError, if statistic for class_name was not provided.
        """
        if class_name not in self._class_count:
            raise AssertionError(u'Class count statistic is required, but entry not found for: '
                                 u'{}'.format(class_name))
        return self._class_count[class_name]

    def get_edge_count_between_vertex_pair(
        self, vertex_out_class_name, vertex_in_class_name, edge_class_name
    ):
        """Return the edge count between two vertices of a given type using an edge of a given type.

        Edge traversal cost between two vertices using an edge that connects the vertices' using
        their abstract inherited types is difficult to estimate, so we provide an interface for
        this statistic.

        Args:
            vertex_out_class_name: str, vertex class name.
            vertex_in_class_name: str, vertex class name.
            edge_class_name: str, edge class name.

        Returns:
            - The count of edges if the statistic exists
            - None otherwise
        """
        statistic_id = (vertex_in_class_name, vertex_out_class_name, edge_class_name)
        if statistic_id not in self._edge_count_between_vertex_pair:
            return None
        return self._edge_count_between_vertex_pair[statistic_id]

    def get_domain_count(self, vertex_name, field_name):
        """Return the number of distinct values the vertex field has over all vertex instances.

        This statistics helps estimate the result size of @filter directives used to restrict
        values using equality operators like '=', '!=', and 'in_collection'.

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
        """Return a histogram for the given vertex field, providing statistics about range values.

        This statistics helps estimate the result size of @filter directives used to restrict
        numbers using inequality operators like '>', '<', and 'between'.

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
