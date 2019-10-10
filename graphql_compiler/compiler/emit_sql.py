# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
import six
import sqlalchemy

from . import blocks
from .expressions import FoldedContextField
from .helpers import FoldScopeLocation, get_edge_direction_and_name


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
    """For each query path, find which columns are used outside of a fold output."""
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
    """For each fold path, find outputs."""
    folded_outputs = {}
    # Find outputs used for each fold path
    for _, output_info in ir.query_metadata_table.outputs:
        if isinstance(output_info.location, FoldScopeLocation):
            fold_path = output_info.location.fold_path
            folded_outputs.setdefault(fold_path, set()).add(output_info.location)
    return folded_outputs


class SQLFoldObject(object):
    """Immutable object used to collect info for folds in order to ensure correct code emission"""
    def __init__(self, inner_vertex_table,
                 outer_vertex_table,
                 join_info):
        """Create an SQLFoldObject with table, type, and join information supplied by the IR."""
        self._inner_vertex_alias = inner_vertex_table  # SQLAlchemy table alias output columns in fold are selected from
        self._outer_vertex_alias = outer_vertex_table  # SQLAlchemy table alias for vertex outside of fold

        # 2-tuple:
        #  edge: join descriptor for the columns used to join outer and inner vertex
        #  self._current_alias: unaliased version of the outer vertex table used outside the subquery
        #
        self._join_info = join_info
        self._outputs = []
        self._group_by = []

    @property
    def outputs(self):
        """Get the output columns for the fold subquery."""
        return self._outputs

    @property
    def group_by(self):
        """Get the columns to group by for the fold subquery."""
        return self._group_by

    @property
    def inner_vertex_alias(self):
        """Get the SQLAlchemy table corresponding to the innermost vertex from the fold."""
        return self._inner_vertex_alias

    @property
    def outer_vertex_alias(self):
        """Get the SQLAlchemy table corresponding to vertex immediately outside the fold."""
        return self._outer_vertex_alias

    @property
    def join_info(self):
        """Get a tuple containing edge and table info for the joins within the subquery."""
        return self._join_info


class UniqueAliasGenerator(object):
    """Immutable class used to generate unique aliases for subqueries and columns """
    def __init__(self):
        """Create unique subquery and column aliases by tracking counters."""
        self._folded_output_count = 1
        self._fold_count = 1

    def generate_subquery(self):
        """Generate a new subquery alias and increment the counter."""
        alias = 'folded_subquery_{}'.format(self._fold_count)
        self._fold_count += 1
        return alias

    def generate_output_column(self):
        """Generate a new output column alias and increment the counter."""
        alias = 'fold_output_{}'.format(self._folded_output_count)
        self._folded_output_count += 1
        return alias


class CompilationState(object):
    """Mutable class used to keep track of state while emitting a sql query."""

    def __init__(self, sql_schema_info, ir):
        """Initialize a CompilationState, setting the current location at the root of the query."""
        # Immutable metadata
        self._sql_schema_info = sql_schema_info
        self._ir = ir
        self._used_columns = _find_columns_used_outside_folds(sql_schema_info, ir)
        self._all_folded_outputs = _find_folded_outputs(ir)

        # Current query location state. Only mutable by calling _relocate.
        self._current_location = None  # the current location in the query. None means global.
        self._current_alias = None  # a sqlalchemy table Alias at the current location
        self._aliases = {}  # mapping marked query paths to table _Aliases representing them
        self._relocate(ir.query_metadata_table.root_location)
        self._came_from = {}  # mapping aliases to the column used to join into them.

        # The query being constructed as the IR is processed
        self._from_clause = self._current_alias  # the main sqlalchemy Selectable
        self._outputs = []  # sqlalchemy Columns labelled correctly for output
        self._filters = []  # sqlalchemy Expressions to be used in the where clause

        self._fold = None
        self._in_fold = False
        self._fold_inner_vertex_location = None
        self._fold_outer_vertex_location = None

        # Maps FoldScopeLocations (i.e., unique fold outputs) to the SQLAlchemy string label used to alias them
        self._fold_output_column_aliases = {}
        self._alias_generator = UniqueAliasGenerator()

    def _relocate(self, new_location):
        """Move to a different location in the query, updating the _alias."""
        self._current_location = new_location
        if (self._current_location.query_path, None) in self._aliases:
            self._current_alias = self._aliases[(self._current_location.query_path, None)]
        else:
            self._current_alias = (
                self._sql_schema_info.vertex_name_to_table[self._current_classname].alias()
            )

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
            onclause=(parent_alias.c[from_column] == self._current_alias.c[to_column]),
            # modified to use the same indexing as in the fold method
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
            raise NotImplementedError('Traversals inside a fold are not implemented yet.')
        # Follow the edge
        previous_alias = self._current_alias
        edge = self._sql_schema_info.join_descriptors[self._current_classname][vertex_field]
        self._relocate(self._current_location.navigate_to_subpath(vertex_field))
        self._join_to_parent_location(previous_alias, edge.from_column, edge.to_column, optional)

    def recurse(self, vertex_field, depth):
        """Execute a Recurse Block."""
        if self._in_fold:
            raise AssertionError('Recurse inside a fold is not allowed.')
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
        with isinstance(predicate.left, FoldedContextField) as left_predicate_folded:
            with isinstance(predicate.right, FoldedContextField) as right_predicate_folded:
                if self._in_fold or left_predicate_folded or right_predicate_folded:
                    raise NotImplementedError('Filters inside a fold are not implemented yet.')

        sql_expression = predicate.to_sql(self._aliases,
                                          self._current_alias,
                                          self._fold_output_column_aliases)
        if self._is_in_optional_scope():
            sql_expression = sqlalchemy.or_(sql_expression,
                                            self._came_from[self._current_alias].is_(None))
        self._filters.append(sql_expression)

    def fold(self, fold_scope_location):
        """Begin execution of a Fold Block."""
        # This method creates the SELECT clause and GROUP BY for the fold subquery.
        #
        # SELECT will contain OuterVertex.uuid, a unique identifier for the
        # OuterVertex determined by the edge descriptor from the vertex immediately outside the fold
        # to the inner vertex where the fold outputs are.
        #
        # NOTE: right now inner vertex denotes both the vertex which is folded on AND the vertex at which the
        # outputs are placed. This is only accurate when there are no traversals inside of the fold. Once
        # functionality for traversals inside folds is introduced the folded vertex will no longer necessarily
        # be the one that has the outputs.
        #
        # SELECT will also contain an ARRAY_AGG for each columns labeled for output inside the fold
        #
        # SELECT will also contain a COUNT(*) if _x_count is referred to somewhere in the query
        #
        # The FROM and JOIN clauses are constructed during the Unfold block.
        #
        # The full subquery will look as follows:
        #
        # SELECT
        #   OuterVertex.uuid <- this value is determined from the edge descriptor
        #   array_agg(InnerVertex.fold_output_column) AS fold_output
        # FROM OuterVertex
        # INNER JOIN ... <- INNER JOINs compiled during Unfold block
        # ON ...
        #          ...
        # INNER JOIN InnerVertex <- INNER JOINs compiled during Unfold block
        # ON ...
        # GROUP BY OuterVertex.uuid

        if self._in_fold:
            raise AssertionError(u'Fold block {} entered while inside another fold block at current location {}.'
                                 .format(fold_scope_location, self._current_location_info))

        # begin the fold
        self._in_fold = True
        # location of vertex that occurs immediately outside fold
        self._fold_outer_vertex_location = self._current_location
        # location of vertex that is folded on
        self._fold_inner_vertex_location = fold_scope_location

        # basic info about the outer vertex and inner vertex
        inner_vertex_alias = self._sql_schema_info.vertex_name_to_table[
            self._ir.query_metadata_table.get_location_info(fold_scope_location).type.name
        ].alias()
        outer_vertex_alias = self._current_alias.alias()

        # collect edge information to join the fold subquery to the main selectable
        edge_direction, edge_name = fold_scope_location.fold_path[0]
        full_edge_name = '{}_{}'.format(edge_direction, edge_name)

        join_descriptor = self._sql_schema_info.join_descriptors[
            self._current_classname][full_edge_name]

        # we will use this to make sure that the join inside
        # the subquery uses one alias of the current table
        # and that the join outside the subquery uses another alias
        join_info = (join_descriptor, self._current_alias)

        self._fold = SQLFoldObject(inner_vertex_alias,
                                   outer_vertex_alias,
                                   join_info)
        # find outputs for this fold in self._all_folded_outputs and add to self._fold_outputs
        if fold_scope_location.fold_path in self._all_folded_outputs:
            for fold_output in self._all_folded_outputs[fold_scope_location.fold_path]:
                if fold_output.field == '_x_count':
                    raise NotImplementedError(u'_x_count not implemented in SQL')

                # making explicit label forces column to have label as opposed to anon_label
                intermediate_fold_output_name = self._alias_generator.generate_output_column() # TODO: this is unnecessary, use fold_output.field
                self._fold_output_column_aliases[fold_output] = intermediate_fold_output_name
                # add array aggregated intermediate output to self._fold_outputs
                self._fold.outputs.append(
                    sqlalchemy.func.array_agg(
                        self._fold.inner_vertex_alias.c[fold_output.field]
                    ).label(intermediate_fold_output_name)
                )

        # the group by field is the unique identifier for the outer vertex
        self._fold.outputs.append(self._fold.outer_vertex_alias.c[join_descriptor.from_column])
        self._fold.group_by.append(self._fold.outer_vertex_alias.c[join_descriptor.from_column])

    def construct_fold_joins(self, edge):
        join_clause = self._fold.outer_vertex_alias
        join_clause = sqlalchemy.join(
            join_clause,
            self._fold.inner_vertex_alias,
            onclause=(self._fold.outer_vertex_alias.c[edge.from_column] ==
                      self._fold.inner_vertex_alias.c[edge.to_column])
        )
        return join_clause

    def construct_fold_subquery(self, subquery_from_clause):
        return sqlalchemy.select(
            self._fold.outputs
        ).select_from(
            subquery_from_clause
        ).group_by(
            *self._fold.group_by
        ).alias(self._alias_generator.generate_subquery())
    def unfold(self):
        """Complete the execution of a Fold Block."""
        # Create the folded select statement
        # left join to the self._from_clause on self._fold_join_vertex_field
        edge, outer_vertex = self._fold.join_info

        subquery_from_clause = self.construct_fold_joins(edge)
        fold_subquery = self.construct_fold_subquery(subquery_from_clause)

        # TODO: This isn't the right key, because it is too vague. self._fold_inner_vertex_location is too specific though
        self._aliases[(self._fold_inner_vertex_location.fold_path, None)] = fold_subquery
        self._from_clause = sqlalchemy.join(
            self._from_clause,
            fold_subquery,
            onclause=(outer_vertex.c[edge.from_column] == fold_subquery.c[edge.from_column]),
            isouter=True
        )
        # this line is necessary because the column referenced in the outputs
        # belongs to the innermost occurrence of the outer vertex's table
        # but we have now aliased and referenced that table again, so we need
        # to replace later substitutions of that column with ones
        # taken from this new alias
        self._aliases[(self._current_location.at_vertex().query_path, None)] = outer_vertex
        # reset the folded subquery
        self._fold = None
        self._in_fold = False
        self._current_alias = outer_vertex

    def mark_location(self):
        """Execute a MarkLocation Block."""
        self._aliases[
            (self._current_location.query_path,
             self._fold_inner_vertex_location if self._in_fold else None)
        ] = self._current_alias

    def construct_result(self, output_name, field):
        """Execute a ConstructResult Block."""
        self._outputs.append(field.to_sql(
            self._aliases,
            self._current_alias,
            self._fold_output_column_aliases
        ).label(output_name))

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
