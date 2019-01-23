# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql_compiler.compiler import blocks, expressions


UNSUPPORTED_META_FIELDS = {
    u'@class': u'__typename'
}

SKIPPABLE_BLOCK_TYPES = (
    # MarkLocation blocks are used in the first pass over the IR blocks to create a mapping of
    # IR block -> query path for all IR blocks. They can safely be skipped during tree construction.
    blocks.MarkLocation,
    # Global operations are used as a marker, but do not require other handling by the SQL backend.
    blocks.GlobalOperationsStart,
    # ConstructResult blocks are given special handling, they can otherwise be disregarded.
    blocks.ConstructResult,
)

SUPPORTED_BLOCK_TYPES = (
    blocks.QueryRoot,
    blocks.Filter,
)

SUPPORTED_OUTPUT_EXPRESSION_TYPES = (
    expressions.OutputContextField,
)


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


SUPPORTED_OPERATORS = {
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


SqlOutput = namedtuple('SqlOutput', ('field_name', 'output_name', 'graphql_type'))
