# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
from collections import namedtuple

import six
import sqlalchemy
from sqlalchemy import select
from sqlalchemy.dialects.mssql.base import MSDialect
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression
from sqlalchemy.sql.compiler import _CompileLabel
from sqlalchemy.sql.expression import BinaryExpression
from sqlalchemy.sql.functions import func

from . import blocks
from ..schema import COUNT_META_FIELD_NAME
from .expressions import ContextField, Expression
from .helpers import FoldScopeLocation, get_edge_direction_and_name


# Some reserved column names used in emitted SQL queries
CTE_DEPTH_NAME = "__cte_depth"
CTE_KEY_NAME = "__cte_key"

# Formatting strings for intermediate queries/outputs from folds
FOLD_OUTPUT_FORMAT_STRING = "fold_output_{}"
FOLD_SUBQUERY_FORMAT_STRING = "folded_subquery_{}"


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
                raise AssertionError(
                    u"Found block {} before QueryRoot: {}".format(block, ir.ir_blocks)
                )

        if isinstance(block, blocks.GlobalOperationsStart):
            if found_global_operations_block:
                raise AssertionError(
                    u"Found duplicate GlobalOperationsStart: {}".format(ir.ir_blocks)
                )
            found_global_operations_block = True
        else:
            if found_global_operations_block:
                if not isinstance(block, globally_allowed_blocks):
                    raise AssertionError(
                        u"Only {} are allowed after GlobalOperationsBlock. "
                        u"Found {} in {}.".format(globally_allowed_blocks, block, ir.ir_blocks)
                    )
            else:
                if isinstance(block, global_only_blocks):
                    raise AssertionError(
                        u"Block {} is only allowed after GlobalOperationsBlock: {}".format(
                            block, ir.ir_blocks
                        )
                    )
        yield block


def _find_columns_used_outside_folds(sql_schema_info, ir):
    """For each query path outside of a fold output, find which columns are used."""
    used_columns = {}

    # Find filters used
    for location, _ in ir.query_metadata_table.registered_locations:
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
            vertex_field_name = "{}_{}".format(edge_direction, edge_name)
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


def _find_tagged_parameters(expression_from_filter: Expression) -> bool:
    """Return True if the expression contains a ContextField (i.e. a tagged parameter)."""
    has_context_fields = False

    def visitor_fn(expression_to_visit: Expression) -> Expression:
        """Update has_context_fields if a ContextField is found."""
        nonlocal has_context_fields
        if isinstance(expression_to_visit, ContextField):
            has_context_fields = True
        return expression_to_visit

    expression_from_filter.visit_and_update(visitor_fn)

    return has_context_fields


def _find_folded_fields(ir):
    """For each fold path, find folded fields (outputs and metafields used in filters)."""
    folded_fields = {}
    # Find outputs used for each fold path.
    for _, output_info in ir.query_metadata_table.outputs:
        if isinstance(output_info.location, FoldScopeLocation):
            fold_path = output_info.location.fold_path
            folded_fields.setdefault(fold_path, set()).add(output_info.location)

    # Add _x_count, if used as a Filter at any Location.
    for location, _ in ir.query_metadata_table.registered_locations:
        for location_filter in ir.query_metadata_table.get_filter_infos(location):
            for field in location_filter.fields:
                if field == COUNT_META_FIELD_NAME:
                    folded_fields.setdefault(location.fold_path, set()).add(
                        location.navigate_to_field(field)
                    )

    return folded_fields


class XMLPathBinaryExpression(BinaryExpression):
    """Special override of BinaryExpression used to trigger `compile_xmlpath` during compile.

    This type of binary expression is used to describe the Selectable selected inside the
    XML PATH subquery. Using an XMLPathBinaryExpression forces the compiler to produce that
    Selectable without aliasing (aka labeling) it. This prevents the string resulting from
    the XML PATH from having extraneous XML tags based on the alias given to the column.
    """


@compiles(_CompileLabel, "default")
def compile_xmlpath(element, compiler, **kw):
    """Suppress labeling when compiling XML PATH subqueries, otherwise compile as usual.

    This method is needed because if XML PATH column is selected with an alias then each
    entry in the resulting array is wrapped in XML tags bearing that alias.
    e.g. `SELECT (SELECT ... FOR XML PATH ('')) AS blah ...` results in a string of the form
    <blah>element1</blah><blah>element2</blah>. Since SQLAlchemy adds labels to all Selectables, we
    must to suppress that labeling.
    """
    if isinstance(element.element, XMLPathBinaryExpression):
        # this indicates that no label should be inserted for this element
        kw.update(
            within_columns_clause=False  # label always gets added if within_columns_clause is True
        )
    return compiler.visit_label(element, **kw)


def _get_xml_path_clause(output_column, predicate_expression):
    """Produce an MSSQL-style XML PATH-based aggregation subquery.

    XML PATH clause aggregates the values of the output_column from the output vertex
    properly encoded to ensure that we can reconstruct a list of the original values
    regardless of what characters they contain, whether they are empty or null, and
    regardless of their data type.

    Empty arrays are represented as '', null values are represented as '~', array
    entries are delimited using '|'.

    All occurrences of '^', '~', and '|' in the original string values are
    replaced with '^e' (escape), '^n' (null), and '^d' (delimiter), respectively.

    Undoing the encoding above, as well as the XML reference entity encoding performed
    by the XML PATH statement, is deferred to post-processing when the list is retrieved
    from the string representation produced by the subquery. See post_process_mssql_folds
    in graphql_compiler/post_processing/sql_post_processing.py for more information of
    post-processing the results.

    Joining from the preceding vertex to the correct output vertex
    is performed with the WHERE clause. This is contrasted with PostgreSQL subqueries,
    in which the join from penultimate vertex to output vertex is done within
    the FROM/JOIN clause of the aggregation subquery.

    Args:
        output_column: SQLAlchemy Column, value being aggregated with XML PATH
        predicate_expression: SQLAlchemy BinaryExpression, predicate used to filter

    Returns:
        A SQLAlchemy Selectable corresponding to the XML PATH subquery
    """
    delimiter = expression.literal_column("'|'")
    null = expression.literal_column("'~'")
    encoded_column = func.REPLACE(  # replace all occurrences of '^' in the original with '^e'
        output_column, expression.literal_column("'^'"), expression.literal_column("'^e'")
    )
    encoded_column = func.REPLACE(  # replace all occurrences of '~' in the original with '^n'
        encoded_column, null, expression.literal_column("'^n'")
    )
    encoded_column = func.REPLACE(  # replace all occurrences of '|' in the original with '^d'
        encoded_column, delimiter, expression.literal_column("'^d'")
    )

    # delimit elements in the array using '|'and mark nulls with `~`
    xml_column = delimiter + func.COALESCE(  # denote null values with '~'
        encoded_column, null
    )  # allow unambiguously distinguishing (nullable) array elements using scheme above

    # use constructor: you can't directly construct an XMLPathBinaryExpression from plain text
    xml_column = XMLPathBinaryExpression(xml_column.left, xml_column.right, xml_column.operator)

    return func.COALESCE(  # coalesce to represent empty arrays as ''
        select([xml_column])
        .where(predicate_expression)
        .suffix_with("FOR XML PATH ('')")
        .as_scalar(),
        expression.literal_column("''"),
    )


# 3-tuple describing the join information for each traversal in a fold.
#
# Contains DirectJoinDescriptor naming the columns used in the join predicate,
# the source/from table, and the destination/to table
SQLFoldTraversalDescriptor = namedtuple(
    "SQLFoldJoinInfo",
    (
        # DirectJoinDescriptor giving columns used to join from_table/to_table
        "join_descriptor",
        # SQLAlchemy table corresponding to corresponding to the outside vertex of the traversal,
        # appears on the left side of the join.
        "from_table",
        # SQLAlchemy table corresponding to corresponding to the inside vertex of the traversal,
        # appears on the right side of the join.
        "to_table",
    ),
)


class SQLFoldObject(object):
    """Object used to collect info for folds in order to ensure correct code emission."""

    # A SQLFoldObject consists of information related to the SELECT clause of the fold subquery,
    # the GROUP BY clause, the WHERE clause (if applying filters) and the FROM clause which contains
    # one JOIN per vertex traversed in the fold, including the traversal from the vertex outside
    # the fold to the folded vertex itself.
    #
    # The life cycle for the SQLFoldObject is:
    #   1. initializing it with the information for the outer vertex (the one outside the fold)
    #   2. at least one traversal
    #   3. visiting the output vertex to collect the output columns
    #   4. optionally adding a filter condition
    #   5. ending the fold by producing the resulting subquery
    #
    # This life cycle is completed via calls to __init__, visit_traversed_vertex,
    # visit_output_vertex, add_filter, and end_fold.
    #
    # The SELECT clause for the fold subquery contains OuterVertex.SOME_COLUMN, a unique
    # identifier (the primary key) for the OuterVertex determined by the edge descriptor
    # from the vertex immediately outside the fold to the folded vertex. This presently
    # only supports non-composite primary keys.
    #
    # SELECT will also contain an ARRAY_AGG for each column labeled for output inside the fold if
    # compiling to PostgreSQL. For compilation to MSSQL an XML PATH-based aggregation is performed.
    #
    # SELECT will also contain a COUNT(*) if _x_count is referred to by the query.
    #
    # The GROUP BY clause is produced during initialization.
    #
    # If a filter occurs on any vertex field inside the fold, a WHERE clause will also be produced.
    # TODO: implement filters for MSSQL
    #
    # The FROM and JOIN clauses are constructed during end_fold using info from the
    # visit_traversed_vertex function.
    #
    # The full subquery will look as follows for PostgreSQL:
    #
    # SELECT
    #   OuterVertex.SOME_COLUMN <- this value is the primary key
    #   ARRAY_AGG(OutputVertex.fold_output_column) AS fold_output
    # FROM OuterVertex
    # INNER JOIN ... <- INNER JOINs compiled during end_fold
    # ON ...
    #          ...
    # INNER JOIN OutputVertex <- INNER JOINs compiled during end_fold
    # ON ...
    # WHERE ... <- only for filters, which can be added with add_filter
    # GROUP BY OuterVertex.SOME_COLUMN
    #
    # and as follows for MSSQL:
    #
    # SELECT
    #   OuterVertex.SOME_COLUMN <- this value is the primary key
    #   COALESCE((SELECT ... FOR XML PATH(''), '~') AS fold_output
    # FROM OuterVertex
    # INNER JOIN ...
    # ON ...
    #          ...
    # INNER JOIN VertexPrecedingOutput
    # ON ...
    def __init__(self, dialect, outer_vertex_table, primary_key):
        """Create an SQLFoldObject with table, type, and join information supplied by the IR.

        Args:
            dialect: SQLAlchemy compiler object passed in from the schema, representing
                                the dialect we are compiling to.
            outer_vertex_table: SQLAlchemy table alias for vertex outside of fold.
            primary_key: PrimaryKeyConstraint, primary_key of the vertex immediately outside the
                         fold. Used to set the group by as well as join the fold subquery to the
                         rest of the query. Composite keys unsupported.
        """
        # table containing output columns
        # initially None because output table is unknown until call to visit_output_vertex
        self._output_vertex_alias = None

        # table for vertex immediately outside fold
        self._outer_vertex_alias = outer_vertex_table
        if len(primary_key.columns) > 1:
            raise NotImplementedError(
                u"Composite keys not supported. "
                u"A composite primary key {} was found for table {}. "
                u"SQL fold only supports non-composite primary "
                u"keys.".format(primary_key, outer_vertex_table.original)
            )

        # name of the field used in the primary key for the vertex outside the fold
        # current implementation does not support composite primary keys
        #
        # we must use the name of the column as opposed to the column itself because
        # primary key refers to the column from the original table, while we need the
        # identically named column from its alias
        self._outer_vertex_primary_key = list(primary_key.columns)[0].description

        # group by column for fold subquery
        self._group_by = [self._outer_vertex_alias.c[self._outer_vertex_primary_key]]

        # List of SQLFoldTraversalDescriptor namedtuples describing each traversal in the fold
        # starting with the join from the vertex immediately outside the fold to the folded vertex:
        self._traversal_descriptors = []
        self._outputs = []  # output columns for fold
        self._filters = []  # sqlalchemy Expressions to be used in the where clause

        # SQLAlchemy compiler object determining which dialect to target
        self._dialect = dialect
        self._ended = False  # indicates whether `end_fold` has been called on this object

    def __str__(self):
        """Produce string used to customize error messages."""
        if self._outer_vertex_alias is None:
            return u'SQLFoldObject("Invalid fold: no vertex preceding fold.")'
        elif self._output_vertex_alias is None:
            return (
                u'SQLFoldObject("Vertex outside fold: {}.' u'Output vertex for fold: None.")'
            ).format(self._outer_vertex_alias.original)
        else:
            return u'SQLFoldObject("Vertex outside fold: {}. Output vertex for fold: {}.")'.format(
                self._outer_vertex_alias.original, self._output_vertex_alias.original
            )

    @property
    def outputs(self):
        """Get the output columns for the fold subquery."""
        return self._outputs

    @property
    def group_by(self):
        """Get the columns to group by for the fold subquery."""
        return self._group_by

    @property
    def filters(self):
        """Get the list of SQL expressions to be used in the WHERE clause."""
        return self._filters

    @property
    def output_vertex_alias(self):
        """Get the SQLAlchemy table corresponding to the innermost vertex from the fold."""
        return self._output_vertex_alias

    @property
    def outer_vertex_alias(self):
        """Get the SQLAlchemy table corresponding to vertex immediately outside the fold."""
        return self._outer_vertex_alias

    def _set_outputs(self, outputs):
        """Set output columns for the fold object."""
        self._outputs = outputs

    def _set_group_by(self, group_by):
        """Set output columns for the fold object."""
        self._group_by = group_by

    def _construct_fold_joins(self):
        """Use the traversal descriptors to create the join clause for the tables in the fold."""
        # Start the join clause with the from_table of the first traversal descriptor,
        # which is the vertex immediately preceding the fold
        join_clause = self._traversal_descriptors[0].from_table
        if isinstance(self._dialect, MSDialect):
            # For MSSQL the logic of the final join predicate (from the vertex preceding the output
            # to the output vertex) occurs in the WHERE clause of the SELECT ... FOR XML PATH('')
            # so we don't iterate all n joins for MSSQL, just the first n-1.
            terminating_index = len(self._traversal_descriptors) - 1
        elif isinstance(self._dialect, PGDialect):
            terminating_index = len(self._traversal_descriptors)
        else:
            raise NotImplementedError(
                u"Fold only supported for MSSQL and "
                u"PostgreSQL, dialect was set to {}".format(self._dialect.name)
            )

        traversal_descriptors = self._traversal_descriptors[:terminating_index]
        # Starting at the first from_table, join traversed vertices in order until the output
        # vertex (PostgreSQL) is reached, or until the last vertex preceding the output
        # vertex (MSSQL) is reached.
        for travel_descriptor in traversal_descriptors:
            # joins from earlier in the chain of traversals are at the beginning of the list
            # b/c joins are appended in the order they are traversed
            from_table = travel_descriptor.from_table
            to_table = travel_descriptor.to_table
            join_descriptor = travel_descriptor.join_descriptor
            join_clause = sqlalchemy.join(
                join_clause,
                to_table,
                onclause=(
                    from_table.c[join_descriptor.from_column]
                    == to_table.c[join_descriptor.to_column]
                ),
            )

        return join_clause

    def _construct_fold_subquery(self, subquery_from_clause):
        """Combine all parts of the fold object to produce the complete fold subquery."""
        select_statement = sqlalchemy.select(self.outputs).select_from(subquery_from_clause)

        if self.filters:
            select_statement = select_statement.where(sqlalchemy.and_(*self.filters))

        if isinstance(self._dialect, MSDialect):
            # mssql doesn't rely on a group by
            return select_statement
        elif isinstance(self._dialect, PGDialect):
            return select_statement.group_by(*self.group_by)
        else:
            raise NotImplementedError(
                u"Fold only supported for MSSQL and "
                u"PostgreSQL, dialect was set to {}".format(self._dialect.name)
            )

    def _get_array_agg_column(self, intermediate_fold_output_name, fold_output_field):
        """Select an array_agg of the fold output field, labeled as requested."""
        return sqlalchemy.func.array_agg(self.output_vertex_alias.c[fold_output_field]).label(
            intermediate_fold_output_name
        )

    def _get_mssql_xml_path_column(
        self, intermediate_fold_output_name, fold_output_field, last_traversal
    ):
        """Select the MSSQL XML PATH aggregation of the fold output field, labeled as requested.

        The MSSQL equivalent of array aggregation is performed using an XML PATH subquery that has
        the basic structure outlined below.

        SELECT
            COALESCE('|' + ENCODE(OutputVertex.output_field), '~')
        FROM
            OutputVertex
        WHERE
            VertexPrecedingOutput.primary_key = OutputVertex.foreign_key
        FOR XML PATH ('')

        - ENCODE is shorthand for a function composition which replaces '~' (null),
        '|' (list delimiter), '^' (escape) with '^n', '^d', '^e', resp.

        - VertexPrecedingOutput is the vertex immediately preceding the output vertex in the
        chain of traversals, beginning at the vertex immediately outside the fold.
        VertexPrecedingOutput is the `from_table` of the last traversal descriptor tuple
        added to the fold's `traversal_descriptors` list.

        - The join predicate may have primary_key and foreign_key reversed depending on the
        direction of the edge connecting VertexPrecedingOutput to OutputVertex.

        Args:
            intermediate_fold_output_name: string label to give to the resulting XML PATH
                                            subquery built
            fold_output_field: string name of the column requested from the output vertex.
            last_traversal: SQLFoldTraversalDescriptor describing tables/WHERE predicate
                            used in subquery.

        Returns:
            Selectable for XML PATH aggregation subquery
        """
        # use join info tuple for most recent traversal to set WHERE clause for XML PATH subquery
        edge, from_alias, to_alias = last_traversal

        return _get_xml_path_clause(
            self.output_vertex_alias.c[fold_output_field],
            (from_alias.c[edge.from_column] == to_alias.c[edge.to_column]),
        ).label(intermediate_fold_output_name)

    def _get_fold_output_column_clause(self, fold_output_field):
        """Get the SQLAlchemy column expression corresponding to the fold output field."""
        if fold_output_field == COUNT_META_FIELD_NAME:
            return sqlalchemy.func.coalesce(
                sqlalchemy.func.count(), sqlalchemy.literal_column("0")
            ).label(FOLD_OUTPUT_FORMAT_STRING.format(COUNT_META_FIELD_NAME))
        else:
            # force column to have explicit label as opposed to anon_label
            intermediate_fold_output_name = FOLD_OUTPUT_FORMAT_STRING.format(fold_output_field)
            # add array aggregated output column to self._outputs
            # add aggregated output column to self._outputs
            if isinstance(self._dialect, MSDialect):
                # MSSQL uses XML PATH aggregation
                return self._get_mssql_xml_path_column(
                    intermediate_fold_output_name,
                    fold_output_field,
                    # output is last vertex traversed
                    self._traversal_descriptors[-1],
                )
            elif isinstance(self._dialect, PGDialect):
                # PostgreSQL uses ARRAY_AGG
                return self._get_array_agg_column(intermediate_fold_output_name, fold_output_field)
            else:
                raise NotImplementedError(
                    u"Fold only supported for MSSQL and PostgreSQL, "
                    u"dialect set to {}".format(self._dialect.name)
                )

        # We should have either triggered a not implemented error, or returned earlier
        raise AssertionError(
            u"Reached end of function without returning a value, "
            u"this code should be unreachable."
        )

    def _get_fold_outputs(self, fold_scope_location, all_folded_outputs):
        """Generate output columns for innermost fold scope and add them to active SQLFoldObject."""
        # find outputs for this fold in all_folded_outputs and add to self._outputs
        if fold_scope_location.fold_path in all_folded_outputs:
            for fold_output in all_folded_outputs[fold_scope_location.fold_path]:
                # distinguish folds with the same fold path but different query paths
                if (fold_output.base_location, fold_output.fold_path) == (
                    fold_scope_location.base_location,
                    fold_scope_location.fold_path,
                ):
                    # get sqlalchemy column for fold_output
                    column_clause = self._get_fold_output_column_clause(fold_output.field)
                    # append resulting column to outputs
                    self._outputs.append(column_clause)

        # use to join unique identifier for the fold's outer vertex to the final table
        self._outputs.append(self.outer_vertex_alias.c[self._outer_vertex_primary_key])

        # sort to make select order deterministic
        return sorted(self._outputs, key=lambda column: column.name, reverse=True)

    def visit_output_vertex(self, output_alias, fold_scope_location, all_folded_outputs):
        """Update output columns when visiting the vertex containing output directives."""
        if self._ended:
            raise AssertionError(
                u"Cannot visit output vertices after end_fold has been called. "
                u"Invalid state encountered during fold {}".format(self)
            )
        if self._output_vertex_alias is not None:
            raise AssertionError(
                u"Cannot visit multiple output vertices in one fold. "
                u"Invalid state encountered during fold {}".format(self)
            )
        self._output_vertex_alias = output_alias
        self._outputs = self._get_fold_outputs(fold_scope_location, all_folded_outputs)

    def visit_traversed_vertex(self, join_descriptor, from_table, to_table):
        """Add a new traversal descriptor for every vertex traversed in the fold."""
        if self._ended:
            raise AssertionError(
                u"Cannot visit traversed vertices after end_fold has been called."
                u"Invalid state encountered during fold {}".format(self)
            )
        self._traversal_descriptors.append(
            SQLFoldTraversalDescriptor(join_descriptor, from_table, to_table)
        )

    def add_filter(self, predicate, aliases):
        """Add a new filter to the SQLFoldObject."""
        if self._ended:
            raise AssertionError(
                u"Cannot add a filter after end_fold has been called. Invalid "
                u"state encountered during fold {}".format(self)
            )
        if isinstance(self._dialect, MSDialect):
            raise NotImplementedError(u"Filtering on fields is not implemented for MSSQL yet.")
        # Filters are applied to output vertices, thus current_alias=self.output_vertex_alias.
        sql_expression = predicate.to_sql(self._dialect, aliases, self.output_vertex_alias)
        self._filters.append(sql_expression)

    def end_fold(self, alias_generator, from_clause, outer_from_table):
        """Produce the final subquery and join it onto the rest of the query."""
        if self._ended:
            raise AssertionError(
                u"Cannot call end_fold more than once. "
                u"Invalid state encountered during fold {}".format(self)
            )
        if self._output_vertex_alias is None:
            raise AssertionError(
                u"No output vertex visited. "
                u"Invalid state encountered during fold {}".format(self)
            )
        if len(self._traversal_descriptors) == 0:
            raise AssertionError(
                u"No traversed vertices visited. "
                u"Invalid state encountered during fold {}".format(self)
            )

        # for now we only handle folds containing one traversal (i.e. join)
        if len(self._traversal_descriptors) > 1:
            raise NotImplementedError(u"Folds containing multiple traversals are not implemented.")

        # join together all vertices traversed
        subquery_from_clause = self._construct_fold_joins()

        # produce full subquery
        fold_subquery = self._construct_fold_subquery(subquery_from_clause).alias(
            alias_generator.generate_subquery()
        )

        # join the subquery onto the rest of the query
        joined_from_clause = sqlalchemy.join(
            from_clause,
            fold_subquery,
            onclause=(
                outer_from_table.c[self._outer_vertex_primary_key]
                == fold_subquery.c[
                    self._outer_vertex_primary_key
                ]  # only support a single primary key field, no composite keys
            ),
            isouter=False,
        )
        self._ended = True  # prevent any more functions being called on this fold
        return fold_subquery, joined_from_clause, outer_from_table


class UniqueAliasGenerator(object):
    """Mutable class used to generate unique aliases for subqueries."""

    def __init__(self):
        """Create unique subquery aliases by tracking counter."""
        self._fold_count = 1

    def generate_subquery(self):
        """Generate a new subquery alias and increment the counter."""
        alias = FOLD_SUBQUERY_FORMAT_STRING.format(self._fold_count)
        self._fold_count += 1
        return alias


class CompilationState(object):
    """Mutable class used to keep track of state while emitting a sql query."""

    def __init__(self, sql_schema_info, ir):
        """Initialize a CompilationState, setting the current location at the root of the query."""
        # Immutable metadata
        self._sql_schema_info = sql_schema_info
        self._ir = ir
        self._used_columns = _find_columns_used_outside_folds(sql_schema_info, ir)
        # mapping fold paths to FoldScopeLocations with field information
        self._all_folded_fields = _find_folded_fields(ir)

        # Current query location state. Only mutable by calling _relocate.
        self._current_location = None  # the current location in the query. None means global.
        self._current_alias = None  # a sqlalchemy table Alias at the current location

        # Dict mapping (some_location.query_path, fold_scope_location.fold_path) tuples to
        # corresponding table _Aliases. some_location is either self._current_location
        # or the base location of an open FoldScopeLocation.
        # Note: for tables with an _x_count column, that column will always
        # be named "fold_output__x_count".
        self._aliases = {}
        self._relocate(ir.query_metadata_table.root_location)
        self._came_from = {}  # mapping aliases to the column used to join into them.

        # The query being constructed as the IR is processed
        self._from_clause = self._current_alias  # the main sqlalchemy Selectable
        self._outputs = []  # sqlalchemy Columns labelled correctly for output
        self._filters = []  # sqlalchemy Expressions to be used in the where clause

        self._current_fold = None  # SQLFoldObject to collect fold info and guide output query
        self._fold_vertex_location = None  # location in the IR tree where the fold starts

        self._alias_generator = UniqueAliasGenerator()  # generates aliases for the fold subqueries

        # indicates the sqlalchemy compiler determining the query's dialect
        self._dialect = self.sql_schema_info.dialect

    def _relocate(self, new_location):
        """Move to a different location in the query, updating the _alias."""
        self._current_location = new_location
        if (self._current_location.query_path, None) in self._aliases:
            self._current_alias = self._aliases[(self._current_location.query_path, None)]
        else:
            self._current_alias = self._sql_schema_info.vertex_name_to_table[
                self._current_classname
            ].alias()

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
            self._filters.append(
                sqlalchemy.or_(
                    self._came_from[self._current_alias].isnot(None),
                    self._came_from[parent_alias].is_(None),
                )
            )

        # Join to where we came from
        self._from_clause = self._from_clause.join(
            self._current_alias,
            onclause=(parent_alias.c[from_column] == self._current_alias.c[to_column]),
            isouter=self._is_in_optional_scope(),
        )

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
        if self._current_fold is not None:
            raise NotImplementedError("Traversals inside a fold are not implemented yet.")
        # Follow the edge
        previous_alias = self._current_alias
        edge = self._sql_schema_info.join_descriptors[self._current_classname][vertex_field]
        self._relocate(self._current_location.navigate_to_subpath(vertex_field))
        self._join_to_parent_location(previous_alias, edge.from_column, edge.to_column, optional)

    def recurse(self, vertex_field, depth):
        """Execute a Recurse Block."""
        if self._current_fold is not None:
            raise AssertionError("Recurse inside a fold is not allowed.")
        previous_alias = self._current_alias
        edge = self._sql_schema_info.join_descriptors[self._current_classname][vertex_field]
        if not self._current_alias.primary_key:
            raise AssertionError(
                u"The table for vertex {} has no primary key specified. This "
                u"information is required to emit a @recurse directive.".format(
                    self._current_classname
                )
            )
        if len(self._current_alias.primary_key) > 1:
            raise NotImplementedError(
                u"The table for vertex {} has a composite primary key {}. "
                u"The SQL backend does not support @recurse on tables with "
                u"composite primary keys.".format(
                    self._current_classname, self._current_alias.primary_key
                )
            )
        primary_key = self._current_alias.primary_key[0].name
        self._relocate(self._current_location.navigate_to_subpath(vertex_field))

        # Sanitize literal columns to be used in the query
        if not isinstance(depth, int):
            raise AssertionError(
                u"Depth must be a number. Received {} {}".format(type(depth), depth)
            )
        literal_depth = sqlalchemy.literal_column(str(depth))
        literal_0 = sqlalchemy.literal_column("0")
        literal_1 = sqlalchemy.literal_column("1")

        # Find which columns should be selected
        used_columns = sorted(self._used_columns[self._current_location.query_path])

        # The base of the recursive CTE selects all needed columns and sets the depth to 0
        base = sqlalchemy.select(
            [self._current_alias.c[col] for col in used_columns]
            + [
                self._current_alias.c[primary_key].label(CTE_KEY_NAME),
                literal_0.label(CTE_DEPTH_NAME),
            ]
        ).cte(recursive=True)

        # The recursive step selects all needed columns, increments the depth, and joins to the base
        step = self._current_alias.alias()
        self._current_alias = base.union_all(
            sqlalchemy.select(
                [step.c[col] for col in used_columns]
                + [
                    base.c[CTE_KEY_NAME].label(CTE_KEY_NAME),
                    (base.c[CTE_DEPTH_NAME] + literal_1).label(CTE_DEPTH_NAME),
                ]
            )
            .select_from(
                base.join(step, onclause=base.c[edge.from_column] == step.c[edge.to_column])
            )
            .where(base.c[CTE_DEPTH_NAME] < literal_depth)
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
            raise AssertionError(u"CompilationState is already in global scope.")
        self._current_location = None

    def filter(self, predicate):
        """Execute a Filter Block."""
        # If there is an active fold, add the filter to the current fold. Note that this is only for
        # regular fields i.e. non-_x_count fields. Filtering on _x_count will use the COUNT(*)
        # output from the folded subquery and apply the filter in the global WHERE clause.
        if self._current_fold is not None:
            if _find_tagged_parameters(predicate):
                raise NotImplementedError(
                    u"Filtering with a tagged parameter in a fold scope is not implemented yet."
                )
            self._current_fold.add_filter(predicate, self._aliases)

        # Otherwise, add the filter to the compilation state. Note that this is for filters outside
        # a fold scope and _x_count filters within a fold scope.
        else:
            sql_expression = predicate.to_sql(self._dialect, self._aliases, self._current_alias)
            if self._is_in_optional_scope():
                sql_expression = sqlalchemy.or_(
                    sql_expression, self._came_from[self._current_alias].is_(None)
                )
            self._filters.append(sql_expression)

    def fold(self, fold_scope_location):
        """Begin execution of a Fold Block."""
        # This method traverses the first vertex in the fold, and if applicable produces the
        # output and group by clauses.
        if self._current_fold is not None:
            raise AssertionError(
                u"Fold block {} entered while inside another "
                u"fold block at current location {}.".format(
                    fold_scope_location, self._current_location_info
                )
            )
        # begin the fold
        # 1. get fold metadata
        # location of vertex that is folded on
        self._fold_vertex_location = fold_scope_location
        outer_alias = self._current_alias.alias()
        outer_vertex_primary_key = self._sql_schema_info.vertex_name_to_table[
            self._current_classname
        ].primary_key
        # 2. get information on the folded vertex and its edge to the outer vertex
        # basic info about the folded vertex
        fold_vertex_alias = self._sql_schema_info.vertex_name_to_table[
            self._ir.query_metadata_table.get_location_info(fold_scope_location).type.name
        ].alias()

        # collect edge information to join the fold subquery to the main selectable
        edge_direction, edge_name = fold_scope_location.fold_path[0]
        full_edge_name = "{}_{}".format(edge_direction, edge_name)
        # only works if fold scope location is the immediate child of self._current_classname
        join_descriptor = self._sql_schema_info.join_descriptors[self._current_classname][
            full_edge_name
        ]

        # 3. initialize fold object
        self._current_fold = SQLFoldObject(self.dialect, outer_alias, outer_vertex_primary_key)

        # 4. add join information for this traversal to the fold object
        self._current_fold.visit_traversed_vertex(join_descriptor, outer_alias, fold_vertex_alias)

        # 5. add output columns to fold object
        self._current_fold.visit_output_vertex(
            fold_vertex_alias, fold_scope_location, self._all_folded_fields
        )

    def unfold(self):
        """Complete the execution of a Fold Block."""
        fold_subquery, from_cls, outer_vertex = self._current_fold.end_fold(
            self._alias_generator, self._from_clause, self._current_alias
        )

        # generate a key for self._aliases that maps to the fold subquery's alias
        subquery_alias_key = (
            self._fold_vertex_location.base_location.query_path,
            self._fold_vertex_location.fold_path,
        )

        # Replace the table first placed in the dict during the MarkLocation
        # following the start of the fold scope. It needs to be replaced because while
        # inside the fold scope, columns accessed at the fold scope location refer
        # to the folded vertex table, while after the Unfold, those column accesses refer to
        # the subquery constructed for the fold.
        self._aliases[subquery_alias_key] = fold_subquery
        self._from_clause = from_cls

        # Ensure references to the outer vertex table after the Unfold refer to a totally new
        # copy of the outer vertex table. Otherwise references would select columns from the
        # copy of that table found inside the fold subquery.
        self._aliases[(self._current_location.at_vertex().query_path, None)] = outer_vertex

        # clear the fold from the compilation state
        self._current_fold = None
        self._fold_vertex_location = None
        self._current_alias = outer_vertex

    def mark_location(self):
        """Execute a MarkLocation Block."""
        # If the current location is the beginning of a fold, the current alias
        # will eventually be replaced by the resulting fold subquery during Unfold.
        self._aliases[
            (
                self._fold_vertex_location.base_location.query_path,
                self._fold_vertex_location.fold_path,
            )
            if self._current_fold is not None
            else (self._current_location.query_path, None)
        ] = self._current_alias

    def construct_result(self, output_name, field):
        """Execute a ConstructResult Block."""
        self._outputs.append(
            field.to_sql(self.dialect, self._aliases, self._current_alias).label(output_name)
        )

    def get_query(self):
        """After all IR Blocks are processed, return the resulting sqlalchemy query."""
        return (
            sqlalchemy.select(self._outputs)
            .select_from(self._from_clause)
            .where(sqlalchemy.and_(*self._filters))
        )

    @property
    def sql_schema_info(self):
        """Get the SQLALchemySchemaInfo for the current query."""
        return self._sql_schema_info

    @property
    def dialect(self):
        """Get the SQLAlchemyCompiler determining the dialect the query compiles to."""
        return self._dialect


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
            state.traverse(u"{}_{}".format(block.direction, block.edge_name), block.optional)
        elif isinstance(block, blocks.Recurse):
            state.recurse(u"{}_{}".format(block.direction, block.edge_name), block.depth)
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
            raise NotImplementedError(u"Unsupported block {}.".format(block))

    return state.get_query()
