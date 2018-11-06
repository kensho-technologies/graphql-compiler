# Copyright 2018-present Kensho Technologies, LLC.

# These columns are reserved for the construction of recursive queries
DEPTH_INTERNAL_NAME = u'___depth_internal_name'

UNSUPPORTED_META_FIELDS = {
    u'@class': u'__typename'
}


class Operator(object):
    def __init__(self, name, cardinality):
        """Represent an operator and it's underlying method."""
        self.name = name
        self.cardinality = cardinality


class Cardinality(object):
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


class SqlBackend(object):

    def __init__(self, backend):
        """Create a new SqlBackend to manage backend specific properties for compilation."""
        self._backend = backend

    @property
    def backend(self):
        """Return the backend as a string."""
        return self._backend
