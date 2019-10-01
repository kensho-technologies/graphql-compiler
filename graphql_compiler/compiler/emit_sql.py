# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
import six
import sqlalchemy

from . import blocks
from .helpers import FoldScopeLocation, get_edge_direction_and_name
from .expressions import FoldedContextField

# Some reserved column names used in emitted SQL queries
CTE_DEPTH_NAME = '__cte_depth'
CTE_KEY_NAME = '__cte_key'


def _traverse_and_validate_blocks(ir):
    """Yield all blocks, while validating consistency."""
    found_query_root = False
    found_global_operations_block = False

    global_only_blocks = (blocks.ConstructResult,)
    globally_allowed_blocks = (blocks.ConstructResult, blocks.Filter)

    for block in ir.ir_blocks:
        if isinstance(block, blocks.QueryRoot):
            found_query_root = True
        else:
            if not found_query_root:
                raise AssertionError(u'Found block {} before QueryRoot: {}'
                                     .format(block, ir.ir_blocks))

        if isinstance(block, blocks.GlobalOperationsStart):
            if found_global_operations_block:
                raise AssertionError(u'Found duplicate GlobalOperationsStart: {}'
                                     .format(ir.ir_blocks))
            found_global_operations_block = True
        else:
            if found_global_operations_block:
                if not isinstance(block, globally_allowed_blocks):
                    raise AssertionError(u'Only {} are allowed after GlobalOperationsBlock. '
                                         u'Found {} in {}.'
                                         .format(globally_allowed_blocks, block, ir.ir_blocks))
            else:
                if isinstance(block, global_only_blocks):
                    raise AssertionError(u'Block {} is only allowed after GlobalOperationsBlock: {}'
                                         .format(block, ir.ir_blocks))
        yield block


def _find_columns_used_outside_folds(sql_schema_info, ir):
    """For each query path, find which columns are used in any way."""
    used_columns = {}

    # Find filters used
    for location, location_info in ir.query_metadata_table.registered_locations:
        if isinstance(location, FoldScopeLocation):
            continue
        for filter_info in ir.query_metadata_table.get_filter_infos(location):
            for field in filter_info.fields:
                used_columns.setdefault(location.query_path, set()).add(field)

    # Find foreign keys used
    for location, location_info in ir.query_metadata_table.registered_locations:
        for child_location in ir.query_metadata_table.get_child_locations(location):
            if isinstance(child_location, FoldScopeLocation):
                continue
            edge_direction, edge_name = get_edge_direction_and_name(child_location.query_path[-1])
            vertex_field_name = '{}_{}'.format(edge_direction, edge_name)
            edge = sql_schema_info.join_descriptors[location_info.type.name][vertex_field_name]
            used_columns.setdefault(location.query_path, set()).add(edge.from_column)
            used_columns.setdefault(child_location.query_path, set()).add(edge.to_column)

            # A recurse implies an outgoing foreign key usage
            child_location_info = ir.query_metadata_table.get_location_info(child_location)
            if child_location_info.recursive_scopes_depth > location_info.recursive_scopes_depth:
                used_columns.setdefault(child_location.query_path, set()).add(edge.from_column)

    # Find outputs used
    for _, output_info in ir.query_metadata_table.outputs:
        if isinstance(output_info.location, FoldScopeLocation):
            continue
        query_path = output_info.location.query_path
        used_columns.setdefault(query_path, set()).add(output_info.location.field)

    # Find tags used
    for _, output_info in ir.query_metadata_table.tags:
        if isinstance(output_info.location, FoldScopeLocation):
            continue
        query_path = output_info.location.query_path
        used_columns.setdefault(query_path, set()).add(output_info.location.field)

    return used_columns


def _find_folded_outputs(ir):
    """For each fold path, find outputs"""
    folded_outputs = {}
    # Find outputs used for each fold path
    for _, output_info in ir.query_metadata_table.outputs:
        if isinstance(output_info.location, FoldScopeLocation):
            fold_path = output_info.location.fold_path
            folded_outputs.setdefault(fold_path, set()).add(output_info.location)
    return folded_outputs


class CompilationState(object):
    """Mutable class used to keep track of state while emitting a sql query."""

    def __init__(self, sql_schema_info, ir):
        """Initialize a CompilationState, setting the current location at the root of the query."""
        # Metadata
        self._sql_schema_info = sql_schema_info
        self._ir = ir
        self._used_columns = _find_columns_used_outside_folds(sql_schema_info, ir)
        self._all_folded_outputs = _find_folded_outputs(ir)
        self._in_fold = False

        # Current query location state. Only mutable by calling _relocate.
        self._current_location = None  # the current location in the query. None means global.
        self._current_alias = None  # a sqlalchemy table Alias at the current location
        # TODO: keys should be (query_path, fold_path). Aliases not inside a fold, fold_path = None
        self._aliases = {}  # mapping marked query paths to table _Aliases representing them
        self._relocate(ir.query_metadata_table.root_location)
        self._came_from = {}  # mapping aliases to the column used to join into them.

        # The query being constructed as the IR is processed
        self._from_clause = self._current_alias  # the main sqlalchemy Selectable
        self._outputs = []  # sqlalchemy Columns labelled correctly for output
        self._filters = []  # sqlalchemy Expressions to be used in the where clause

        # The folded subquery being constructed as the IR is processed (reset for each fold)
        self._fold_from_clause = None  # the main sqlalchemy Selectable for the fold subquery
        self._fold_outputs = []  # sqlalchemy fold subquery outputs
        self._fold_group_by = []  # sqlalchemy fold subquery Columns to GROUP BY

        # Information needed to LEFT JOIN fold subquery to main Selectable (reset for each fold)
        self._pre_fold_location = None  # the current Location prior to fold
        self._fold_location = None  # the fold's FoldScopeLocation
        self._fold_join_vertex_field = None  # field to perform LEFT JOIN on
        self._fold_location_info = None # This tells us the vertex that we are folding on

        # Information to keep track of fold aliases
        self._folded_output_aliases = {}  # mapping FoldScopeLocations to their intermediate alias
        self._folded_output_count = 1
        self._fold_count = 1

    def _relocate(self, new_location):
        """Move to a different location in the query, updating the _alias."""
        self._current_location = new_location
        if (self._current_location.query_path, None) in self._aliases:
            self._current_alias = self._aliases[(self._current_location.query_path, None)]
        else:
            self._current_alias = (
                self._sql_schema_info.vertex_name_to_table[self._current_classname].alias()
            )

    def _fold_relocate(self, new_location):
        """Move to a different location in the query, updating the _alias."""
        self._current_location = new_location
        if (self._current_location.query_path, self._fold_location) in self._aliases:
            self._current_alias = self._aliases[(self._current_location.query_path, self._fold_location)]
        else:
            self._current_alias = (
                self._sql_schema_info.vertex_name_to_table[self._fold_location_info.type.name].alias()
            )
            self._aliases[(self._current_location.query_path, self._fold_location)] = self._current_alias

    def _join_to_parent_location(self, parent_alias, from_column, to_column, optional):
        """Join the current location to the parent location using the column names specified."""
        self._came_from[self._current_alias] = self._current_alias.c[to_column]

        if self._is_in_optional_scope() and not optional:
            # For mandatory edges in optional scope, we emit LEFT OUTER JOIN and enforce the
            # edge being mandatory with additional filters in the WHERE clause.
            #
            # This is some tricky logic. To prevent regression, here's some caution against
            # solutions that might seem simpler, but are not correct:
            # 1. You might think it's simpler to just use an INNER JOIN for mandatory edges in
            #    optional scope. However, if there is a LEFT JOIN miss, the NULL value resulting
            #    from it will not match anything in this INNER JOIN, and the row will be removed.
            #    As a result, @optional semantics will not be preserved.
            # 2. You might think that a cleaner solution is performing all the mandatory traversals
            #    first in subqueries, and joining those subqueries with LEFT OUTER JOIN. This
            #    approach is incorrect because a mandatory edge traversal miss inside an optional
            #    scope is supposed to invalidate the whole result. However, with this solution the
            #    result will still appear.
            self._filters.append(sqlalchemy.or_(
                self._came_from[self._current_alias].isnot(None),
                self._came_from[parent_alias].is_(None)))

        # Join to where we came from
        self._from_clause = self._from_clause.join(
            self._current_alias,
            onclause=(parent_alias.c[from_column] == self._current_alias.c[to_column]), # modified to use the same indexing as in the fold method
            isouter=self._is_in_optional_scope())

    @property
    def _current_location_info(self):
        """Get the LocationInfo of the current location in the query."""
        return self._ir.query_metadata_table.get_location_info(self._current_location)

    @property
    def _current_classname(self):
        """Get the string class name of the current location in the query."""
        return self._current_location_info.type.name

    def _is_in_optional_scope(self):
        if self._current_location is None:
            return False
        return self._current_location_info.optional_scopes_depth > 0

    def backtrack(self, previous_location):
        """Execute a Backtrack Block."""
        self._relocate(previous_location)

    def traverse(self, vertex_field, optional):
        """Execute a Traverse Block."""
        if self._in_fold:
            raise NotImplementedError("Traversals inside a fold are not implemented yet.")
        # Follow the edge
        previous_alias = self._current_alias
        edge = self._sql_schema_info.join_descriptors[self._current_classname][vertex_field]
        self._relocate(self._current_location.navigate_to_subpath(vertex_field))
        self._join_to_parent_location(previous_alias, edge.from_column, edge.to_column, optional)

    def recurse(self, vertex_field, depth):
        """Execute a Recurse Block."""
        if self._in_fold:
            raise AssertionError("Recurse inside a fold is not allowed.")
        previous_alias = self._current_alias
        edge = self._sql_schema_info.join_descriptors[self._current_classname][vertex_field]
        if not self._current_alias.primary_key:
            raise AssertionError(u'The table for vertex {} has no primary key specified. This '
                                 u'information is required to emit a @recurse directive.'
                                 .format(self._current_classname))
        if len(self._current_alias.primary_key) > 1:
            raise NotImplementedError(u'The table for vertex {} has a composite primary key {}. '
                                      u'The SQL backend does not support @recurse on tables with '
                                      u'composite primary keys.'
                                      .format(self._current_classname,
                                              self._current_alias.primary_key))
        primary_key = self._current_alias.primary_key[0].name
        self._relocate(self._current_location.navigate_to_subpath(vertex_field))

        # Sanitize literal columns to be used in the query
        if not isinstance(depth, int):
            raise AssertionError(u'Depth must be a number. Received {} {}'
                                 .format(type(depth), depth))
        literal_depth = sqlalchemy.literal_column(str(depth))
        literal_0 = sqlalchemy.literal_column('0')
        literal_1 = sqlalchemy.literal_column('1')

        # Find which columns should be selected
        used_columns = sorted(self._used_columns[self._current_location.query_path])

        # The base of the recursive CTE selects all needed columns and sets the depth to 0
        base = sqlalchemy.select(
            [self._current_alias.c[col] for col in used_columns] + [
                self._current_alias.c[primary_key].label(CTE_KEY_NAME),
                literal_0.label(CTE_DEPTH_NAME),
            ]
        ).cte(recursive=True)

        # The recursive step selects all needed columns, increments the depth, and joins to the base
        step = self._current_alias.alias()
        self._current_alias = base.union_all(sqlalchemy.select(
            [step.c[col] for col in used_columns] + [
                base.c[CTE_KEY_NAME].label(CTE_KEY_NAME),
                (base.c[CTE_DEPTH_NAME] + literal_1).label(CTE_DEPTH_NAME),
            ]
        ).select_from(
            base.join(step, onclause=base.c[edge.from_column] == step.c[edge.to_column])
        ).where(
            base.c[CTE_DEPTH_NAME] < literal_depth)
        )

        # TODO(bojanserafimov): Postgres implements CTEs by executing them ahead of everything
        #                       else. The onclause into the CTE is not going to filter the
        #                       recursive base case to a small set of rows, but instead the CTE
        #                       will be created for all hypothetical starting points.
        #                       To optimize for Postgres performance, we should instead wrap the
        #                       part of the query preceding this @recurse into a CTE, and use
        #                       it as the base case.
        self._join_to_parent_location(previous_alias, primary_key, CTE_KEY_NAME, False)

    def start_global_operations(self):
        """Execute a GlobalOperationsStart block."""
        if self._current_location is None:
            raise AssertionError(u'CompilationState is already in global scope.')
        self._current_location = None

    def filter(self, predicate):
        """Execute a Filter Block."""
        if self._in_fold or isinstance(predicate.left, FoldedContextField) or isinstance(predicate.right, FoldedContextField):
            raise NotImplementedError("Filters inside a fold are not implemented yet.")

        sql_expression = predicate.to_sql(self._aliases, self._current_alias, self._folded_output_aliases)
        if self._is_in_optional_scope():
            sql_expression = sqlalchemy.or_(sql_expression,
                                            self._came_from[self._current_alias].is_(None))
        self._filters.append(sql_expression)

    def fold(self, fold_scope_location):
        """Begin execution of a Fold Block"""
        if self._fold_from_clause or self._in_fold:
            raise AssertionError(u'Reached an invalid fold state.')


        # begin the fold
        self._in_fold = True
        self._pre_fold_location = self._current_location
        self._fold_location = fold_scope_location
        self._fold_location_info = self._ir.query_metadata_table.get_location_info(fold_scope_location)
        self._fold_relocate(fold_scope_location.base_location)
        self._fold_from_clause = self._current_alias

        # collect edge information to join the fold subquery to the main selectable
        edge_direction = fold_scope_location.fold_path[0][0]
        edge_name = fold_scope_location.fold_path[0][1]
        self._fold_join_vertex_field = "{}_{}".format(edge_direction, edge_name)
        edge = self._sql_schema_info.join_descriptors[
            self._current_classname][self._fold_join_vertex_field]


        # find outputs for this fold in self._all_folded_outputs and add to self._fold_outputs
        if fold_scope_location.fold_path in self._all_folded_outputs:
            for fold_output in self._all_folded_outputs[fold_scope_location.fold_path]:
                if fold_output.field == '_x_count':
                    raise NotImplementedError(u'_x_count not implemented in SQL')
                # create an intermediate output name, store the alias, and increment the counter
                # for the next intermediate alias
                # TODO: give better fold output names
                intermediate_fold_output_name = "fold_output_{}".format(self._folded_output_count)
                self._folded_output_aliases[fold_output] = intermediate_fold_output_name
                self._folded_output_count += 1
                # add array aggregated intermediate output to self._fold_outputs
                self._fold_outputs.append(
                    sqlalchemy.func.array_agg(
                        self._aliases[(
                            fold_output.base_location.at_vertex().query_path, self._fold_location
                        )].c[fold_output.field]
                    ).label(intermediate_fold_output_name)
                )



        # append the subquery field to group by/join on
        self._fold_outputs.append(
            self._aliases[fold_scope_location.base_location.at_vertex().query_path, self._fold_location].c[
                edge.from_column
            ]
        )
        self._fold_group_by.append(
            self._aliases[fold_scope_location.base_location.at_vertex().query_path, self._fold_location].c[
                edge.from_column
            ]
        )

    def unfold(self):
        """Complete the execution of a Fold Block"""
        # Create the folded select statement, updating the fold count and adding the subquery
        # to self._aliases
        folded_subquery = sqlalchemy.select(
            self._fold_outputs
        ).select_from(
            self._fold_from_clause
        ).group_by(
            *self._fold_group_by
        ).alias("folded_subquery_{}".format(self._fold_count))  # TODO: give better subquery names
        self._fold_count += 1
        self._aliases[(self._fold_location.fold_path, None)] = folded_subquery

        # left join to the self._from_clause on self._fold_join_vertex_field
        edge = self._sql_schema_info.join_descriptors[
            self._current_classname][self._fold_join_vertex_field]
        parent_alias = self._aliases[(self._pre_fold_location.query_path, None)] # None because the parent existed outside a fold
        self._from_clause = self._from_clause.outerjoin(
            folded_subquery,
            onclause=(parent_alias.c[edge.to_column] == folded_subquery.c[edge.from_column])
        )

        # reset the folded subquery
        self._fold_from_clause = None
        self._in_fold = False
        self._fold_outputs = []
        self._pre_fold_location = None
        self._fold_location = None
        self._fold_group_by = []
        self._fold_join_vertex_field = None
        self._current_alias = parent_alias
    def mark_location(self):
        """Execute a MarkLocation Block."""
        self._aliases[(self._current_location.query_path, self._fold_location if self._in_fold else None)] = self._current_alias

    def construct_result(self, output_name, field):
        """Execute a ConstructResult Block."""
        self._outputs.append(field.to_sql(self._aliases, self._current_alias, self._folded_output_aliases).label(output_name))

    def get_query(self):
        """After all IR Blocks are processed, return the resulting sqlalchemy query."""
        return sqlalchemy.select(self._outputs).select_from(
            self._from_clause).where(sqlalchemy.and_(*self._filters))


def emit_code_from_ir(sql_schema_info, ir):
    """Return a SQLAlchemy Query from a passed SqlQueryTree.

    Args:
        sql_schema_info: SQLAlchemySchemaInfo containing all relevant schema information
        ir: IrAndMetadata containing query information with lowered blocks

    Returns:
        SQLAlchemy Query
    """
    state = CompilationState(sql_schema_info, ir)
    for block in _traverse_and_validate_blocks(ir):
        if isinstance(block, blocks.QueryRoot):
            pass
        elif isinstance(block, blocks.MarkLocation):
            state.mark_location()
        elif isinstance(block, blocks.Backtrack):
            state.backtrack(block.location)
        elif isinstance(block, blocks.Traverse):
            state.traverse(u'{}_{}'.format(block.direction, block.edge_name), block.optional)
        elif isinstance(block, blocks.Recurse):
            state.recurse(u'{}_{}'.format(block.direction, block.edge_name), block.depth)
        elif isinstance(block, blocks.EndOptional):
            pass
        elif isinstance(block, blocks.Fold):
            state.fold(block.fold_scope_location)
        elif isinstance(block, blocks.Unfold):
            state.unfold()
        elif isinstance(block, blocks.Filter):
            state.filter(block.predicate)
        elif isinstance(block, blocks.GlobalOperationsStart):
            state.start_global_operations()
        elif isinstance(block, blocks.ConstructResult):
            for output_name, field in sorted(six.iteritems(block.fields)):
                state.construct_result(output_name, field)
        else:
            raise NotImplementedError(u'Unsupported block {}.'.format(block))

    return state.get_query()
