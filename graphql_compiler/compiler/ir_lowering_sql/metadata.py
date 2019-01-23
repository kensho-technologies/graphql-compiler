# Copyright 2018-present Kensho Technologies, LLC.
import six

from ... import exceptions
from .constants import SqlBackend


class SqlMetadata(object):
    """Metadata wrapper for use during compilation.

    In order to transform GraphQL to SQL, there needs to be additional metadata specified
    for mapping:
        - GraphQL types -> SQL tables
        - GraphQL fields -> SQL columns
        - GraphQL edges -> SQL JOINs
    """

    def __init__(self, dialect, sqlalchemy_metadata):
        """Initialize a new SQL metadata manager."""
        self.sqlalchemy_metadata = sqlalchemy_metadata
        self._db_backend = SqlBackend(dialect)
        self.table_name_to_table = {
            name.lower(): table
            for name, table in six.iteritems(self.sqlalchemy_metadata.tables)
        }

    def get_table(self, schema_type):
        """Retrieve a SQLAlchemy table based on the supplied GraphQL schema type name."""
        table_name = schema_type.lower()
        if not self.has_table(table_name):
            raise exceptions.GraphQLCompilationError(
                'No Table found in SQLAlchemy metadata for table name "{}"'.format(table_name)
            )
        return self.table_name_to_table[table_name]

    def has_table(self, schema_type):
        """Retrieve a SQLAlchemy table based on the supplied GraphQL schema type name."""
        table_name = schema_type.lower()
        return table_name in self.table_name_to_table

    @property
    def db_backend(self):
        """Retrieve this compiler's DB backend."""
        return self._db_backend
