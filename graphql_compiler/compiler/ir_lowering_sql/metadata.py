from collections import namedtuple
from sqlalchemy import MetaData, bindparam, or_

from graphql_compiler.compiler.ir_lowering_sql import SqlBlocks
from .constants import SqlBackend, Cardinality

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
        self.table_name_to_table = {
            name.lower(): table for name, table in self.sqlalchemy_metadata.tables.items()
        }

    def get_table(self, block):
        return self._get_table(block.relative_type)

    def _get_table(self, schema_name):
        """
        Retrieve a SQLAlchemy table based on the supplied schema name.
        :param schema_name: Name of the type in the GraphQL schema
        :return: Table
        """
        if schema_name not in self.config or 'table_name' not in self.config[schema_name]:
            table_name = schema_name
        else:
            table_name = self.config[schema_name]['table_name']
        table_name = table_name.lower()
        if table_name not in self.table_name_to_table:
            raise AssertionError(
                'No Table found in SQLAlchemy metadata for table name "{}"'.format(table_name)
            )
        return self.table_name_to_table[table_name]

    @property
    def db_backend(self):
        return self._db_backend

    def get_column_for_block(self, block):
        if isinstance(block, SqlBlocks.Selection):
            return self._get_selection_column(block)
        elif isinstance(block, SqlBlocks.Predicate):
            return self._get_column_for_block(block)
        raise AssertionError

    def _get_selection_column(self, block):
        if not block.renamed:
            column = self._get_column_for_block(block)
            if block.alias is not None:
                return column.label(block.alias)
            return column
        return block.table.c[block.alias]

    def _get_column_for_block(self, block):
        column_name = self._get_column_name_from_schema(block)
        return self._get_column_from_table(block.table, column_name)

    def _get_column_name_from_schema(self, block):
        if block.relative_type not in self.config:
            return block.field_name
        column_name = block.field_name
        schema_config = self.config[block.relative_type]
        if 'column_names' not in schema_config:
            return column_name
        column_map = schema_config['column_names']
        if block.field_name not in column_map:
            return column_name
        return column_map[block.field_name]

    def get_predicate_condition(self, block):
        column = self.get_column_for_block(block)
        if block.is_tag:
            tag_column = self._get_tag_column(block)
            operation = getattr(column, block.operator.name)
            clause = operation(tag_column)

        elif block.operator.cardinality == Cardinality.SINGLE:
            if len(block.param_names) != 1:
                raise AssertionError(
                    'Only one value can be supplied to an operator with singular cardinality.'
                )
            operation = getattr(column, block.operator.name)
            clause = operation(bindparam(block.param_names[0]))
        elif block.operator.cardinality == Cardinality.MANY:
            if len(block.param_names) != 1:
                raise AssertionError(
                    'Only one value can be supplied to an operator with cardinality many.'
                )
            operation = getattr(column, block.operator.name)
            clause = operation(bindparam(block.param_names[0], expanding=True))

        elif block.operator.cardinality == Cardinality.DUAL:
            if len(block.param_names) != 2:
                raise AssertionError(
                    'Two values must be supplied to an operator with dual cardinality.'
                )
            first_param, second_param = block.param_names
            operation = getattr(column, block.operator.name)
            clause = operation(bindparam(first_param), bindparam(second_param))
        else:
            raise AssertionError(
                'Unable to construct where clause with cardinality "{}"'.format(
                    block.operator.cardinality
                )
            )
        if clause is None:
            raise AssertionError("This should be unreachable.")
        if not block.in_optional:
            return clause
        # the == None below is valid SQLAlchemy, the == operator is heavily overloaded.
        return or_(column == None, clause)  # noqa: E711

    def get_on_clause_for_node(self, node):
        on_clause = self.get_edge_columns(node.relation)
        from_col, to_col = on_clause
        if node.relation.direction == 'in':
            from_col, to_col = to_col, from_col

        if on_clause is None:
            return None
        outer_column = self._get_column_from_table(node.parent_node.table, from_col)
        inner_column = self._get_column_from_table(node.table, to_col)
        return outer_column == inner_column

    def _get_tag_column(self, block):
        if block.tag_node.relation.relative_type not in self.config:
            raise AssertionError(
                'No config found for schema "{}"'.format(block.tag_node.relation.relative_type)
            )
        column_name = block.tag_field
        schema_config = self.config[block.tag_node.relation.relative_type]
        if 'column_names' not in schema_config:
            return self._get_column_from_table(block.tag_node.table, column_name)
        column_map = schema_config['column_names']
        if block.tag_field not in column_map:
            return self._get_column_from_table(block.tag_node.table, column_name)
        column_name = column_map[block.tag_field]
        return self._get_column_from_table(block.tag_node.table, column_name)

    @staticmethod
    def _get_column_from_table(table, column_name):
        if not hasattr(table, 'c'):
            raise AssertionError('No columns found on table object {}'.format(table))
        if not hasattr(table.c, column_name):
            raise AssertionError(
                'No column for table "{}" with name "{}"'.format(table, column_name)
            )
        return getattr(table.c, column_name)

    def get_edge_columns(self, block):
        edge_name = block.edge_name
        if not block.is_recursive:
            outer_type_name = block.outer_type
            relative_type = block.relative_type
        else:
            # this is a recursive edge, from a type back onto itself
            outer_type_name = block.relative_type
            relative_type = block.relative_type
        if outer_type_name in self.config:
            parent_config = self.config[outer_type_name]
            if 'edges' in parent_config:
                edges = parent_config['edges']
                if edge_name in edges:
                    return edges[edge_name]
        outer_table = self._get_table(outer_type_name)
        inner_table = self._get_table(relative_type)
        inner_table_fks = [fk for fk in inner_table.foreign_keys if fk.column.table == outer_table]
        outer_table_fks = [fk for fk in outer_table.foreign_keys if fk.column.table == inner_table]
        outer_matches = [foreign_key for foreign_key in inner_table_fks if
                         foreign_key.column.name in outer_table.columns]
        inner_matches = [foreign_key for foreign_key in outer_table_fks if
                         foreign_key.column.name in inner_table.columns]
        if len(outer_matches) == 1 and len(inner_matches) == 0:
            fk = outer_matches[0]
            return OnClause(outer_col=fk.column.name, inner_col=fk.parent.name)
        elif len(inner_matches) == 1 and len(outer_matches) == 0:
            fk = inner_matches[0]
            return OnClause(outer_col=fk.parent.name, inner_col=fk.column.name)
        elif len(inner_matches) == 0 and len(outer_matches) == 0:
            raise AssertionError(
                'No foreign key found from type {} to type {}'.format(outer_type_name, relative_type)
            )
        else:
            raise AssertionError('Ambiguous foreign key specified.')




