from collections import namedtuple
from enum import Enum

from sqlalchemy.sql import functions

from sqlalchemy import func, String


class Cardinality(Enum):
    SINGLE = 1
    DUAL = 2
    MANY = 3


class group_concat(functions.GenericFunction):
    '''
    Registers the SQL `group_concat` aggregate function with SQLAlchemy funcs.
    '''
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
        return self._backend

    @property
    def fold_aggregate(self):
        return self._fold_aggregate

    @property
    def recursion_combinator(self):
        return self._recursion_combinator
