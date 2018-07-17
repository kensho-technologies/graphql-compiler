from sqlalchemy import bindparam, or_, and_, select, literal_column, case, cast, String

from graphql_compiler.compiler.helpers import Location
from .constants import Cardinality


class SqlNode(object):
    def __init__(self, parent_node, relation):
        self.parent_node = parent_node
        self.children_nodes = []
        self.recursions = []
        self.selections = []
        self.predicates = []
        self.link_columns = []
        self.recursion_to_column = {}
        self.link_column = None
        self.relation = relation
        self.from_clause = None
        self.table = None

    def add_child_node(self, child_node):
        if child_node.relation.is_recursive:
            self.recursions.append(child_node)
        else:
            self.children_nodes.append(child_node)

    def add_selection(self, selection):
        if not isinstance(selection, SqlBlocks.Selection):
            raise AssertionError('Trying to add non-selection')
        self.selections.append(selection)

    def add_link_column(self, column):
        self.link_columns.append(column)

    def add_predicate(self, predicate):
        if not isinstance(predicate, SqlBlocks.Predicate):
            raise AssertionError('Trying to add non-predicate')
        self.predicates.append(predicate)

    def collapse_query_tree(self, compiler_metadata):
        for child_node in self.children_nodes:
            child_node.collapse_query_tree(compiler_metadata)
        self.create_table(compiler_metadata)
        self.create_links_for_recursions()
        for child_node in self.children_nodes:
            # pull up the childs SQL blocks
            self.pull_up_node_blocks(child_node)
            # join to the child
            self.join_to_node(child_node, compiler_metadata)

    def create_links_for_recursions(self):
        if len(self.recursions) == 0:
            return
        pk = [column for column in self.table.c if column.primary_key][0]
        for recursion in self.recursions:
            self.create_link_for_recursion(pk, recursion)

    def create_table(self, compiler_metadata):
        table = self.relation.get_table(compiler_metadata).alias()
        self.reference_table(table)

    def pull_up_node_blocks(self, child_node):
        self.selections.extend(child_node.selections)
        self.predicates.extend(child_node.predicates)
        self.recursions.extend(child_node.recursions)
        for recursion, link_column in child_node.recursion_to_column.items():
            self.recursion_to_column[recursion] = link_column
        self.link_columns.extend(child_node.link_columns)

    def join_to_node(self, child_node, compiler_metadata):
        # outer table is the current table, inner table is the child's
        onclause = child_node.relation.get_on_clause(self.table, child_node.table,
                                                     compiler_metadata)
        if onclause is None:
            # should only happen at root
            return
        if child_node.relation.in_optional:
            self.from_clause = self.from_clause.outerjoin(
                child_node.from_clause, onclause=onclause
            )
            return
        self.from_clause = self.from_clause.join(
            child_node.from_clause, onclause=onclause
        )

    def create_link_for_recursion(self, pk, recursion):
        link_column = pk.label(None)
        self.recursion_to_column[recursion] = link_column
        self.add_link_column(link_column)

    def reference_table(self, table):
        self.table = table
        self.from_clause = table
        self.update_table_for_nodes(table, self.selections)
        self.update_table_for_nodes(table, self.predicates)

    @staticmethod
    def update_table_for_nodes(table, nodes):
        for node in nodes:
            node.table = table

    def to_query_recursive(self, compiler_metadata, return_final_query, parent_cte=None, link_column=None):
        self.collapse_query_tree(compiler_metadata)
        outer_link_column = None
        if self.relation.is_recursive:
            outer_link_column = self.create_recursive_element(compiler_metadata, link_column, parent_cte)
        query = self.create_base_query(compiler_metadata)
        self.wrap_query_as_cte(query)
        recursive_selections = []
        for recursion in self.recursions:
            link_column = self.recursion_to_column[recursion]
            recursive_link_column = recursion.to_query_recursive(
                compiler_metadata, return_final_query=False,
                parent_cte=self.table, link_column=link_column
            )
            recursive_selections.extend(recursion.selections)
            self.join_to_recursive_node(link_column, recursion, recursive_link_column)
        # make sure selections point to the underlying CTE now
        self.selections = self.selections + recursive_selections
        if return_final_query:
            query = self.create_final_query(compiler_metadata, recursive_selections)
            return query
        return outer_link_column

    def join_to_recursive_node(self, link_column, recursion, recursive_link_column):
        current_cte_column = self.table.c[link_column.name]
        recursive_cte_column = recursion.table.c[recursive_link_column.name]
        self.from_clause = self.from_clause.join(
            recursion.from_clause, onclause=current_cte_column == recursive_cte_column
        )

    def create_final_query(self, compiler_metadata, recursive_selections):
        # no need to adjust predicates, they are already applied
        columns = [selection.get_selection_column(compiler_metadata) for selection in
                   self.selections]
        # no predicates required,  since they are captured in the base CTE
        return self.create_query(columns, None)

    def wrap_query_as_cte(self, query):
        cte = query.cte()
        self.from_clause = cte
        self.table = cte
        self.update_table_for_nodes(cte, self.selections)
        for selection in self.selections:
            # CTE has assumed the alias columns, make sure the selections know that
            selection.rename()

    def create_base_query(self, compiler_metadata):
        selection_columns = [selection.get_selection_column(compiler_metadata) for selection in
                   self.selections]
        selection_columns += self.link_columns
        predicates = [predicate.to_predicate_statement(compiler_metadata) for predicate in
                      self.predicates]
        query = self.create_query(selection_columns, predicates)
        return query

    def create_query(self, columns, predicates):
        query = (
            select(columns, distinct=True)
            .select_from(self.from_clause)
        )
        if predicates is not None:
            query = query.where(and_(*predicates))
        return query

    def create_recursive_element(self, compiler_metadata, link_column,
                                 parent_cte):
        on_clause = compiler_metadata.get_on_clause(
            self.relation.relative_type, self.relation.edge_name, None
        )
        recursive_table = self.relation.get_table(compiler_metadata)
        table = recursive_table.alias()
        primary_key = [column for column in table.c if column.primary_key][0]
        parent_cte_column = parent_cte.c[link_column.name]
        distinct_parent_column_query = select([parent_cte_column.label('link')],
                                              distinct=True).alias()
        anchor_query = (
            select([
                primary_key.label(on_clause.inner_col),
                primary_key.label(on_clause.outer_col),
                literal_column('0').label('__depth_internal_name'),
                cast(primary_key, String()).concat(',').label('path'),
            ], distinct=True)
                .select_from(
                table.join(distinct_parent_column_query,
                           primary_key == distinct_parent_column_query.c['link'])
            )
        )
        recursive_cte = anchor_query.cte(recursive=True)
        recursive_query = (
            select([
                recursive_cte.c[on_clause.inner_col],
                table.c[on_clause.outer_col],
                (recursive_cte.c['__depth_internal_name'] + 1).label('__depth_internal_name'),
                recursive_cte.c.path.concat(cast(table.c[on_clause.outer_col], String())).concat(
                    ',').label('path'),
            ])
                .select_from(
                table.join(recursive_cte,
                           table.c[on_clause.inner_col] == recursive_cte.c[on_clause.outer_col])
            ).where(and_(
                recursive_cte.c['__depth_internal_name'] < self.relation.recursion_depth,
                case(
                    [
                        (
                            recursive_cte.c.path.contains(
                                cast(table.c[on_clause.outer_col], String())),
                            1)
                    ],
                    else_=0
                ) == 0
            ))
        )
        recursion_combinator = compiler_metadata.db_backend.recursion_combinator
        recursive_query = getattr(recursive_cte, recursion_combinator)(recursive_query)
        pk = [column for column in self.table.c if column.primary_key][0]
        self.from_clause = self.from_clause.join(recursive_query,
                                                 pk == recursive_query.c[on_clause.outer_col])
        link_column = recursive_query.c[on_clause.inner_col].label(None)
        self.add_link_column(link_column)
        outer_link_column = link_column
        return outer_link_column

    def to_query(self, compiler_metadata):
        query = self.to_query_recursive(compiler_metadata, return_final_query=True)
        return query

    def __repr__(self):
        return self.relation.__repr__()


class SqlBlocks:

    class BaseBlock:
        def __init__(self, query_state):
            self.query_state = query_state
            self.table = None

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
                    raise AssertionError('Column {} not found in columns {}', column_name, self.table.c)
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

        def get_predicate_column(self, compiler_metadata):
            return compiler_metadata.get_column(self.relative_type, self.field_name, self.table)

        def to_sql(self, location_to_table, compiler_metadata):
            """Gets the SQLAlchemy where clause for a Predicate block."""
            table = location_to_table[self.location]
            column = self.get_column(table, compiler_metadata)
            return self.get_predicate(column)

        def to_predicate_statement(self, compiler_metadata):
            column = self.get_predicate_column(compiler_metadata)
            return self.get_predicate(column)

        def get_predicate(self, column):
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

    class LinkSelection(BaseBlock):
        """Marker Selection construct to make sure necessary fields are exposed for relations."""
        def __init__(self, to_edge, query_state):
            self.to_edge = to_edge
            super(SqlBlocks.LinkSelection, self).__init__(query_state)

        def to_sql(self, location_to_table, compiler_metadata, primary_key=False):
            """Get the SQLAlchemy column for this selection."""
            # todo modify aggregate based on the SQL backend
            table = location_to_table[Location(self.location.query_path[:-1])]
            if primary_key:
                return [column.label(None) for column in table.c if column.primary_key][0]
            column_name = self.get_field(compiler_metadata)
            column = table.c[column_name]
            return column.label(None)

        def get_field(self, compiler_metadata):
            on_clause = compiler_metadata.get_on_clause(
                self.outer_type, self.to_edge, self.relative_type
            )
            return on_clause.outer_col

    class StartRecursion(BaseBlock):
        pass

    class EndRecursion(BaseBlock):
        pass

    class Relation(BaseBlock):

        def __init__(self, query_state, recursion_depth=None):
            self.recursion_depth = recursion_depth
            super(SqlBlocks.Relation, self).__init__(query_state)

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

        def to_sql(self, outer_table, inner_table, compiler_metadata, outer_column_name = None):
            """Converts the Relation to an OnClause"""
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name, self.relative_type)
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

        def get_on_clause(self, outer_table, inner_table, compiler_metadata, outer_column_name = None):
            """Converts the Relation to an OnClause"""
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name, self.relative_type)
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

        def to_optional_sql(self, outer_column, inner_table, compiler_metadata):
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name, self.relative_type)
            if on_clause is None:
                return None
            inner_column = getattr(inner_table.c, on_clause.inner_col)
            return outer_column == inner_column

        def __repr__(self):
            return self.location.query_path.__repr__()
