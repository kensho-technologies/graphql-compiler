from collections import namedtuple
from sqlalchemy import MetaData

from .constants import SqlBackend

OnClause = namedtuple('OnClause', ['outer_col', 'inner_col'])



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

    def get_table(self, schema_name):
        """
        Retrieve a SQLAlchemy table based on the supplied schema name.
        :param schema_name: Name of the type in the GraphQL schema
        :return: Table
        """
        if schema_name not in self.config:
            raise AssertionError(
                'No schema in config for name "{}"'.format(schema_name)
            )
        if 'table_name' not in self.config[schema_name]:
            raise AssertionError(
                'No table found for schema name "{}"'.format(schema_name)
            )
        table_name = self.config[schema_name]['table_name']
        if table_name not in self.sqlalchemy_metadata.tables:
            raise AssertionError(
                'No Table found in SQLAlchemy metadata for table name "{}"'.format(table_name)
            )
        return self.sqlalchemy_metadata.tables[table_name]


    @property
    def db_backend(self):
        return self._db_backend

    def get_column(self, schema_type_name, schema_column, table):
        """
        Retrieve a SQLAlchemy column for the table mapped from the supplied schema name,
        with the designated schema field name.
        :param table: SQLAlchemy table to get the column on
        :param schema_type_name: The name of the type in the GraphQL schema.
        :param schema_column: The name of the field in the GraphQL schema.
        :return: SQLAlchemy column.
        """
        if schema_type_name not in self.config:
            raise AssertionError(
                'No config found for schema "{}"'.format(schema_type_name)
            )
        column_name = schema_column
        schema_config = self.config[schema_type_name]
        if 'column_names' not in schema_config:
            return self.get_table_column(table, column_name)
        column_map = schema_config['column_names']
        if schema_column not in column_map:
            return self.get_table_column(table, column_name)
        column_name = column_map[schema_column]
        return self.get_table_column(table, column_name)

    def get_column_name(self, schema_type_name, schema_column):
        if schema_type_name not in self.config:
            raise AssertionError(
                'No config found for schema "{}"'.format(schema_type_name)
            )
        column_name = schema_column
        schema_config = self.config[schema_type_name]
        if 'column_names' not in schema_config:
            return column_name
        column_map = schema_config['column_names']
        if schema_column not in column_map:
            return column_name
        column_name = column_map[schema_column]
        return column_name

    @staticmethod
    def get_table_column(table, column_name):
        if not hasattr(table.c, column_name):
            raise AssertionError(
                'No column for table "{}" with name "{}"'.format(table, column_name)
            )
        return getattr(table.c, column_name)

    def get_on_clause(self, outer_type_name, edge_name, relative_type):
        """
        Returns the on-clause columns for the tables mapped from the outer and inner type names.
        :param outer_type_name: The name to be mapped to the outer table.
        :param edge_name: The name to be mapped to the inner table
        :return: on clause columns: parent, child
        """
        if outer_type_name not in self.config:
            return None
        parent_config = self.config[outer_type_name]
        if 'edges' not in parent_config:
            return None
        edges = parent_config['edges']
        if edge_name in edges:
            return edges[edge_name]
        outer_table = self.get_table(outer_type_name)
        inner_table = self.get_table(relative_type)
        inner_table_fks = [fk for fk in inner_table.foreign_keys if fk.column.table == outer_table]
        outer_table_fks = [fk for fk in outer_table.foreign_keys if fk.column.table == inner_table]
        outer_matches = [foreign_key for foreign_key in inner_table_fks if foreign_key.column.name in outer_table.columns]
        inner_matches = [foreign_key for foreign_key in outer_table_fks if foreign_key.column.name in inner_table.columns]
        if len(outer_matches) == 1 and len(inner_matches) == 0:
            fk = outer_matches[0]
            return OnClause(outer_col=fk.column.name, inner_col=fk.parent.name)
        elif len(inner_matches) == 1 and len(outer_matches) == 0:
            fk = inner_matches[0]
            return OnClause(outer_col=fk.parent.name, inner_col=fk.column.name)
        else:
            raise AssertionError('Ambiguous foreign key specified.')


