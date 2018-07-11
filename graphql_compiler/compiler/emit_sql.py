import logging

from sqlalchemy import select, and_

from ..compiler.helpers import Location
from .ir_lowering_sql.sql_blocks import SqlBlocks

logger = logging.getLogger(__name__)


class SqlEmitter(object):
    def __init__(self, sql_blocks):
        """SQL IR container."""
        self.sql_blocks = sql_blocks

    @staticmethod
    def group_sql_blocks(sql_blocks):
        """Group the SQL blocks by type, preserving order"""
        relations, predicates, groups, folds = [], [], [], []
        for block in sql_blocks:
            if isinstance(block, SqlBlocks.Selection):
                if block.in_fold:
                    folds.append(block)
                else:
                    groups.append(block)
            elif isinstance(block, SqlBlocks.Relation):
                relations.append(block)
            elif isinstance(block, SqlBlocks.Predicate):
                predicates.append(block)
            else:
                raise AssertionError("Invalid block encountered in SQL block grouping.")
        return relations, predicates, groups, folds

    def compile(self, compiler_metadata):
        """Compile final query against the supplied compiler_metadata."""
        relations, predicates, groups, folds = self.group_sql_blocks(self.sql_blocks)
        selections = groups + folds
        if len(selections) == 0:
            raise AssertionError('At least 1 column must be marked for output.')
        # we can skip the group_by entirely if nothing is ever within a fold
        perform_group_by = len(folds) != 0
        from_clause, output_location_to_table = self.create_relations(relations, compiler_metadata)
        predicates = [
            predicate.to_sql(output_location_to_table, compiler_metadata) for
            predicate in predicates
        ]
        if not perform_group_by:
            selections = [
                selection.to_sql(output_location_to_table, compiler_metadata, aggregate=False) for
                selection in selections
            ]
            return (
                select(selections)
                .select_from(from_clause)
                .where(and_(*predicates))
            )
        # select all columns defining a group normally
        group_selections = [
            selection.to_sql(output_location_to_table, compiler_metadata, aggregate=False) for
            selection in groups
        ]

        # convert all columns outside of the group (in fold) to their group aggregate
        fold_selections = [
            fold.to_sql(output_location_to_table, compiler_metadata, aggregate=True) for
            fold in folds
        ]

        return (
            select(group_selections + fold_selections)
            .select_from(from_clause)
            .where(and_(*predicates))
            # perform grouping on all groups (columns not in a fold)
            .group_by(*group_selections)
        )

    @staticmethod
    def create_relations(relations, compiler_metadata):
        """Create a FROM clause, with the appropriate JOIN statements."""
        # todo: This should probably be a lowering pass
        if len(relations) == 0:
            raise AssertionError('Cannot join 0 tables.')
        first_relation = relations[0]
        table = first_relation.get_table(compiler_metadata).alias()
        from_clause = table  # start with selecting from the first supplied table
        # store output locations separately from the actual locations
        output_location_to_table = {first_relation.location: table}
        raw_location_to_table = {first_relation.location: (table, first_relation)}
        for relation in relations[1:]:
            # get the next table to join
            raw_location = relation.location
            outer_table, outer_relation = raw_location_to_table[Location(relation.location.query_path[:-1])]
            location = SqlEmitter.patch_relation_location(relation)
            table = relation.get_table(compiler_metadata).alias()
            raw_location_to_table[raw_location] = (table, relation)
            join_unnecessary = outer_table.element == table.element and outer_relation.relative_type != relation.relative_type
            if join_unnecessary:
                output_location_to_table[location] = outer_table
                continue
            output_location_to_table[location] = table
            on_clause = relation.to_sql(outer_table, table, compiler_metadata)
            if relation.in_optional:
                from_clause = from_clause.outerjoin(table, onclause=on_clause)
            else:
                from_clause = from_clause.join(table, onclause=on_clause)
        return from_clause, output_location_to_table

    @staticmethod
    def patch_relation_location(relation):
        '''
        Strip runs from the location. This way, if we are recursing on Table, and the actual
        path is Root -> Table -> Table -> SomeOtherTable, we make this match the OutputContext
        QueryPath, which will be Root -> Table -> SomeOtherTable (no regard for recursion)
        This doubly ensures that the last table joined is the one used for output, because both
        the recursive relation with path Root -> Table -> Table -> SomeOtherTable and the one with
        path Root -> Table -> SomeOtherTable will have assigned location
        Root -> Table -> SomeOtherTable, but with the later element of the recursion overriding the
        former.
        '''
        if relation.in_recursive:
            query_path = [relation.location.query_path[0]]
            for loc in relation.location.query_path[1:]:
                if loc != query_path[-1]:
                    query_path.append(loc)
            relation.location = Location(tuple(query_path))
        return relation.location


def emit_code_from_ir(sql_blocks, compiler_metadata):
    return SqlEmitter(sql_blocks).compile(compiler_metadata)