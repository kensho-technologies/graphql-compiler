from sqlalchemy import MetaData

from graphql_compiler.compiler import blocks
from .constants import SqlBackend


class BasicEdge:
    def __init__(self, source_column, sink_column, table_name=None):
        self.source_col = source_column
        self.sink_col = sink_column
        self.table_name = table_name


class MultiEdge:
    def __init__(self, junction_edge, final_edge):
        if not isinstance(junction_edge, BasicEdge) or not isinstance(final_edge, BasicEdge):
            raise AssertionError('A MultiEdge must be comprised of BasicEdges')
        self.junction_edge = junction_edge
        self.final_edge = final_edge


class CompilerMetadata:
    """
    Configuration manager for compilation.

    In order to transform GraphQL to SQL, there needs to be
    additional configuration specified surrounding GraphQL type -> SQL table, GraphQL field -> SQL
    table column, and SQL table to SQL table relationships (for JOIN statements).
    """
    def __init__(self, config, dialect, sqlalchemy_metadata: MetaData):
        """Initialize a new metadata manager."""
        self.config = config
        self.sqlalchemy_metadata = sqlalchemy_metadata
        self._db_backend = SqlBackend(dialect)
        self.table_name_to_table = {
            name.lower(): table for name, table in self.sqlalchemy_metadata.tables.items()
        }

    def get_table(self, schema_type):
        """
        Retrieve a SQLAlchemy table based on the supplied schema name.
        :param schema_type: Name of the type in the GraphQL schema
        :return: Table
        """
        table_name = schema_type.lower()
        if table_name not in self.table_name_to_table:
            raise AssertionError(
                'No Table found in SQLAlchemy metadata for table name "{}"'.format(table_name)
            )
        return self.table_name_to_table[table_name]

    def get_edge(self, type_name, edge_name):
        if type_name in self.config:
            parent_config = self.config[type_name]
            if 'edges' in parent_config:
                edges = parent_config['edges']
                if edge_name in edges:
                    return edges[edge_name]
        return None

    @property
    def db_backend(self):
        return self._db_backend
