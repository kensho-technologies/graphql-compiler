# Copyright 2018-present Kensho Technologies, LLC.
import six

from ... import exceptions
from .constants import SqlBackend


class SqlMetadata(object):
    """Metadata wrapper for use during compilation.

    In order to transform GraphQL to SQL, there needs to be additional metadata specified
    for mapping:
        - GraphQL types -> SQL tables
        - GraphQL edges -> SQL JOINs
    """

    def __init__(self, tables, joins):
        """Initialize a new SQL metadata.

        Args:
            - tables: dict mapping every graphql type to a sqlalchemy table
            - joins: dict mapping graphql classes to:
                        dict mapping edge fields at that class to a dict with the following info:
                           to_table: GrapqQL vertex where the edge ends up
                           from_column: column name in this table
                           to_column: column name in tables[to_table]. The join is done on the from_column
                                      and to_column being equal. If you really need other kinds of joins,
                                      feel free to extend the interface.
        """
        self.table_name_to_table = tables
        self.joins = joins

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
