import logging
from collections import namedtuple, defaultdict

from sqlalchemy import select, and_

from graphql_compiler.compiler.ir_lowering_sql.query_state_manager import QueryState
from ..compiler.helpers import Location
from .ir_lowering_sql.sql_blocks import SqlBlocks

logger = logging.getLogger(__name__)


Dependency = namedtuple('Dependency', ['from_location', 'to_location', 'from_column', 'to_column', 'to_state'])


class RootQuery(object):
    def __init__(self, compiler_metadata):
        self.compiler_metadata = compiler_metadata
        self.selections = []
        self.relations = []
        self.predicates = []
        self.dependencies = []
        self.from_clause = None
        self.output_location_to_table = {}

    def add_selection(self, selection):
        self.selections.append(selection)

    def add_relation(self, relation):
        self.relations.append(relation)

    def add_predicate(self, predicate):
        self.predicates.append(predicate)

    def add_dependency(self, dependency):
        self.dependencies.append(dependency)


    @property
    def query(self):
        from_clause = self.create_from_clause()
        predicate_stmts = [
            predicate.to_sql(self.output_location_to_table, self.compiler_metadata) for
            predicate in self.predicates
        ]
        selections_stmts = [
            selection.to_sql(self.output_location_to_table, self.compiler_metadata, aggregate=False) for
            selection in self.selections
        ]
        return (
            select(selections_stmts)
            .select_from(from_clause)
            .where(and_(*predicate_stmts))
        )

    @property
    def cte(self):
        selection_location_to_column = defaultdict(set)
        selection_location_to_state = {}
        for selection in self.selections:
            selection_location_to_column[selection.location].add(selection.field_name)
            selection_location_to_state[selection.location] = selection.query_state
        for dependency in self.dependencies:
            if dependency.from_column not in selection_location_to_column[dependency.from_location]:
                self.add_selection(SqlBlocks.Selection(
                    field_name=dependency.from_column,
                    alias=None,
                    query_state=selection_location_to_state[dependency.from_location]
                ))


        return self.query.cte()

    def create_from_clause(self):

        """Create a FROM clause, with the appropriate JOIN statements."""
        # todo: This should probably be a lowering pass
        if len(self.relations) == 0:
            raise AssertionError('Cannot join 0 tables.')
        # pass 1: Ignore recursive and optional
        first_relation = self.relations[0]
        table = first_relation.get_table(self.compiler_metadata).alias()
        from_clause = table  # start with selecting from the first supplied table
        # store output locations separately from the actual locations
        self.output_location_to_table = {first_relation.location: table}
        raw_location_to_table = {first_relation.location: (table, first_relation)}
        recursions = []
        optionals = []
        for relation in self.relations[1:]:
            if relation.in_recursive:
                recursions.append(relation)
                continue
            if relation.in_optional:
                optionals.append(relation)
            # get the next table to join
            raw_location = relation.location
            outer_table, outer_relation = raw_location_to_table[
                Location(relation.location.query_path[:-1])]
            location = SqlEmitter.patch_relation_location(relation)
            table = relation.get_table(self.compiler_metadata).alias()
            raw_location_to_table[raw_location] = (table, relation)
            join_unnecessary = outer_table.element == table.element and outer_relation.relative_type != relation.relative_type
            if join_unnecessary:
                self.output_location_to_table[location] = outer_table
                continue
            self.output_location_to_table[location] = table
            on_clause = relation.to_sql(outer_table, table, self.compiler_metadata)
            if relation.in_optional:
                from_clause = from_clause.outerjoin(table, onclause=on_clause)
            else:
                from_clause = from_clause.join(table, onclause=on_clause)
        return from_clause

class OptionalQuery(RootQuery):

    def add_selection(self, selection):
        self.selections.append(selection)

    def add_relation(self, relation):
        self.relations.append(relation)

    def add_predicate(self, predicate):
        self.predicates.append(predicate)

    def add_dependency(self, dependency):
        self.dependencies.append(dependency)


    def create_from_clause(self):

        """Create a FROM clause, with the appropriate JOIN statements."""
        # todo: This should probably be a lowering pass
        if len(self.relations) == 0:
            raise AssertionError('Cannot join 0 tables.')
        # pass 1: Ignore recursive and optional
        first_relation = self.relations[0]
        table = first_relation.get_table(self.compiler_metadata).alias()
        from_clause = table  # start with selecting from the first supplied table
        # store output locations separately from the actual locations
        self.output_location_to_table = {first_relation.location: table}
        raw_location_to_table = {first_relation.location: (table, first_relation)}
        recursions = []
        optionals = []
        for relation in self.relations[1:]:
            if relation.in_recursive:
                recursions.append(relation)
                continue
            if relation.in_optional:
                optionals.append(relation)
            # get the next table to join
            raw_location = relation.location
            outer_table, outer_relation = raw_location_to_table[
                Location(relation.location.query_path[:-1])]
            location = SqlEmitter.patch_relation_location(relation)
            table = relation.get_table(self.compiler_metadata).alias()
            raw_location_to_table[raw_location] = (table, relation)
            join_unnecessary = outer_table.element == table.element and outer_relation.relative_type != relation.relative_type
            if join_unnecessary:
                self.output_location_to_table[location] = outer_table
                continue
            self.output_location_to_table[location] = table
            on_clause = relation.to_sql(outer_table, table, self.compiler_metadata)
            if relation.in_optional:
                from_clause = from_clause.outerjoin(table, onclause=on_clause)
            else:
                from_clause = from_clause.join(table, onclause=on_clause)
        return from_clause

class SqlEmitter(object):
    def __init__(self, sql_blocks):
        """SQL IR container."""
        self.sql_blocks = sql_blocks

    def compile(self, compiler_metadata):
        root_selections = []
        root_links = []
        root_predicates = []
        root_relations = []

        optional_selections = []
        optional_links = []
        optional_predicates = []
        optional_relations = []

        location_to_table = {}


        for block in self.sql_blocks:
            if isinstance(block, SqlBlocks.Selection):
                if block.in_optional:
                    optional_selections.append(block)
                else:
                    root_selections.append(block)
            elif isinstance(block, SqlBlocks.LinkSelection):
                root_links.append(block)
            elif isinstance(block, SqlBlocks.Predicate):
                if block.in_optional:
                    optional_predicates.append(block)
                else:
                    root_predicates.append(block)
            elif isinstance(block, SqlBlocks.Relation):
                if block.in_optional:
                    optional_relations.append(block)
                else:
                    root_relations.append(block)

        relation = root_relations[0]
        table = relation.get_table(compiler_metadata).alias()
        from_clause = table
        location_to_table[relation.location] = table
        for relation in root_relations[1:]:
            table = relation.get_table(compiler_metadata).alias()
            location_to_table[relation.location] = table
            outer_table = location_to_table[Location(relation.location.query_path[:-1])]
            on_clause = relation.to_sql(outer_table, table, compiler_metadata)
            from_clause = from_clause.join(table, onclause=on_clause)
        root_selection_stmts = [
            selection.to_sql(location_to_table, compiler_metadata, False) for selection in root_selections
        ]

        root_link_selection_stmts = []
        location_to_link_column = {}
        for link in root_links:
            column = link.to_sql(location_to_table, compiler_metadata)
            root_link_selection_stmts.append(column)
            location = Location(query_path=link.location.query_path)
            location_to_link_column[location] = column
        root_predicate_stmts = [
            predicate.to_sql(location_to_table, compiler_metadata) for predicate in
            root_predicates
        ]
        root_cte = (
            select(root_selection_stmts + root_link_selection_stmts)
            .select_from(from_clause)
            .where(and_(*root_predicate_stmts))
        ).cte()
        for relation in root_relations:
            location_to_table[relation.location] = root_cte

        for selection in root_selections:
            if selection.alias is not None:
                selection.field_name = selection.alias
        cte_selection_stmts = [
            selection.to_sql(location_to_table, compiler_metadata, False, True) for
            selection in root_selections
        ]
        from_clause = root_cte
        if len(optional_relations) >= 1:
            print('hi')
        for relation in optional_relations:
            table = relation.get_table(compiler_metadata).alias()
            location_to_table[relation.location] = table
            outer_column_name = None
            if relation.location in location_to_link_column:
                outer_column = location_to_link_column[relation.location]
                outer_column_name = outer_column.name
            outer_table = location_to_table[Location(relation.location.query_path[:-1])]
            on_clause = relation.to_sql(outer_table, table, compiler_metadata, outer_column_name)
            from_clause = from_clause.outerjoin(table, onclause=on_clause)
        optional_selection_stmts = [
            selection.to_sql(location_to_table, compiler_metadata, False) for
            selection in optional_selections
        ]
        selection_stmts = cte_selection_stmts + optional_selection_stmts
        optional_predicates = [
            predicate.to_sql(location_to_table, compiler_metadata) for predicate in
            optional_predicates
        ]

        root_query = (
            select(selection_stmts)
            .select_from(from_clause)
            .where(and_(*optional_predicates))
        )

        return root_query











    # def compile(self, compiler_metadata):
    #     root_query, optional_queries = self.get_queries(compiler_metadata)
    #     if len(optional_queries) >= 1:
    #         print('hi')
    #         return
    #     return root_query.query
    #
    # def get_queries(self, compiler_metadata):
    #     root_query = RootQuery(compiler_metadata)
    #     optional_queries = {}
    #     for block in self.sql_blocks:
    #         if block.in_optional:
    #             if block.optional_id not in optional_queries:
    #                 optional_queries[block.optional_id] = OptionalQuery(compiler_metadata)
    #         if isinstance(block, SqlBlocks.Selection):
    #             if not block.in_optional and not block.in_recursive:
    #                 root_query.add_selection(block)
    #             if block.in_optional:
    #                 optional_queries[block.optional_id].add_selection(block)
    #
    #         if isinstance(block, SqlBlocks.Predicate):
    #             if not block.in_optional and not block.in_recursive:
    #                 root_query.add_predicate(block)
    #             if block.in_optional:
    #                 optional_queries[block.optional_id].add_predicate(block)
    #         if isinstance(block, SqlBlocks.Relation):
    #             if not block.in_optional and not block.in_recursive:
    #                 root_query.add_relation(block)
    #             if block.in_optional:
    #                 from_location, to_location, from_column, to_column = block.get_dependency_fields(compiler_metadata)
    #                 dependency = Dependency(from_location, to_location, from_column, to_column)
    #                 root_query.add_dependency(dependency)
    #                 optional_queries[block.optional_id].add_dependency(dependency)
    #                 optional_queries[block.optional_id].add_relation(block)
    #     return root_query, list(optional_queries.values())
    #
    # # @staticmethod
    # # def group_sql_blocks(sql_blocks):
    # #     """Group the SQL blocks by type, preserving order"""
    # #     relations, predicates, groups, folds = [], [], [], []
    # #     for block in sql_blocks:
    # #         if isinstance(block, SqlBlocks.Selection):
    # #             if block.in_fold:
    # #                 folds.append(block)
    # #             else:
    # #                 groups.append(block)
    # #         elif isinstance(block, SqlBlocks.Relation):
    # #             relations.append(block)
    # #         elif isinstance(block, SqlBlocks.Predicate):
    # #             predicates.append(block)
    # #         else:
    # #             raise AssertionError("Invalid block encountered in SQL block grouping.")
    # #     return relations, predicates, groups, folds
    # #
    # # def compile(self, compiler_metadata):
    # #     """Compile final query against the supplied compiler_metadata."""
    # #     relations, predicates, groups, folds = self.group_sql_blocks(self.sql_blocks)
    # #     selections = groups + folds
    # #     if len(selections) == 0:
    # #         raise AssertionError('At least 1 column must be marked for output.')
    # #     # we can skip the group_by entirely if nothing is ever within a fold
    # #     perform_group_by = len(folds) != 0
    # #     from_clause, output_location_to_table = self.create_relations(relations, compiler_metadata)
    # #     predicates = [
    # #         predicate.to_sql(output_location_to_table, compiler_metadata) for
    # #         predicate in predicates
    # #     ]
    # #     if not perform_group_by:
    # #         selections = [
    # #             selection.to_sql(output_location_to_table, compiler_metadata, aggregate=False) for
    # #             selection in selections
    # #         ]
    # #         return (
    # #             select(selections)
    # #             .select_from(from_clause)
    # #             .where(and_(*predicates))
    # #         )
    # #     # select all columns defining a group normally
    # #     group_selections = [
    # #         selection.to_sql(output_location_to_table, compiler_metadata, aggregate=False) for
    # #         selection in groups
    # #     ]
    # #
    # #     # convert all columns outside of the group (in fold) to their group aggregate
    # #     fold_selections = [
    # #         fold.to_sql(output_location_to_table, compiler_metadata, aggregate=True) for
    # #         fold in folds
    # #     ]
    # #
    # #     return (
    # #         select(group_selections + fold_selections)
    # #         .select_from(from_clause)
    # #         .where(and_(*predicates))
    # #         # perform grouping on all groups (columns not in a fold)
    # #         .group_by(*group_selections)
    # #     )
    # #
    # #
    # # @staticmethod
    # # def create_relations(relations, compiler_metadata):
    # #     """Create a FROM clause, with the appropriate JOIN statements."""
    # #     # todo: This should probably be a lowering pass
    # #     if len(relations) == 0:
    # #         raise AssertionError('Cannot join 0 tables.')
    # #     # pass 1: Ignore recursive and optional
    # #     first_relation = relations[0]
    # #     table = first_relation.get_table(compiler_metadata).alias()
    # #     from_clause = table  # start with selecting from the first supplied table
    # #     # store output locations separately from the actual locations
    # #     output_location_to_table = {first_relation.location: table}
    # #     raw_location_to_table = {first_relation.location: (table, first_relation)}
    # #     recursions = []
    # #     optionals = []
    # #     for relation in relations[1:]:
    # #         if relation.in_recursive:
    # #             recursions.append(relation)
    # #             continue
    # #         if relation.in_optional:
    # #             optionals.append(relation)
    # #         # get the next table to join
    # #         raw_location = relation.location
    # #         outer_table, outer_relation = raw_location_to_table[Location(relation.location.query_path[:-1])]
    # #         location = SqlEmitter.patch_relation_location(relation)
    # #         table = relation.get_table(compiler_metadata).alias()
    # #         raw_location_to_table[raw_location] = (table, relation)
    # #         join_unnecessary = outer_table.element == table.element and outer_relation.relative_type != relation.relative_type
    # #         if join_unnecessary:
    # #             output_location_to_table[location] = outer_table
    # #             continue
    # #         output_location_to_table[location] = table
    # #         on_clause = relation.to_sql(outer_table, table, compiler_metadata)
    # #         if relation.in_optional:
    # #             from_clause = from_clause.outerjoin(table, onclause=on_clause)
    # #         else:
    # #             from_clause = from_clause.join(table, onclause=on_clause)
    # #     return from_clause, output_location_to_table
    #
    # @staticmethod
    # def patch_relation_location(relation):
    #     '''
    #     Strip runs from the location. This way, if we are recursing on Table, and the actual
    #     path is Root -> Table -> Table -> SomeOtherTable, we make this match the OutputContext
    #     QueryPath, which will be Root -> Table -> SomeOtherTable (no regard for recursion)
    #     This doubly ensures that the last table joined is the one used for output, because both
    #     the recursive relation with path Root -> Table -> Table -> SomeOtherTable and the one with
    #     path Root -> Table -> SomeOtherTable will have assigned location
    #     Root -> Table -> SomeOtherTable, but with the later element of the recursion overriding the
    #     former.
    #     '''
    #     if relation.in_recursive:
    #         query_path = [relation.location.query_path[0]]
    #         for loc in relation.location.query_path[1:]:
    #             if loc != query_path[-1]:
    #                 query_path.append(loc)
    #         relation.location = Location(tuple(query_path))
    #     return relation.location


def emit_code_from_ir(sql_blocks, compiler_metadata):
    return SqlEmitter(sql_blocks).compile(compiler_metadata)