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


class LocalStatistics(Statistics):
    """Provides statistics using ones given at initialization."""
    def __init__(
        self, class_counts
    ):
        """Initializes statistics with the given data.

        Args:
            class_counts: dict, str -> int, mapping vertex/edge class name to class count.
        """
        self._class_counts = frozendict(class_counts)

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
