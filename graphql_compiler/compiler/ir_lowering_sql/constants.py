# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple

UNSUPPORTED_META_FIELDS = {
    u'@class': u'__typename'
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
