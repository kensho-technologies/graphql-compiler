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
)

SUPPORTED_BLOCK_TYPES = (
    blocks.QueryRoot,
)

SUPPORTED_OUTPUT_EXPRESSION_TYPES = (
    expressions.OutputContextField,
)


class SqlBackend(object):

    def __init__(self, backend):
        """Create a new SqlBackend to manage backend specific properties for compilation."""
        self._backend = backend

    @property
    def backend(self):
        """Return the backend as a string."""
        return self._backend


SqlOutput = namedtuple('SqlOutput', ('field_name', 'output_name', 'graphql_type'))
