from sqlalchemy import bindparam, or_

from graphql_compiler.compiler.helpers import Location
from .constants import Cardinality



class SqlBlocks:

    class BaseBlock:
        def __init__(self, query_state):
            self.query_state = query_state

        @property
        def location(self):
            return self.query_state.location

        @property
        def edge_name(self):
            return self.query_state.current_vertex

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
        def in_recursive(self):
            return self.query_state.in_recursive

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
            super(SqlBlocks.Selection, self).__init__(query_state)

        def get_column(self, table, compiler_metadata):
            return compiler_metadata.get_column(self.relative_type, self.field_name, table)

        def to_sql(self, location_to_table, compiler_metadata, aggregate):
            """Get the SQLAlchemy column for this selection."""
            # todo modify aggregate based on the SQL backend
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
            "<=": Operator('__le__',Cardinality.SINGLE),
            ">=": Operator('__ge__', Cardinality.SINGLE),
            "between": Operator('between', Cardinality.DUAL),
            'has_substring': Operator('contains', Cardinality.SINGLE),
        }

        def __init__(self, field_name, param_names, operator_name, query_state):
            """Creates a new Predicate block."""
            self.field_name = field_name
            self.param_names = param_names
            if operator_name not in self.operators:
                raise AssertionError(
                    'Invalid operator "{}" supplied to predicate.'.format(operator_name)
                )
            self.operator = self.operators[operator_name]
            super(SqlBlocks.Predicate, self).__init__(query_state)

        def get_column(self, table, compiler_metadata):
            return compiler_metadata.get_column(self.relative_type, self.field_name, table)

        def to_sql(self, location_to_table, compiler_metadata):
            """Gets the SQLAlchemy where clause for a Predicate block."""
            table = location_to_table[self.location]
            column = self.get_column(table, compiler_metadata)
            if self.operator.cardinality == Cardinality.SINGLE:
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

        def get_table(self, compiler_metadata):
            return compiler_metadata.get_table(self.relative_type)

        def get_dependency_fields(self, compiler_metadata):
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name, self.relative_type)
            from_location = Location(self.location.query_path[:-1])
            to_location = self.location
            from_column = on_clause.outer_col
            to_column = on_clause.inner_col
            return from_location, to_location, from_column, to_column

        def get_inner_column_dependency(self, compiler_metadata):
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name, self.relative_type)
            location = Location(self.location.query_path[:-1])
            column = on_clause.inner_col
            return location, column

        def to_sql(self, outer_table, inner_table, compiler_metadata):
            """Converts the Relation to an OnClause"""
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name, self.relative_type)
            if on_clause is None:
                return None
            if not hasattr(outer_table.c, on_clause.outer_col):
                raise AssertionError(
                    'Table for schema "{}" does not have column "{}"'.format(
                        self.outer_type, on_clause.outer_col
                    )
                )
            outer_column = getattr(outer_table.c, on_clause.outer_col)
            if not hasattr(inner_table.c, on_clause.inner_col):
                raise AssertionError(
                    'Table for schema "{}" does not have column "{}"'.format(
                        self.relative_type, on_clause.inner_col
                    )
                )
            inner_column = getattr(inner_table.c, on_clause.inner_col)
            return outer_column == inner_column
