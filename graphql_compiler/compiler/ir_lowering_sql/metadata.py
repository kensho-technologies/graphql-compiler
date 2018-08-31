# Copyright 2018-present Kensho Technologies, LLC.
from sqlalchemy import MetaData

from .constants import SqlBackend


class DirectEdge:
    def __init__(self, source_column, sink_column, table_name=None):
        """Create a new Edge representing a simple foreign key relationship between tables."""
        self.source_col = source_column
        self.sink_col = sink_column
        self.table_name = table_name


class JunctionEdge:
    def __init__(self, junction_edge, final_edge):
        """Create a new MultiEdge representing an edge that traverses a junction table."""
        if not isinstance(junction_edge, DirectEdge) or not isinstance(final_edge, DirectEdge):
            raise AssertionError('A MultiEdge must be comprised of BasicEdges')
        self.junction_edge = junction_edge
        self.final_edge = final_edge


class CompilerMetadata:
    """Configuration manager for compilation.

    In order to transform GraphQL to SQL, there needs to be
    additional configuration specified surrounding GraphQL type -> SQL table, GraphQL field -> SQL,
    and GraphQL Edge -> SQL JOIN.
    """

    def __init__(self, config, dialect, sqlalchemy_metadata):
        """Initialize a new compiler metadata manager."""
        self.config = config
        self.sqlalchemy_metadata = sqlalchemy_metadata
        self._db_backend = SqlBackend(dialect)
        self.table_name_to_table = {
            name.lower(): table for name, table in self.sqlalchemy_metadata.tables.items()
        }

    def get_table(self, schema_type):
        """Retrieve a SQLAlchemy table based on the supplied GraphQL schema type name."""
        table_name = schema_type.lower()
        if table_name not in self.table_name_to_table:
            raise AssertionError(
                'No Table found in SQLAlchemy metadata for table name "{}"'.format(table_name)
            )
        return self.table_name_to_table[table_name]

    def get_edge(self, outer_type_name, inner_type_name, edge_name):
        """Retrieve a SimpleEdge or MultiEdge from the config, if it exists."""
        if outer_type_name in self.config:
            parent_config = self.config[outer_type_name]
            if edge_name in parent_config:
                return parent_config[edge_name][inner_type_name]
        return None

    @property
    def db_backend(self):
        """Retrieve this compilers DB backend."""
        return self._db_backend
