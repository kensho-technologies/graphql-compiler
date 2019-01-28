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


Operator = namedtuple('Operator', ('name', 'cardinality'))


CARDINALITY_UNARY = 'UNARY'
CARDINALITY_BINARY = 'BINARY'
CARDINALITY_LIST_VALUED = 'LIST_VALUED'


# The mapping supplied for SUPPORTED_OPERATORS allows for programmatic resolution of expressions
# to their SQLAlchemy equivalents. As a concrete example, when converting the GraphQL filter
# column_name @filter(op_name: "=", value: ["$variable_name"])
# the corresponding python uses SQLAlchemy operation `__eq__` in a call like
# getattr(Column(column_name), '__eq__')(BindParameter('variable_name')
# which programattically generates the equivalent of the desired SQLAlchemy expression
# Column('column_name') == BindParameter('variable_name')
SUPPORTED_OPERATORS = {
    u'contains': Operator(u'in_', CARDINALITY_LIST_VALUED),
    u'&&': Operator(u'and_', CARDINALITY_BINARY),
    u'||': Operator(u'or_', CARDINALITY_BINARY),
    u'=': Operator(u'__eq__', CARDINALITY_UNARY),
    u'!=': Operator(u'__ne__', CARDINALITY_UNARY),
    u'<': Operator(u'__lt__', CARDINALITY_UNARY),
    u'>': Operator(u'__gt__', CARDINALITY_UNARY),
    u'<=': Operator(u'__le__', CARDINALITY_UNARY),
    u'>=': Operator(u'__ge__', CARDINALITY_UNARY),
    u'has_substring': Operator(u'contains', CARDINALITY_UNARY),
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
