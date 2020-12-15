# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
import datetime
import math
from typing import Any, Dict, List, Optional, Tuple

import six


@dataclass
class VertexSamplingSummary:
    """Results extracted from sampling a random subset that are relevant for statistics."""

    # The class this summary describes
    vertex_name: str

    # Mapping field_name -> (field_value -> observed_count) for all field names and observed
    # field values on this vertex class.
    value_counts: Dict[str, Dict[Any, int]]

    # The number_of_instances / number_of_samples ratio
    sample_ratio: int


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

    def get_value_count(self, vertex_name: str, field_name: str, value: Any) -> Optional[float]:
        """Return the estimated number of times the given value appears in the database.

        Args:
            vertex_name: vertex on which the field is defined
            field_name: field for which the value stands
            value: value to be counted

        Returns:
            An estimate on how often this value currently appears in the given field, or None
            if unknown.
        """
        return None


class LocalStatistics(Statistics):
    """Statistics class that receives all statistics at initialization, storing them in-memory."""

    # See __init__ docstring for definitions.
    _class_counts: Dict[str, int]
    _vertex_edge_vertex_counts: Dict[Tuple[str, str, str], int]
    _distinct_field_values_counts: Dict[Tuple[str, str], int]
    _field_quantiles: Dict[Tuple[str, str], List[Any]]
    _sampling_summaries: Dict[str, VertexSamplingSummary]

    def __init__(
        self,
        class_counts: Dict[str, int],
        *,
        vertex_edge_vertex_counts: Optional[Dict[Tuple[str, str, str], int]] = None,
        distinct_field_values_counts: Optional[Dict[Tuple[str, str], int]] = None,
        field_quantiles: Optional[Dict[Tuple[str, str], List[Any]]] = None,
        sampling_summaries: Optional[Dict[str, VertexSamplingSummary]] = None,
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
            sampling_summaries: optional SamplingSummaries for some classes

        TODO(bojanserafimov): Enforce a canonical representation for quantile values and
                              sampling summaries. Datetimes should be in utc, decimals should
                              have type float, etc.
        TODO(bojanserafimov): Validate class_counts against sample_ratio * num_samples
        """
        if vertex_edge_vertex_counts is None:
            vertex_edge_vertex_counts = dict()
        if distinct_field_values_counts is None:
            distinct_field_values_counts = dict()
        if field_quantiles is None:
            field_quantiles = dict()
        if sampling_summaries is None:
            sampling_summaries = dict()

        # Validate arguments
        for (vertex_name, field_name), quantile_list in six.iteritems(field_quantiles):
            if len(quantile_list) < 2:
                raise AssertionError(
                    f"The number of quantiles should be at least 2. Field "
                    f"{vertex_name}.{field_name} has {len(quantile_list)}."
                )
            for quantile in quantile_list:
                if isinstance(quantile, datetime.datetime):
                    if quantile.tzinfo is not None:
                        raise NotImplementedError(
                            f"Range reasoning for tz-aware datetimes is not implemented. "
                            f"found tz-aware quantiles for {vertex_name}.{field_name}."
                        )

        self._class_counts = class_counts
        self._vertex_edge_vertex_counts = vertex_edge_vertex_counts
        self._distinct_field_values_counts = distinct_field_values_counts
        self._field_quantiles = field_quantiles
        self._sampling_summaries = sampling_summaries

    def get_class_count(self, class_name):
        """See base class."""
        return self._class_counts.get(class_name)

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

    def get_value_count(self, vertex_name: str, field_name: str, value: Any) -> Optional[float]:
        """See base class."""
        vertex_sampling_summary = self._sampling_summaries.get(vertex_name)
        if vertex_sampling_summary is None:
            return None

        field_sampled_value_counts = vertex_sampling_summary.value_counts.get(field_name)
        if field_sampled_value_counts is None:
            return None

        sampled_value_count = field_sampled_value_counts.get(value)
        if sampled_value_count is not None:
            return sampled_value_count * vertex_sampling_summary.sample_ratio
        else:
            # We want to minimize the error ratio: max(true_value/estimate, estimate/true_value).
            # By rule of 3 (https://en.wikipedia.org/wiki/Rule_of_three_(statistics)), we have 95%
            # confidence that the true value count is less than (3 * sample_ratio). So we have
            # 95% confidence that the error ratio is at most math.sqrt(3 * sample_ratio). Some
            # intuition: with a sample ratio of 1000 the error ratio bound evaluates to about
            # sqrt(3000) ~= 55.
            return max(1, math.sqrt(3 * vertex_sampling_summary.sample_ratio))
