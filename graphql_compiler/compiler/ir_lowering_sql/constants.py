# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple
from enum import Enum

from sqlalchemy import String, func
from sqlalchemy.sql import functions

from ... import exceptions


# These columns are reserved for the construction of recursive queries
DEPTH_INTERNAL_NAME = u'___depth_internal_name'

RESERVED_COLUMN_NAMES = {
    DEPTH_INTERNAL_NAME,
}

UNSUPPORTED_META_FIELDS = {
    u'@class': u'__typename'
}


class Operator:
    def __init__(self, name, cardinality):
        """Represent an operator and it's underlying method."""
        self.name = name
        self.cardinality = cardinality


class Cardinality(Enum):
    """Cardinality for SQLAlchemy operators."""

    UNARY = 1
    BINARY = 2
    LIST_VALUED = 3


OPERATORS = {
    u'contains': Operator(u'in_', Cardinality.LIST_VALUED),
    u'&&': Operator(u'and_', Cardinality.BINARY),
    u'||': Operator(u'or_', Cardinality.BINARY),
    u'=': Operator(u'__eq__', Cardinality.UNARY),
    u'<': Operator(u'__lt__', Cardinality.UNARY),
    u'>': Operator(u'__gt__', Cardinality.UNARY),
    u'<=': Operator(u'__le__', Cardinality.UNARY),
    u'>=': Operator(u'__ge__', Cardinality.UNARY),
    u'has_substring': Operator(u'contains', Cardinality.UNARY),
}

UNSUPPORTED_OPERATOR_NAMES = {
    u'intersects',
    u'has_edge_degree',
}


class group_concat(functions.GenericFunction):
    """Register the SQL `group_concat` aggregate function with SQLAlchemy funcs."""

    type = String


FoldAggregate = namedtuple('FoldAggregate', ['func', 'args'])


class SqlBackend(object):

    supported_backend_to_fold_aggregate = {
        u'postgresql': FoldAggregate(func=func.array_agg, args=[]),
    }

    def __init__(self, backend):
        """Create a new SqlBackend to manage backend specific properties for compilation."""
        self._backend = backend

    @property
    def backend(self):
        """Return the backend as a string."""
        return self._backend

    @property
    def fold_aggregate(self):
        """Return the method used as a fold aggregate."""
        if self.backend not in self.supported_backend_to_fold_aggregate:
            raise exceptions.GraphQLValidationError(
                u'Backend "{}" is unsupported for folding, SQL cannot be compiled.'
            )
        return self.supported_backend_to_fold_aggregate[self.backend]
