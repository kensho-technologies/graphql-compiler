# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod

from frozendict import frozendict
import six


@six.python_2_unicode_compatible
@six.add_metaclass(ABCMeta)
class Statistics(object):
    """Abstract class for statistics regarding the data in all backend instances for one schema.

    For the purposes of query cardinality estimation, we need statistics to provide better
    cardinality estimates when operations like edge traversal or @filter directives are used.
    All statistics except get_class_count() are optional, so if the statistic doesn't exist, a
    value of None should be returned.
    """

    def __str__(self):
        """Return a human-readable unicode representation of the Statistics object."""
        raise NotImplementedError()

    def __repr__(self):
        """Return a human-readable representation of the Statistics object."""
        return self.__str__()

    @abstractmethod
    def get_class_count(self, class_name):
        """Return how many vertex or edge instances have, or inherit, the given class name.

        Args:
            class_name: str, either a vertex class name or an edge class name defined in the
                        GraphQL schema.

        Returns:
            int, count of vertex or edge instances having, or inheriting, the given class name.

        Raises:
            AssertionError, if the count statistic for the given vertex/edge class does not exist.
        """
        raise NotImplementedError()

    def get_vertex_edge_vertex_count(
        self, vertex_source_class_name, edge_class_name, vertex_target_class_name
    ):
        """Return count of edge_class instances linking vertex_source and vertex_target instances.

        This statistic is optional, as the estimator can roughly predict this statistic using
        get_class_count(). In some cases of traversal between two vertices using an edge connecting
        the vertices' superclasses, the estimates generated using get_class_count() may be off by
        several orders of magnitude. In such cases, this statistic should be provided.

        Note that vertices that inherit from vertex_source and vertex_target should also be
        considered as vertex_source or vertex_target vertices respectively, and should be included
        in the statistic.

        Args:
            vertex_source_class_name: str, vertex class name defined in the GraphQL schema.
            edge_class_name: str, edge class name defined in the GraphQL schema.
            vertex_target_class_name: str, vertex class name defined in the GraphQL schema.

        Returns:
            - int, count of edge_class edges with the two vertex classes as its endpoints
                   if the statistic exists.
            - None otherwise.
        """
        return None

    def get_distinct_field_values_count(self, vertex_name, field_name):
        """Return the count of distinct values a vertex's property field has over all instances.

        This statistic helps estimate the result size of @filter directives used to filter
        values using equality operators like '=', '!=', and 'in_collection'.

        Args:
            vertex_name: str, name of a vertex defined in the GraphQL schema.
            field_name: str, name of a vertex field.

        Returns:
            - int, count of distinct values of that vertex's property field if the statistic exists.
            - None otherwise.
        """
        return None

    def get_field_quantiles(self, vertex_name, field_name):
        """Return a list dividing the field values in equally-sized groups.

        Args:
            vertex_name: str, name of a vertex defined in the GraphQL schema.
            field_name: str, name of a vertex field. This field has to have a type on which
                        the < operator makes sense.

        Returns:
            None or a sorted list of N quantiles dividing the values of the field
            into N-1 groups of almost equal size. The first element of the list is the smallest
            known value, and the last element is the largest known value.
        """
        return None


class LocalStatistics(Statistics):
    """Statistics class that receives all statistics at initialization, storing them in-memory."""

    def __init__(
        self, class_counts, vertex_edge_vertex_counts=None,
        distinct_field_values_counts=None, field_quantiles=None
    ):
        """Initialize statistics with the given data.

        Args:
            class_counts: dict, str -> int, mapping vertex/edge class name to count of
                          instances of that class.
            vertex_edge_vertex_counts: optional dict, (str, str, str) -> int, mapping tuple of
                                       (vertex source class name, edge class name, vertex target
                                       class name) to count of edge instances of given class
                                       connecting instances of two vertex classes.
            distinct_field_values_counts: optional dict, (str, str) -> int, mapping vertex class
                                          name and property field name to the count of distinct
                                          values of that vertex class's property field.
            field_quantiles: optional dict, (str, str) -> list, mapping vertex class name
                             and property field name to a list of N quantiles, a sorted list of
                             values separating the values of the field into N-1 groups of almost
                             equal size. The first element of the list is the smallest known value,
                             and the last element is the largest known value. The i-th
                             element is a value greater than or equal to i/N of all present
                             values. The number N can be different for each entry. N has to be at
                             least 2 for every entry present in the dict.
        """
        if vertex_edge_vertex_counts is None:
            vertex_edge_vertex_counts = dict()
        if distinct_field_values_counts is None:
            distinct_field_values_counts = dict()
        if field_quantiles is None:
            field_quantiles = dict()

        # Validate arguments
        for vertex_name, quantile_list in six.iteritems(field_quantiles):
            if len(quantile_list) < 2:
                raise AssertionError(u'The number of quantiles should be at least 2. Vertex '
                                     u'{} has {}.'.format(vertex_name, len(quantile_list)))

        self._class_counts = frozendict(class_counts)
        self._vertex_edge_vertex_counts = frozendict(vertex_edge_vertex_counts)
        self._distinct_field_values_counts = frozendict(distinct_field_values_counts)
        self._field_quantiles = frozendict(field_quantiles)

    def get_class_count(self, class_name):
        """See base class."""
        if class_name not in self._class_counts:
            raise AssertionError(u'Class count statistic is required, but entry not found for: '
                                 u'{}'.format(class_name))
        return self._class_counts[class_name]

    def get_vertex_edge_vertex_count(
        self, vertex_source_class_name, edge_class_name, vertex_target_class_name
    ):
        """See base class."""
        statistic_key = (vertex_source_class_name, edge_class_name, vertex_target_class_name)
        return self._vertex_edge_vertex_counts.get(statistic_key)

    def get_distinct_field_values_count(self, vertex_name, field_name):
        """See base class."""
        statistic_key = (vertex_name, field_name)
        return self._distinct_field_values_counts.get(statistic_key)

    def get_field_quantiles(self, vertex_name, field_name):
        """See base class."""
        statistic_key = (vertex_name, field_name)
        return self._field_quantiles.get(statistic_key)
