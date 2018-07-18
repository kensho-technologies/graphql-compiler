from sqlalchemy import bindparam, or_, and_, select, literal_column, case, cast, String

from graphql_compiler.compiler.helpers import Location
from .constants import Cardinality


def collapse_query_tree(node, compiler_metadata):
    # recursively collapse the children's trees
    for child_node in node.children_nodes:
        collapse_query_tree(child_node, compiler_metadata)
    # create the current node's table
    create_table(node, compiler_metadata)
    # ensure that columns required for recursion are present
    create_links_for_recursions(node)
    for child_node in node.children_nodes:
        # pull up the childs SQL blocks
        pull_up_node_blocks(node, child_node)
        # join to the child
        join_to_node(node, child_node, compiler_metadata)


def to_query_recursive(node, compiler_metadata, return_final_query, parent_cte=None, link_column=None):
    collapse_query_tree(node, compiler_metadata)
    outer_link_column = None
    if node.relation.is_recursive:
        outer_link_column = create_recursive_element(
            node, compiler_metadata, link_column, parent_cte
        )
    query = create_base_query(node, compiler_metadata)
    wrap_query_as_cte(node, query)
    recursive_selections = []
    for recursive_node in node.recursions:
        link_column = node.recursion_to_column[recursive_node]
        recursive_link_column = to_query_recursive(
            recursive_node,compiler_metadata, return_final_query=False,
            parent_cte=node.table, link_column=link_column
        )
        recursive_selections.extend(recursive_node.selections)
        join_to_recursive_node(node, link_column, recursive_node, recursive_link_column)
    # make sure selections point to the underlying CTE now
    node.selections = node.selections + recursive_selections
    if return_final_query:
        return create_final_query(node, compiler_metadata)
    return outer_link_column


def create_recursive_element(node, compiler_metadata, link_column, parent_cte):
    on_clause = compiler_metadata.get_on_clause(
        node.relation.relative_type, node.relation.edge_name, None
    )
    recursive_table = node.relation.get_table(compiler_metadata)
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
            recursive_cte.c['__depth_internal_name'] < node.relation.recursion_depth,
            case(
                [
                    (recursive_cte.c.path.contains(cast(table.c[on_clause.outer_col], String())), 1)
                ],
                else_=0
            ) == 0
        ))
    )
    recursion_combinator = compiler_metadata.db_backend.recursion_combinator
    recursive_query = getattr(recursive_cte, recursion_combinator)(recursive_query)
    pk = [column for column in node.table.c if column.primary_key][0]
    node.from_clause = node.from_clause.join(recursive_query,
                                             pk == recursive_query.c[on_clause.outer_col])
    link_column = recursive_query.c[on_clause.inner_col].label(None)
    node.add_link_column(link_column)
    outer_link_column = link_column
    return outer_link_column


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

    def __repr__(self):
        return self.relation.__repr__()


def create_table(node, compiler_metadata):
    table = node.relation.get_table(compiler_metadata).alias()
    reference_table(node, table)


def pull_up_node_blocks(node, child_node):
    node.selections.extend(child_node.selections)
    node.predicates.extend(child_node.predicates)
    node.recursions.extend(child_node.recursions)
    for recursion, link_column in child_node.recursion_to_column.items():
        node.recursion_to_column[recursion] = link_column
    node.link_columns.extend(child_node.link_columns)


def join_to_node(node, child_node, compiler_metadata):
    # outer table is the current table, inner table is the child's
    onclause = child_node.relation.get_on_clause(node.table, child_node.table,
                                                 compiler_metadata)
    if onclause is None:
        # should only happen at root
        return
    if child_node.relation.in_optional:
        node.from_clause = node.from_clause.outerjoin(
            child_node.from_clause, onclause=onclause
        )
        return
    node.from_clause = node.from_clause.join(
        child_node.from_clause, onclause=onclause
    )


def reference_table(node, table):
    node.table = table
    node.from_clause = table
    update_table_for_blocks(table, node.selections)
    update_table_for_blocks(table, node.predicates)


def update_table_for_blocks(table, blocks):
    for block in blocks:
        block.table = table


def to_query(node, compiler_metadata):
    query = to_query_recursive(node, compiler_metadata, return_final_query=True)
    return query


def create_link_for_recursion(node, pk, recursion):
    link_column = pk.label(None)
    node.recursion_to_column[recursion] = link_column
    node.add_link_column(link_column)


def create_links_for_recursions(node):
    if len(node.recursions) == 0:
        return
    pk = [column for column in node.table.c if column.primary_key][0]
    for recursion in node.recursions:
        create_link_for_recursion(node, pk, recursion)


def join_to_recursive_node(node, link_column, recursion, recursive_link_column):
    current_cte_column = node.table.c[link_column.name]
    recursive_cte_column = recursion.table.c[recursive_link_column.name]
    node.from_clause = node.from_clause.join(
        recursion.from_clause, onclause=current_cte_column == recursive_cte_column
    )


def create_final_query(node, compiler_metadata):
    # no need to adjust predicates, they are already applied
    columns = [selection.get_selection_column(compiler_metadata) for selection in
               node.selections]
    # no predicates required,  since they are captured in the base CTE
    return create_query(node, columns, None)


def wrap_query_as_cte(node, query):
    cte = query.cte()
    node.from_clause = cte
    node.table = cte
    update_table_for_blocks(cte, node.selections)
    for selection in node.selections:
        # CTE has assumed the alias columns, make sure the selections know that
        selection.rename()


def create_base_query(node, compiler_metadata):
    selection_columns = [selection.get_selection_column(compiler_metadata) for selection in
                         node.selections]
    selection_columns += node.link_columns
    predicates = [predicate.to_predicate_statement(compiler_metadata) for predicate in
                  node.predicates]
    query = create_query(node, selection_columns, predicates)
    return query


def create_query(node, columns, predicates):
    query = (
        select(columns, distinct=True)
            .select_from(node.from_clause)
    )
    if predicates is not None:
        query = query.where(and_(*predicates))
    return query


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
            on_clause = compiler_metadata.get_on_clause(self.outer_type, self.edge_name,
                                                        self.relative_type)
            if on_clause is None:
                return None
            inner_column = getattr(inner_table.c, on_clause.inner_col)
            return outer_column == inner_column

        def __repr__(self):
            return self.location.query_path.__repr__()
