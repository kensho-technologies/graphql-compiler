# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple
from enum import Enum

from sqlalchemy.sql import functions

from sqlalchemy import func, String

from graphql_compiler import exceptions

# These columns are reserved for the construction of recursive queries
DEPTH_INTERNAL_NAME = u'__depth_internal_name'
PATH_INTERNAL_NAME = u'__path_internal_name'
LINK_INTERNAL_NAME = u'__link_internal_name'
RESERVED_COLUMN_NAMES = {DEPTH_INTERNAL_NAME, PATH_INTERNAL_NAME, LINK_INTERNAL_NAME}


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


class group_concat(functions.GenericFunction):
    """Register the SQL `group_concat` aggregate function with SQLAlchemy funcs."""

    type = String


FoldAggregate = namedtuple('FoldAggregate', ['func', 'args'])


class SqlBackend(object):

    supported_backend_to_fold_aggregate = {
        u'postgresql': FoldAggregate(func=func.array_agg, args=[]),
        u'sqlite': FoldAggregate(func.group_concat, args=[';;']),
        u'mssql': FoldAggregate(func=func.string_agg, args=[';;']),
    }
    supported_backend_recursion_combinator = {
        u'mssql': u'union_all',
        u'sqlite': u'union',
        u'postgresql': u'union',
    }

    def __init__(self, backend):
        """Create a new SqlBackend to manage backend specific properties for compilation."""
        if backend not in self.supported_backend_to_fold_aggregate:
            raise exceptions.GraphQLValidationError(
                u'Backend "{}" is unsupported for folding, SQL cannot be compiled.'
            )
        if backend not in self.supported_backend_recursion_combinator:
            raise exceptions.GraphQLValidationError(
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
