# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple
from enum import Enum

from sqlalchemy.sql import functions

from sqlalchemy import func, String


class Cardinality(Enum):
    SINGLE = 1
    DUAL = 2
    MANY = 3


# These columns are reserved for the construction of recursive queries
DEPTH_INTERNAL_NAME = '__depth_internal_name'
PATH_INTERNAL_NAME = '__path_internal_name'
LINK_INTERNAL_NAME = '__link_internal_name'
RESERVED_COLUMN_NAMES = {DEPTH_INTERNAL_NAME, PATH_INTERNAL_NAME, LINK_INTERNAL_NAME}


class Operator:
    def __init__(self, name, cardinality):
        """Represent an operator and it's underlying method."""
        self.name = name
        self.cardinality = cardinality


OPERATORS = {
    "contains": Operator('in_', Cardinality.MANY),
    "=": Operator('__eq__', Cardinality.SINGLE),
    "<": Operator('__lt__', Cardinality.SINGLE),
    ">": Operator('__gt__', Cardinality.SINGLE),
    "<=": Operator('__le__', Cardinality.SINGLE),
    ">=": Operator('__ge__', Cardinality.SINGLE),
    "&&": Operator('and_', Cardinality.DUAL),
    'has_substring': Operator('contains', Cardinality.SINGLE),
}


class group_concat(functions.GenericFunction):
    """Register the SQL `group_concat` aggregate function with SQLAlchemy funcs."""

    type = String


FoldAggregate = namedtuple('FoldAggregate', ['func', 'args'])


class SqlBackend(object):

    supported_backend_to_fold_aggregate = {
        'postgresql': FoldAggregate(func=func.array_agg, args=[]),
        'sqlite': FoldAggregate(func.group_concat, args=[';;']),
        'mssql': FoldAggregate(func=func.string_agg, args=[';;']),
    }
    supported_backend_recursion_combinator = {
        'mssql': 'union_all',
        'sqlite': 'union',
        'postgresql': 'union',
    }

    def __init__(self, backend):
        """Create a new SqlBackend to manage backend specific properties for compilation."""
        if backend not in self.supported_backend_to_fold_aggregate:
            raise AssertionError(
                u'Backend "{}" is unsupported for folding, SQL cannot be compiled.'
            )
        if backend not in self.supported_backend_recursion_combinator:
            raise AssertionError(
                u'Backend "{}" is unsupported for recursion, SQL cannot be compiled.'
            )
        self._backend = backend
        self._fold_aggregate = self.supported_backend_to_fold_aggregate[backend]
        self._recursion_combinator = self.supported_backend_recursion_combinator[backend]

    @property
    def backend(self):
        """Return the backend as a string."""
        return self._backend

    @property
    def fold_aggregate(self):
        """Return the method used as a fold aggregate."""
        return self._fold_aggregate

    @property
    def recursion_combinator(self):
        """Return the method used to combine the anchor and recursive clauses of a recursive CTE."""
        return self._recursion_combinator
