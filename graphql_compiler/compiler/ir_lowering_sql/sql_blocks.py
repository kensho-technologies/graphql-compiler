from sqlalchemy import bindparam, or_

from graphql_compiler.compiler.helpers import Location
from .constants import Cardinality


class SqlBlocks:
    """
    The core abstraction of the SQL backend, these are transformations of IR blocks, preserving
    the elements that are of importance, while mapping to a more natural domain and language for
    considering SQL queries.
    """
    class BaseBlock:
        def __init__(self, query_state):
            self.query_state = query_state
            self.table = None

        @property
        def location(self):
            return self.query_state.location

        @property
        def edge_name(self):
            current_vertex = self.query_state.current_vertex
            if current_vertex.startswith('out_'):
                return current_vertex[4:]
            if current_vertex.startswith('in_'):
                return current_vertex[3:]
            raise AssertionError

        @location.setter
        def location(self, value):
            if not isinstance(value, Location):
                raise AssertionError(
                    'Cannot set SQL block location with invalid type "{}"'.format(type(value))
                )
            self.query_state.location = value

        @property
        def relative_type(self):
            return self.query_state.current_type()

        @property
        def outer_type(self):
            return self.query_state.outer_type()

        @property
        def in_optional(self):
            return self.query_state.in_optional

        @property
        def is_recursive(self):
            return self.query_state.is_recursive

        @property
        def in_fold(self):
            return self.query_state.in_fold

        @property
        def optional_id(self):
            return self.query_state.optional_id

    class Selection(BaseBlock):
        def __init__(self, field_name, alias, query_state):
            self.field_name = field_name
            self.alias = alias
            self.renamed = False
            super(SqlBlocks.Selection, self).__init__(query_state)

        def rename(self):
            if self.alias is None:
                self.alias = self.field_name
            self.renamed = True

        def get_column(self, table, compiler_metadata):
            return compiler_metadata.get_column(self.relative_type, self.field_name, table)

        def get_selection_column(self, compiler_metadata):
            if not self.renamed:
                column_name = compiler_metadata.get_column_name(self.relative_type, self.field_name)
                if column_name not in self.table.c:
                    raise AssertionError('Column {} not found in columns {}', column_name,
                                         self.table.c)
                column = self.table.c[column_name]
                if self.alias is not None:
                    return column.label(self.alias)
                return column
            else:
                return self.table.c[self.alias]

        def to_sql(self, location_to_table, compiler_metadata, aggregate, use_alias=False):
            """Get the SQLAlchemy column for this selection."""
            # todo modify aggregate based on the SQL backend
            if use_alias:
                return location_to_table[self.location].c[self.alias]
            column = self.get_column(location_to_table[self.location], compiler_metadata)
            if aggregate:
                aggregate, args = compiler_metadata.db_backend.fold_aggregate
                column = aggregate(column, *args)
            if self.alias is not None:
                column = column.label(self.alias)
            return column

    class Predicate(BaseBlock):

        class Operator:
            def __init__(self, name, cardinality):
                self.name = name
                self.cardinality = cardinality

        operators = {
            "contains": Operator('in_', Cardinality.MANY),
            "=": Operator('__eq__', Cardinality.SINGLE),
            "<": Operator('__lt__', Cardinality.SINGLE),
            ">": Operator('__gt__', Cardinality.SINGLE),
            "<=": Operator('__le__', Cardinality.SINGLE),
            ">=": Operator('__ge__', Cardinality.SINGLE),
            "between": Operator('between', Cardinality.DUAL),
            'has_substring': Operator('contains', Cardinality.SINGLE),
        }

        def __init__(self, field_name, param_names, operator_name, is_tag, tag_location, tag_field,
                     query_state):
            """Creates a new Predicate block."""
            self.field_name = field_name
            self.param_names = param_names
            self.is_tag = is_tag
            self.tag_location = tag_location
            self.tag_field = tag_field
            self.tag_node = None
            if operator_name not in self.operators:
                raise AssertionError(
                    'Invalid operator "{}" supplied to predicate.'.format(operator_name)
                )
            self.operator = self.operators[operator_name]
            super(SqlBlocks.Predicate, self).__init__(query_state)

        def get_column(self, table, compiler_metadata):
            return compiler_metadata.get_column(self.relative_type, self.field_name, table)

        def get_tag_column(self, compiler_metadata):
            return compiler_metadata.get_column(
                self.tag_node.relation.relative_type, self.tag_field, self.tag_node.table
            )

        def get_predicate_column(self, compiler_metadata):
            return compiler_metadata.get_column(self.relative_type, self.field_name, self.table)

        def to_sql(self, location_to_table, compiler_metadata):
            """Gets the SQLAlchemy where clause for a Predicate block."""
            table = location_to_table[self.location]
            column = self.get_column(table, compiler_metadata)
            return self.get_predicate(column, compiler_metadata)

        def to_predicate_statement(self, compiler_metadata):
            column = self.get_predicate_column(compiler_metadata)
            return self.get_predicate(column, compiler_metadata)

        def get_predicate(self, column, compiler_metadata):
            if self.is_tag:
                tag_column = self.get_tag_column(compiler_metadata)
                operation = getattr(column, self.operator.name)
                clause = operation(tag_column)

            elif self.operator.cardinality == Cardinality.SINGLE:
                if len(self.param_names) != 1:
                    raise AssertionError(
                        'Only one value can be supplied to an operator with singular cardinality.'
                    )
                operation = getattr(column, self.operator.name)
                clause = operation(bindparam(self.param_names[0]))
            elif self.operator.cardinality == Cardinality.MANY:
                if len(self.param_names) != 1:
                    raise AssertionError(
                        'Only one value can be supplied to an operator with cardinality many.'
                    )
                operation = getattr(column, self.operator.name)
                clause = operation(bindparam(self.param_names[0], expanding=True))

            elif self.operator.cardinality == Cardinality.DUAL:
                if len(self.param_names) != 2:
                    raise AssertionError(
                        'Two values must be supplied to an operator with dual cardinality.'
                    )
                first_param, second_param = self.param_names
                operation = getattr(column, self.operator.name)
                clause = operation(bindparam(first_param), bindparam(second_param))
            else:
                raise AssertionError(
                    'Unable to construct where clause with cardinality "{}"'.format(
                        self.operator.cardinality
                    )
                )
            if clause is None:
                raise AssertionError("This should be unreachable.")
            if not self.in_optional:
                return clause
            # the == None below is valid SQLAlchemy, the == operator is heavily overloaded.
            return or_(column == None, clause)  # noqa: E711

    class Relation(BaseBlock):

        def __init__(self, query_state, recursion_depth=None, direction=None):
            self.recursion_depth = recursion_depth
            self.direction = direction
            super(SqlBlocks.Relation, self).__init__(query_state)

        def get_table(self, compiler_metadata):
            return compiler_metadata.get_table(self.relative_type)

        def get_dependency_fields(self, compiler_metadata):
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name,
                                                        self.relative_type)
            from_location = Location(self.location.query_path[:-1])
            to_location = self.location
            from_column = on_clause.outer_col
            to_column = on_clause.inner_col
            return from_location, to_location, from_column, to_column

        def get_inner_column_dependency(self, compiler_metadata):
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name,
                                                        self.relative_type)
            location = Location(self.location.query_path[:-1])
            column = on_clause.inner_col
            return location, column

        def to_sql(self, outer_table, inner_table, compiler_metadata, outer_column_name=None):
            """Converts the Relation to an OnClause"""
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name,
                                                        self.relative_type)
            if on_clause is None:
                return None
            outer_column_name = on_clause.outer_col if outer_column_name is None else outer_column_name
            if not hasattr(outer_table.c, outer_column_name):
                raise AssertionError(
                    'Table for schema "{}" does not have column "{}"'.format(
                        self.outer_type, on_clause.outer_col
                    )
                )
            outer_column = getattr(outer_table.c, outer_column_name)
            if not hasattr(inner_table.c, on_clause.inner_col):
                raise AssertionError(
                    'Table for schema "{}" does not have column "{}"'.format(
                        self.relative_type, on_clause.inner_col
                    )
                )
            inner_column = getattr(inner_table.c, on_clause.inner_col)
            return outer_column == inner_column

        def get_on_clause(self, outer_table, inner_table, compiler_metadata,
                          outer_column_name=None):
            """Converts the Relation to an OnClause"""
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name,
                                                        self.relative_type)
            from_col, to_col = on_clause
            if self.direction == 'in':
                from_col, to_col = to_col, from_col

            if on_clause is None:
                return None
            outer_column_name = on_clause.outer_col if outer_column_name is None else outer_column_name
            if not hasattr(outer_table.c, from_col):
                raise AssertionError(
                    'Table for schema "{}" does not have column "{}"'.format(
                        self.outer_type, on_clause.outer_col
                    )
                )
            outer_column = getattr(outer_table.c, from_col)
            if not hasattr(inner_table.c, to_col):
                raise AssertionError(
                    'Table for schema "{}" does not have column "{}"'.format(
                        self.relative_type, on_clause.inner_col
                    )
                )
            inner_column = getattr(inner_table.c, to_col)
            return outer_column == inner_column

        def to_optional_sql(self, outer_column, inner_table, compiler_metadata):
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name,
                                                        self.relative_type)
            if on_clause is None:
                return None
            inner_column = getattr(inner_table.c, on_clause.inner_col)
            return outer_column == inner_column

        def __repr__(self):
            return self.location.query_path.__repr__()
