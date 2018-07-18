import logging
from collections import namedtuple

from sqlalchemy import select, and_, literal_column

from ..compiler.helpers import Location
from .ir_lowering_sql.sql_blocks import SqlBlocks, to_query

logger = logging.getLogger(__name__)


Dependency = namedtuple('Dependency', ['from_location', 'to_location', 'from_column', 'to_column', 'to_state'])


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
        optional_predicates = []
        optional_relations = []

        recursive_relations = []
        recursive_selections = []

        location_to_table = {}

        in_recursion = False
        saved_blocks = []
        for block in self.sql_blocks:
            if isinstance(block, SqlBlocks.Selection):
                if in_recursion and not block.is_recursive:
                    saved_blocks.append(block)
                elif block.in_optional:
                    optional_selections.append(block)
                elif block.is_recursive:
                    recursive_selections.append(block)
                else:
                    root_selections.append(block)
            elif isinstance(block, SqlBlocks.LinkSelection):
                root_links.append(block)
            elif isinstance(block, SqlBlocks.Predicate):
                if in_recursion and not block.is_recursive:
                    saved_blocks.append(block)
                if block.in_optional:
                    optional_predicates.append(block)
                else:
                    root_predicates.append(block)
            elif isinstance(block, SqlBlocks.StartRecursion):
                in_recursion = True
            elif isinstance(block, SqlBlocks.EndRecursion):
                in_recursion = False
            elif isinstance(block, SqlBlocks.Relation):
                if in_recursion and not block.is_recursive:
                    saved_blocks.append(block)
                elif block.in_optional:
                    optional_relations.append(block)
                elif block.is_recursive:
                    recursive_relations.append(block)
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
            if link.is_recursive:
                column = link.to_sql(location_to_table, compiler_metadata, primary_key=True)
            else:
                column = link.to_sql(location_to_table, compiler_metadata, primary_key=False)
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
        recursive_queries = []
        for relation in recursive_relations:
            on_clause = compiler_metadata.get_on_clause(relation.relative_type, relation.edge_name, None)
            recursive_table = relation.get_table(compiler_metadata)
            outer_column = location_to_link_column[relation.location]
            cte_column_name = outer_column.name
            outer_table = recursive_table.alias()
            table = recursive_table.alias()
            primary_key = [column for column in table.c if column.primary_key][0]
            anchor_query = (
                select([
                    primary_key.label(on_clause.inner_col),
                    primary_key.label(on_clause.outer_col),
                    literal_column('0').label('__depth_internal_name'),
                    primary_key.concat(',').label('path'),
                    ])
                    .select_from(
                    table.join(root_cte, root_cte.c[cte_column_name] == primary_key)
                )
            )
            recursive_cte = anchor_query.cte(recursive=True)
            recursive_query = (
                select([
                    recursive_cte.c[on_clause.inner_col],
                    table.c[on_clause.outer_col],
                    (recursive_cte.c['__depth_internal_name'] + 1).label('__depth_internal_name'),
                ])
                    .select_from(
                    table.join(recursive_cte, table.c[on_clause.inner_col] == recursive_cte.c[on_clause.outer_col])
                ).where(recursive_cte.c['__depth_internal_name'] < relation.recursion_depth)
            )
            recursive_query = recursive_cte.union_all(recursive_query)
            recursive_queries.append(recursive_query)
            pk = [column for column in outer_table.c if column.primary_key][0]
            from_clause = from_clause.join(recursive_query, recursive_query.c[on_clause.inner_col] == root_cte.c[cte_column_name])
            from_clause = from_clause.join(outer_table, pk == recursive_query.c[on_clause.outer_col])
            location_to_table[relation.location] = outer_table


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
        recursive_selection_stmts = [
            selection.to_sql(location_to_table, compiler_metadata, False) for
            selection in recursive_selections
        ]

        selection_stmts = cte_selection_stmts + optional_selection_stmts + recursive_selection_stmts
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

def emit_code_from_ir(sql_blocks, compiler_metadata):
    sql_blocks, tree_root = sql_blocks
    result = to_query(tree_root, compiler_metadata)
    return result
    # return SqlEmitter(sql_blocks).compile(compiler_metadata)