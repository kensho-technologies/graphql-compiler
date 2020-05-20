# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
from dataclasses import dataclass
from typing import Dict, Iterator, List, NamedTuple, Optional, Set, Tuple, Union

import six
import sqlalchemy
from sqlalchemy import select
from sqlalchemy.dialects.mssql.base import MSDialect
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression
from sqlalchemy.sql.compiler import _CompileLabel
from sqlalchemy.sql.elements import Label
from sqlalchemy.sql.expression import Alias, BinaryExpression
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.selectable import FromClause, Join, Select

from . import blocks
from ..global_utils import VertexPath
from ..schema import COUNT_META_FIELD_NAME
from ..schema.schema_info import DirectJoinDescriptor, SQLAlchemySchemaInfo
from .compiler_entities import BasicBlock
from .compiler_frontend import IrAndMetadata
from .expressions import ContextField, Expression
from .helpers import (
    BaseLocation,
    FoldPath,
    FoldScopeLocation,
    Location,
    QueryPath,
    get_edge_direction_and_name,
)
from .metadata import LocationInfo


# Some reserved column names used in emitted SQL queries
CTE_DEPTH_NAME = "__cte_depth"
CTE_KEY_NAME = "__cte_key"

# Formatting strings for intermediate queries/outputs from folds
FOLD_OUTPUT_FORMAT_STRING = "fold_output_{}"
FOLD_SUBQUERY_FORMAT_STRING = "folded_subquery_{}"


def _traverse_and_validate_blocks(ir: IrAndMetadata) -> Iterator[BasicBlock]:
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
                raise AssertionError(f"Found block {block} before QueryRoot: {ir.ir_blocks}.")

        if isinstance(block, blocks.GlobalOperationsStart):
            if found_global_operations_block:
                raise AssertionError(f"Found duplicate GlobalOperationsStart: {ir.ir_blocks}.")
            found_global_operations_block = True
        else:
            if found_global_operations_block:
                if not isinstance(block, globally_allowed_blocks):
                    raise AssertionError(
                        f"Only {globally_allowed_blocks} are allowed after GlobalOperationsBlock. "
                        f"Found {block} in {ir.ir_blocks}."
                    )
            else:
                if isinstance(block, global_only_blocks):
                    raise AssertionError(
                        f"Block {block} is only allowed after GlobalOperationsBlock: "
                        f"{ir.ir_blocks}."
                    )
        yield block


def _find_columns_used_outside_folds(
    sql_schema_info: SQLAlchemySchemaInfo, ir: IrAndMetadata
) -> Dict[VertexPath, Set[str]]:
    """For each query path outside of a fold output, find which columns are used."""
    used_columns: Dict[VertexPath, Set[str]] = {}

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
            vertex_field_name = f"{edge_direction}_{edge_name}"
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

    # Columns used in the base case of CTE recursions should be made available from parent scope
    for location, _ in ir.query_metadata_table.registered_locations:
        if isinstance(location, FoldScopeLocation):
            continue
        for recurse_info in ir.query_metadata_table.get_recurse_infos(location):
            traversal = f"{recurse_info.edge_direction}_{recurse_info.edge_name}"
            used_columns[location.query_path] = used_columns.get(location.query_path, set()).union(
                used_columns[location.query_path + (traversal,)]
            )
            used_columns[location.query_path].add(edge.from_column)

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


def _find_folded_fields(ir: IrAndMetadata) -> Dict[FoldPath, Set[FoldScopeLocation]]:
    """For each fold path, find folded fields (outputs and metafields used in filters).

    Args:
        ir: internal representation and metadata of a query for which to find the folded fields.

    Returns:
        Dictionary mapping a FoldPath to  a set of FoldScopeLocations with output field information.
    """
    folded_fields: Dict[FoldPath, Set[FoldScopeLocation]] = {}
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


class SQLFoldTraversalDescriptor(NamedTuple):
    """Describes the join information for traversals inside a fold."""

    # DirectJoinDescriptor giving columns used to join from_table/to_table.
    join_descriptor: DirectJoinDescriptor

    # SQLAlchemy table corresponding to the outside vertex of the traversal,
    # appears on the left side of the join.
    from_table: Alias

    # SQLAlchemy table corresponding to the inside vertex of the traversal,
    # appears on the right side of the join.
    to_table: Alias


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


def _construct_traversal_joins(traversals: List[SQLFoldTraversalDescriptor]) -> Join:
    """Perform JOINs corresponding to the described traversals.

    Args:
        traversals: list of at least 1 SQLFoldTraversalDescriptors in the order they were traversed,
                    from earliest to latest traversal. The to_table of a traversal should be the
                    from_table of the next.

    Returns:
        A Join statement describing the traversals.
    """
    if len(traversals) == 0:
        raise AssertionError(
            "Must pass at least 1 traversal in order to construct traversal JOINs. Received an "
            "empty traversals list."
        )
    join_clause = traversals[0].from_table
    previous_to_table: Optional[Alias] = None
    for traversal_descriptor in traversals:
        # JOINs from earlier in the chain of traversals are at the beginning of the list
        # because JOINs are appended in the order they are traversed.
        from_table = traversal_descriptor.from_table
        if previous_to_table is not None and not previous_to_table.compare(from_table):
            raise AssertionError(
                "Received invalid traversals. The to_table of a SQLFoldTraversalDescriptor must "
                "match the from_table of the subsequent SQLFoldTraversalDescriptor. Received "
                f"to_table {previous_to_table.description} followed by from_table "
                f"{from_table.description}."
            )
        to_table = traversal_descriptor.to_table
        join_descriptor = traversal_descriptor.join_descriptor
        join_clause = sqlalchemy.join(
            join_clause,
            to_table,
            onclause=(
                from_table.c[join_descriptor.from_column] == to_table.c[join_descriptor.to_column]
            ),
        )
        previous_to_table = to_table
    return join_clause


def _get_array_agg_column(output_column: Column, intermediate_fold_output_name: str,) -> Label:
    """Select an array_agg of the fold output field, labeled as requested."""
    return sqlalchemy.func.array_agg(output_column).label(intermediate_fold_output_name)


def _get_mssql_xml_path_column(
    output_column: Column,
    intermediate_fold_output_name: str,
    traversals: List[SQLFoldTraversalDescriptor],
) -> Label:
    """Select the MSSQL XML PATH aggregation of the fold output field, labeled as requested.

    The MSSQL equivalent of array aggregation is performed using an XML PATH subquery that has
    the basic structure outlined below.

    SELECT
        COALESCE('|' + ENCODE(OutputVertex.output_field), '~')
    FROM
        OutputVertex
    JOIN ... ON ...
    WHERE
        FirstTraversedVertex.primary_key = SecondTraversedVertex.foreign_key
    FOR XML PATH ('')

    - ENCODE is shorthand for a function composition which replaces '~' (null),
    '|' (list delimiter), '^' (escape) with '^n', '^d', '^e', respectively. The encoding
    ensures that a list of the original values can be reconstructed regardless of what characters
    they contain, whether they are empty or null, and regardless of their data type.

    - The first traversal is performed in the WHERE clause, while any other traversals are
    performed in the FROM/JOIN clause of the XML PATH query. Note that JOINs are optional and
    correspond to additional traversals inside the fold scope. This is contrasted with PostgreSQL
    subqueries, in which all traversals are performed within the FROM/JOIN clause of the aggregation
    subquery.

    - The WHERE predicate may have primary_key and foreign_key reversed depending on the
    direction of the edge of the first traversal.

    - Undoing the encoding above, as well as the XML reference entity encoding performed
    by the XML PATH statement, is deferred to post-processing when the list is retrieved
    from the string representation produced by the subquery. See post_process_mssql_folds
    in graphql_compiler/post_processing/sql_post_processing.py for more information on
    post-processing the results.

    Args:
        output_column: SQLAlchemy Column to be aggregated with XML PATH.
        intermediate_fold_output_name: string label to give to the resulting aggregated output.
        traversals: traversals performed within the fold. The earliest (first in the list) traversal
                    is performed as a part of the WHERE clause. All other traversals will be JOINed
                    to the FROM clause.

    Returns:
        Selectable for XML PATH aggregation subquery.
    """
    delimiter = expression.literal_column("'|'")
    null = expression.literal_column("'~'")
    encoded_column = func.REPLACE(  # Replace all occurrences of '^' in the original with '^e'.
        output_column, expression.literal_column("'^'"), expression.literal_column("'^e'")
    )
    encoded_column = func.REPLACE(  # Replace all occurrences of '~' in the original with '^n'.
        encoded_column, null, expression.literal_column("'^n'")
    )
    encoded_column = func.REPLACE(  # Replace all occurrences of '|' in the original with '^d'.
        encoded_column, delimiter, expression.literal_column("'^d'")
    )

    # Delimit elements in the array using '|'and replace nulls in the original with `~`.
    xml_column = delimiter + func.COALESCE(encoded_column, null)

    # Use constructor because it is not possible to directly construct an XMLPathBinaryExpression
    # from plain text.
    xml_column = XMLPathBinaryExpression(xml_column.left, xml_column.right, xml_column.operator)

    select_statement = select([xml_column])

    # Construct traversals. The earliest traversal (the first in the list of traversals) is
    # performed as a part of the WHERE statement.
    edge, from_alias, to_alias = traversals[0]
    predicate_expression = from_alias.c[edge.from_column] == to_alias.c[edge.to_column]

    # Any other traversals are performed as JOINs to the FROM statement.
    traversals = traversals[1:]
    if traversals:
        join_clause = _construct_traversal_joins(traversals)
        select_statement = select_statement.select_from(join_clause)

    # Coalesce to represent empty arrays as '' and return the XML PATH aggregated data with label.
    return func.COALESCE(
        select_statement.where(predicate_expression).suffix_with("FOR XML PATH ('')").as_scalar(),
        expression.literal_column("''"),
    ).label(intermediate_fold_output_name)


class FoldSubqueryBuilder(object):
    """Builder that emits a subquery for a fold scope."""

    # The life cycle for the FoldSubqueryBuilder is:
    #   1. initialize at the vertex preceding the fold
    #   2. visit all locations inside the fold scope. Must visit at least one location with outputs.
    #   3. optionally add fold scope filters
    #   4. end the fold, producing the resulting subquery
    #
    # This life cycle is completed via calls to __init__, visit_vertex, add_filter, and end_fold.
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
    # visit_vertex function.
    #
    # The full subquery will look as follows for PostgreSQL:
    #
    # SELECT
    #   OuterVertex.SOME_COLUMN <- this value is the primary key
    #   ARRAY_AGG(OutputVertex.fold_output_column) AS fold_output
    # FROM OuterVertex
    # JOIN ... <- INNER JOINs compiled during end_fold
    # ON ...
    #          ...
    # JOIN OutputVertex <- INNER JOINs compiled during end_fold
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
    # JOIN ...
    # ON ...
    #          ...
    # JOIN VertexPrecedingOutput
    # ON ...
    def __init__(self, dialect: DefaultDialect, outer_vertex_table: Alias, primary_key_name: str):
        """Create a FoldSubqueryBuilder with table, type, and join information supplied by the IR.

        Args:
            dialect: dialect to which the query will be compiled.
            outer_vertex_table: SQLAlchemy table alias for vertex outside of fold.
            primary_key_name: name of the primary key of the vertex immediately outside the
                              fold. Used to set the group by as well as join the fold subquery
                              to the rest of the query.
        """
        # Table and FoldScopeLocation containing output columns are initialized to None because
        # the output table is unknown until one is found during visit_vertex.
        self._output_vertex_alias: Optional[Alias] = None
        self._output_vertex_location: Optional[FoldScopeLocation] = None

        # Table for vertex immediately outside fold.
        self._outer_vertex_alias: Alias = outer_vertex_table
        self._outer_vertex_primary_key: str = primary_key_name

        # List of SQLFoldTraversalDescriptors describing each traversal in the fold
        # starting with the join from the vertex immediately outside the fold to the folded vertex.
        self._traversal_descriptors: List[SQLFoldTraversalDescriptor] = []
        self._outputs: List[Label] = []  # Output columns for folded subquery.
        self._filters: List[
            BinaryExpression
        ] = []  # SQLAlchemy Expressions to be used in the WHERE clause.

        # SQLAlchemy compiler object determining which dialect to target.
        self._dialect: DefaultDialect = dialect

        # Whether this fold has been ended by calling the end_fold function.
        self._ended: bool = False

    def __str__(self):
        """Produce string used to customize error messages."""
        if self._outer_vertex_alias is None:
            return 'FoldSubqueryBuilder("Invalid fold: no vertex preceding fold.")'
        elif self._output_vertex_alias is None:
            return (
                f'FoldSubqueryBuilder("Vertex outside fold: {self._outer_vertex_alias.original}. '
                'Output vertex for fold: None.")'
            )
        else:
            return (
                f'FoldSubqueryBuilder("Vertex outside fold: {self._outer_vertex_alias.original}. '
                f'Output vertex for fold: {self._output_vertex_alias.original}.")'
            )

    def _construct_fold_joins(self) -> Join:
        """Use the traversal descriptors to create the join clause for the tables in the fold."""
        if isinstance(self._dialect, MSDialect):
            # For MSSQL, traversals are performed as a part of the SELECT ... FOR XML PATH('')
            # statement, which is contained in self._outputs. The JOIN clause is simply the
            # from_table of the first traversal descriptor, which is the vertex immediately
            # preceding the fold.
            return self._traversal_descriptors[0].from_table
        elif isinstance(self._dialect, PGDialect):
            return _construct_traversal_joins(self._traversal_descriptors)
        else:
            raise NotImplementedError(
                "Fold only supported for MSSQL and PostgreSQL, "
                f"dialect was set to {self._dialect.name}."
            )

    def _construct_fold_subquery(self, subquery_from_clause: Join) -> Select:
        """Combine all parts of the fold object to produce the complete fold subquery."""
        select_statement = (
            sqlalchemy.select(self._outputs)
            .select_from(subquery_from_clause)
            .where(sqlalchemy.and_(*self._filters))
        )

        if isinstance(self._dialect, MSDialect):
            # mssql doesn't rely on a group by
            return select_statement
        elif isinstance(self._dialect, PGDialect):
            return select_statement.group_by(
                self._outer_vertex_alias.c[self._outer_vertex_primary_key]
            )
        else:
            raise NotImplementedError(
                "Fold only supported for MSSQL and "
                f"PostgreSQL, dialect was set to {self._dialect.name}."
            )

    def _get_fold_output_column_clause(self, fold_output_field: str) -> Label:
        """Get the SQLAlchemy column expression corresponding to the fold output field."""
        if fold_output_field == COUNT_META_FIELD_NAME:
            return sqlalchemy.func.coalesce(
                sqlalchemy.func.count(), sqlalchemy.literal_column("0")
            ).label(FOLD_OUTPUT_FORMAT_STRING.format(COUNT_META_FIELD_NAME))
        else:
            if self._output_vertex_alias is None:
                raise AssertionError(
                    "Attempted to get fold output column before the output vertex was visited "
                    f"(_output_vertex_alias is None) during fold {self}."
                )

            # Get the output column.
            output_column = self._output_vertex_alias.c[fold_output_field]

            # Create intermediate name for the output_column.
            intermediate_fold_output_name = FOLD_OUTPUT_FORMAT_STRING.format(fold_output_field)

            # Perform aggregation appropriate for the _dialect and add aggregated output column
            # to self._outputs.
            if isinstance(self._dialect, MSDialect):
                # MSSQL uses XML PATH aggregation.
                return _get_mssql_xml_path_column(
                    output_column, intermediate_fold_output_name, self._traversal_descriptors,
                )
            elif isinstance(self._dialect, PGDialect):
                # PostgreSQL uses ARRAY_AGG.
                return _get_array_agg_column(output_column, intermediate_fold_output_name)
            else:
                raise NotImplementedError(
                    "Fold only supported for MSSQL and PostgreSQL, "
                    f"dialect set to {self._dialect.name}."
                )

        raise AssertionError(
            "Reached end of function _get_fold_output_column_clause without returning a value "
            f"during fold {self}. This code should be unreachable."
        )

    def _get_fold_outputs(
        self,
        fold_scope_location: FoldScopeLocation,
        all_folded_fields: Dict[FoldPath, Set[FoldScopeLocation]],
    ) -> List[Label]:
        """Generate output columns for innermost fold scope and add them to _outputs."""
        # Find outputs for this fold in all_folded_fields and add to self._outputs.
        if fold_scope_location.fold_path in all_folded_fields:
            for fold_output in all_folded_fields[fold_scope_location.fold_path]:
                # Distinguish folds with the same fold path but different query paths.
                if (fold_output.base_location, fold_output.fold_path) == (
                    fold_scope_location.base_location,
                    fold_scope_location.fold_path,
                ):
                    if fold_output.field is None:
                        raise AssertionError(
                            f"Received invalid fold_output {fold_output}. FoldScopeLocations in "
                            f"all_folded_fields must have their fields set."
                        )
                    if fold_output.field == COUNT_META_FIELD_NAME and isinstance(
                        self._dialect, MSDialect
                    ):
                        raise NotImplementedError(
                            f"_x_count is not implemented for MSSQL. Received _x_count "
                            f"fold_output {fold_output}."
                        )
                    # Get SQLAlchemy column for fold_output.
                    column_clause = self._get_fold_output_column_clause(fold_output.field)
                    # Append resulting column to outputs.
                    self._outputs.append(column_clause)

        # Use to join unique identifier for the fold's outer vertex to the final table.
        self._outputs.append(self._outer_vertex_alias.c[self._outer_vertex_primary_key])

        # Sort to make select order deterministic.
        return sorted(self._outputs, key=lambda column: column.name, reverse=True)

    # TODO(bojanserafimov): This function communicates both a traversal to a new node and
    #                       outputting information at the new node. It could be split into two
    #                       functions that are easier to spec:
    #                       1. traverse(self, join_descriptor)
    #                       2. add_output(self, column_name)
    #                       This way there is no need to define what is considered a folded
    #                       field. It is up to the caller to expose all they will want to use.
    def visit_vertex(
        self,
        join_descriptor: DirectJoinDescriptor,
        from_table: Alias,
        to_table: Alias,
        current_fold_scope_location: FoldScopeLocation,
        all_folded_fields: Dict[FoldPath, Set[FoldScopeLocation]],
    ) -> None:
        """Add a new SQLFoldTraversalDescriptor and add outputs, if visiting an output vertex."""
        if self._ended:
            raise AssertionError(
                "Cannot visit traversed vertices after end_fold has been called."
                f"Invalid state encountered during fold {self}."
            )

        self._traversal_descriptors.append(
            SQLFoldTraversalDescriptor(join_descriptor, from_table, to_table)
        )

        # Collect outputs, if there are any at the current FoldScopeLocation.
        if current_fold_scope_location.fold_path in all_folded_fields:
            # Ensure that no other outputs have been found for this fold since all outputs must
            # come from the same FoldScopeLocation.
            if self._output_vertex_alias is not None:
                raise AssertionError(
                    "Cannot visit multiple output vertices in one fold. "
                    f"Invalid state encountered during fold {self}."
                )
            self._output_vertex_alias = to_table
            self._output_vertex_location = current_fold_scope_location
            self._outputs = self._get_fold_outputs(current_fold_scope_location, all_folded_fields)

    def add_filter(
        self, predicate: Expression, aliases: Dict[Tuple[QueryPath, Optional[FoldPath]], Alias]
    ) -> None:
        """Add a new filter to the FoldSubqueryBuilder."""
        if self._ended:
            raise AssertionError(
                "Cannot add a filter after end_fold has been called. Invalid "
                f"state encountered during fold {self}."
            )
        if isinstance(self._dialect, MSDialect):
            raise NotImplementedError(
                "Filtering on fields inside a fold is not implemented for MSSQL yet."
            )
        # Filters are applied to output vertices, thus current_alias=self.output_vertex_alias.
        sql_expression = predicate.to_sql(self._dialect, aliases, self._output_vertex_alias)
        self._filters.append(sql_expression)

    def end_fold(self) -> Tuple[Select, FoldScopeLocation]:
        """Return the fold subquery and the location its outputs come from."""
        if self._ended:
            raise AssertionError(
                "Cannot call end_fold more than once. "
                f"Invalid state encountered during fold {self}."
            )
        if self._output_vertex_alias is None or self._output_vertex_location is None:
            raise AssertionError(
                f"No output vertex visited. Invalid state encountered during fold {self}."
            )
        if len(self._traversal_descriptors) == 0:
            raise AssertionError(
                f"No traversed vertices visited. Invalid state encountered during fold {self}."
            )

        # For now, folds with multiple outputs are not implemented in MSSQL. Each output comes
        # from its own selectable within the XML PATH statement so it is not guaranteed result order
        # would be preserved across multiple outputs from the same FoldScopeLocation.
        # Note: _outputs includes 1 output used for joining the folded subquery to the main
        # selectable and at least 1 other folded output. Since MSSQL only supports 1 output of a
        # field (_x_counts are not implemented), ensure that len(self.outputs) == 2.
        if len(self._outputs) != 2 and isinstance(self._dialect, MSDialect):
            raise NotImplementedError(
                "Folds containing multiple outputs are not implemented in MSSQL."
            )

        # End the fold, preventing any more functions from being called on this fold.
        self._ended = True

        # Produce the subquery.
        subquery_from_clause = self._construct_fold_joins()
        fold_subquery = self._construct_fold_subquery(subquery_from_clause)
        return fold_subquery, self._output_vertex_location


class UniqueAliasGenerator(object):
    """Mutable class used to generate unique aliases for subqueries."""

    def __init__(self):
        """Create unique subquery aliases by tracking counter."""
        self._fold_count = 1

    def generate_subquery(self) -> str:
        """Generate a new subquery alias and increment the counter."""
        alias = FOLD_SUBQUERY_FORMAT_STRING.format(self._fold_count)
        self._fold_count += 1
        return alias


@dataclass
class ColumnRouter:
    """Container for columns selected from a variety of selectables.

    ContextFields selecting from locations inside a CTE need to be redirected to get those columns
    from the corresponding columns exposed by the CTE instead. A ColumnRouter can be used to store
    these column name mappings.

    The Selectable.c property is the only property of selectables used by ContextFields, so that's
    the only property this class needs to implement to serve as a Selectable.
    TODO(bojanserafimov): make an abstract class instead of duck-typing this.
    """

    c: Dict[str, sqlalchemy.Column]


class CompilationState(object):
    """Mutable class used to keep track of state while emitting a sql query."""

    def __init__(self, sql_schema_info: SQLAlchemySchemaInfo, ir: IrAndMetadata):
        """Initialize a CompilationState, setting the current location at the root of the query."""
        # Immutable metadata
        self._sql_schema_info: SQLAlchemySchemaInfo = sql_schema_info
        self._ir: IrAndMetadata = ir
        self._used_columns: Dict[VertexPath, Set[str]] = _find_columns_used_outside_folds(
            sql_schema_info, ir
        )
        # mapping fold paths to FoldScopeLocations with field information
        self._all_folded_fields: Dict[FoldPath, Set[FoldScopeLocation]] = _find_folded_fields(ir)

        # Current query location state. Only mutable by calling _relocate.
        self._current_location: Optional[
            BaseLocation
        ] = None  # The current location in the query. None means global.
        self._current_alias: Optional[
            Alias
        ] = None  # SQLAlchemy table Alias at the current location.

        # Current folded subquery state.
        self._current_fold: Optional[
            FoldSubqueryBuilder
        ] = None  # FoldSubqueryBuilder to collect fold info and create folded subqueries.

        # Dict mapping (some_location.query_path, fold_scope_location.fold_path) tuples to
        # corresponding table Aliases. some_location is either self._current_location
        # or the base location of an open FoldScopeLocation. For Locations, the second argument of
        # the tuple will be None.
        # Note: for tables with an _x_count column, that column will always
        # be named "fold_output__x_count".
        self._aliases: Dict[Tuple[QueryPath, Optional[FoldPath]], Union[Alias, ColumnRouter]] = {}

        # Move to the beginning location of the query.
        self._relocate(ir.query_metadata_table.root_location)

        # Mapping aliases to the column used to join into them.
        self._came_from: Dict[Alias, Column] = {}

        self._recurse_needs_cte: bool = False

        # The query being constructed as the IR is processed
        self._from_clause: FromClause = self._current_alias  # The main SQLAlchemy Selectable.
        self._outputs: List[Label] = []  # SQLAlchemy Columns labelled correctly for output.
        self._filters: List[
            BinaryExpression
        ] = []  # SQLAlchemy Expressions to be used in the WHERE clause.

        # Generates aliases for fold subqueries.
        self._alias_generator: UniqueAliasGenerator = UniqueAliasGenerator()

    def __str__(self) -> str:
        """Return a human readable string of the CompilationState."""
        return (
            f"CompilationState(current location: {self._current_location}, "
            f"current fold: {self._current_fold}, "
            f"current query: {self.get_query()} "
            "(note: this may be a partial query and is not guaranteed to be valid SQL.))"
        )

    def _relocate(self, new_location: BaseLocation):
        """Move to a different location in the query, updating the _current_alias."""
        self._current_location = new_location
        # Create appropriate alias key based on whether new_location is a FoldScopeLocation or a
        # Location.
        alias_key: Tuple[QueryPath, Optional[FoldPath]]
        if isinstance(self._current_location, FoldScopeLocation):
            alias_key = (
                self._current_location.base_location.query_path,
                self._current_location.fold_path,
            )
        elif isinstance(self._current_location, Location):
            alias_key = (self._current_location.query_path, None)
        else:
            raise AssertionError(
                f"Attempted an invalid relocation to a {type(new_location)}. new_location must be "
                f"either a Location or a FoldScopeLocation. new_location was {new_location}."
            )

        # Update the current alias.
        if alias_key in self._aliases:
            self._current_alias = self._aliases[alias_key]
        else:
            self._current_alias = self._sql_schema_info.vertex_name_to_table[
                self._current_classname
            ].alias()

    # TODO merge from_column and to_column into a joindescriptor
    def _join_to_parent_location(
        self, parent_alias: Alias, from_column: str, to_column: str, optional: bool
    ):
        """Join the current location to the parent location using the column names specified."""
        if self._current_alias is None:
            raise AssertionError(
                "Attempted join to parent location when _current_alias was None "
                f"during fold {self}."
            )

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

        # Join to where we came from.
        self._from_clause = self._from_clause.join(
            self._current_alias,
            onclause=(parent_alias.c[from_column] == self._current_alias.c[to_column]),
            isouter=self._is_in_optional_scope(),
        )

    @property
    def _current_location_info(self) -> LocationInfo:
        """Get the LocationInfo of the current location in the query."""
        return self._ir.query_metadata_table.get_location_info(self._current_location)

    @property
    def _current_classname(self) -> str:
        """Get the string class name of the current location in the query."""
        return self._current_location_info.type.name

    def _is_in_optional_scope(self) -> bool:
        """Determine whether the _current_location is within an optional scope."""
        if self._current_location is None:
            return False
        return self._current_location_info.optional_scopes_depth > 0

    def backtrack(self, previous_location: BaseLocation) -> None:
        """Execute a Backtrack Block."""
        self._relocate(previous_location)

    def traverse(self, vertex_field: str, optional: bool) -> None:
        """Execute a Traverse Block."""
        if self._current_location is None:
            raise AssertionError(
                f"Attempted to traverse when the _current_location was None during fold {self}."
            )

        self._recurse_needs_cte = True

        # Follow the edge, either by calling visit_vertex if in a fold or joining to the
        # parent location.
        previous_alias = self._current_alias
        edge = self._sql_schema_info.join_descriptors[self._current_classname][vertex_field]
        self._relocate(self._current_location.navigate_to_subpath(vertex_field))
        if self._current_fold is not None:
            if not isinstance(self._current_location, FoldScopeLocation):
                raise AssertionError(
                    "Attempting to traverse inside a fold while the _current_location was not a "
                    f"FoldScopeLocation. _current_location was set to {self._current_location}."
                )
            self._current_fold.visit_vertex(
                edge,
                previous_alias,
                self._current_alias,
                self._current_location,
                self._all_folded_fields,
            )
        else:
            self._join_to_parent_location(
                previous_alias, edge.from_column, edge.to_column, optional
            )

    def _wrap_into_cte(self) -> None:
        """Wrap the current query into a cte."""
        # Additional outputs the CTE needs to export for use elsewhere in the query
        extra_outputs: List[Label] = []
        # Mapping alias_key -> external_name -> internal_name
        column_mappings: Dict[Tuple[QueryPath, Optional[FoldPath]], Dict[str, str]] = {}
        for alias_key, alias in self._aliases.items():
            vertex_path, _ = alias_key
            for used_column_name in sorted(self._used_columns[vertex_path]):
                label = "_".join(vertex_path) + "__" + used_column_name
                extra_outputs.append(alias.c[used_column_name].label(label))
                column_mappings.setdefault(alias_key, {})[used_column_name] = label

        # Wrap the query so far into a cte. Make sure to select any fields used outside the cte.
        if self._recurse_needs_cte:
            self._current_alias = self.get_query(extra_outputs).cte(recursive=False)
            self._from_clause = self._current_alias

            self._filters = []  # The filters are already included in the cte
            self._aliases = {
                alias_key: ColumnRouter(
                    {
                        external_name: self._current_alias.c[internal_name]
                        for external_name, internal_name in column_mappings.get(
                            alias_key, {}
                        ).items()
                    }
                )
                for alias_key, alias_value in self._aliases.items()
            }
            if not isinstance(self._current_location, Location):
                raise AssertionError(
                    f"Attempted to wrap to CTE while the _current_location of was type "
                    f"{type(self._current_location)}, but should have been a Location. "
                    f"_current_location was {self._current_location}."
                )
            self._current_alias = self._aliases[(self._current_location.query_path, None)]

    def _get_current_primary_key_name(self, directive_name: str) -> str:
        """Return the name of the single-column primary key at the current location.

        If there is no single-column primary key at this location, an error is raised.

        Args:
            directive_name: name of the directive that requires for the single-column
                            primary key to exist. Used in error messages only.

        Returns:
            name of the single-column primary key
        """
        if self._current_alias is None or not self._current_alias.primary_key:
            raise AssertionError(
                f"The table for vertex {self._current_classname} has no primary key specified. "
                f"This information is required to emit a {directive_name} directive."
            )
        if len(self._current_alias.primary_key) > 1:
            raise NotImplementedError(
                f"The table for vertex {self._current_classname} has a composite primary key "
                f"{self._current_alias.primary_key}. The SQL backend does not support "
                f"{directive_name} on tables with composite primary keys."
            )
        return str(self._current_alias.primary_key[0].name)

    def recurse(self, vertex_field: str, depth: int) -> None:
        """Execute a Recurse Block."""
        if self._current_fold is not None:
            raise AssertionError("Recurse inside a fold is not allowed.")
        if self._current_alias is None:
            raise AssertionError("Cannot recurse when _current_alias is None.")
        if self._current_location is None:
            raise AssertionError("Cannot recurse when _current_location is None.")
        if not isinstance(self._current_location, Location):
            raise AssertionError(
                f"Cannot recurse when _current_location is not a Location. _current_location "
                f"was set to {self._current_location}."
            )

        edge = self._sql_schema_info.join_descriptors[self._current_classname][vertex_field]
        primary_key = self._get_current_primary_key_name("@recurse")

        # Wrap the query so far into a cte if it would speed up the recursive query.
        if self._recurse_needs_cte:
            self._wrap_into_cte()

        previous_alias = self._current_alias
        self._relocate(self._current_location.navigate_to_subpath(vertex_field))

        # Sanitize literal columns to be used in the query
        if not isinstance(depth, int):
            raise AssertionError(f"Depth must be a number. Received {type(depth)} {depth}.")
        literal_depth = sqlalchemy.literal_column(str(depth))
        literal_0 = sqlalchemy.literal_column("0")
        literal_1 = sqlalchemy.literal_column("1")

        # Find which columns should be selected
        used_columns = sorted(self._used_columns[self._current_location.query_path])

        # The base of the recursive CTE selects all needed columns and sets the depth to 0
        base = sqlalchemy.select(
            [previous_alias.c[col].label(col) for col in used_columns]
            + [previous_alias.c[primary_key].label(CTE_KEY_NAME), literal_0.label(CTE_DEPTH_NAME),]
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

        # Instead of joining to the current _from_clause, we make this alias the _from_clause.
        # If the existing _from_clause had any information in it, then the _current_alias would
        # be a cte that contains all that information.
        self._from_clause = self._current_alias

    def start_global_operations(self) -> None:
        """Execute a GlobalOperationsStart block."""
        if self._current_location is None:
            raise AssertionError("CompilationState is already in global scope.")
        self._current_location = None

    def filter(self, predicate: Expression) -> None:
        """Execute a Filter Block."""
        self._recurse_needs_cte = True

        # If there is an active fold, add the filter to the current fold. Note that this is only for
        # regular fields i.e. non-_x_count fields. Filtering on _x_count will use the COUNT(*)
        # output from the folded subquery and apply the filter in the global WHERE clause.
        if self._current_fold is not None:
            if _find_tagged_parameters(predicate):
                raise NotImplementedError(
                    "Filtering with a tagged parameter in a fold scope is not implemented yet."
                )
            self._current_fold.add_filter(predicate, self._aliases)

        # Otherwise, add the filter to the compilation state. Note that this is for filters outside
        # a fold scope and _x_count filters within a fold scope.
        else:
            sql_expression = predicate.to_sql(
                self._sql_schema_info.dialect, self._aliases, self._current_alias
            )
            if self._is_in_optional_scope():
                sql_expression = sqlalchemy.or_(
                    sql_expression, self._came_from[self._current_alias].is_(None)
                )
            self._filters.append(sql_expression)

    def fold(self, fold_scope_location: FoldScopeLocation) -> None:
        """Begin execution of a Fold Block by initializing and visiting the first vertex."""
        if self._current_fold is not None:
            raise AssertionError(
                f"Fold block {fold_scope_location} entered while inside another "
                f"fold block at current location {self._current_location_info}."
            )
        if self._current_alias is None:
            raise AssertionError("Attempted to fold while _current_alias was set to None.")

        # 1. Get fold metadata.
        # Location of vertex that is folded on.
        outer_alias = self._current_alias.alias()
        outer_vertex_primary_key_name = self._get_current_primary_key_name("@fold")

        # 2. Collect edge information to join the fold subquery to the main selectable.
        edge_direction, edge_name = fold_scope_location.fold_path[0]
        full_edge_name = f"{edge_direction}_{edge_name}"
        # only works if fold scope location is the immediate child of self._current_classname
        join_descriptor = self._sql_schema_info.join_descriptors[self._current_classname][
            full_edge_name
        ]

        # 3. Initialize fold object.
        self._current_fold = FoldSubqueryBuilder(
            self._sql_schema_info.dialect, outer_alias, outer_vertex_primary_key_name
        )

        # 4. Relocate to inside the fold scope and visit the first vertex.
        self._relocate(fold_scope_location)
        self._current_fold.visit_vertex(
            join_descriptor,
            outer_alias,
            self._current_alias,
            fold_scope_location,
            self._all_folded_fields,
        )

    def unfold(self) -> None:
        """Complete the execution of a Fold Block."""
        if self._current_fold is None:
            raise AssertionError("Attempted to unfold when _current_fold was None.")

        # 1. Relocate to outside of the fold.
        if not isinstance(self._current_location, FoldScopeLocation):
            raise AssertionError(
                "Attempted to unfold while the _current_location was not a FoldScopeLocation. "
                f"_current_location was {self._current_location}."
            )
        self._relocate(self._current_location.base_location)

        # 2. End the fold, collecting the folded subquery and the location of the folded outputs.
        fold_subquery, output_vertex_location = self._current_fold.end_fold()
        fold_subquery_alias = fold_subquery.alias(self._alias_generator.generate_subquery())

        # 3. Update the alias for the subquery's folded outputs and from clause for this SQL query.
        subquery_alias_key = (
            output_vertex_location.base_location.query_path,
            output_vertex_location.fold_path,
        )
        self._aliases[subquery_alias_key] = fold_subquery_alias

        # 4. Join the fold subquery to the main from clause.
        if self._current_alias is None:
            raise AssertionError(
                f"Attempted to unfold while the _current_alias was None during fold {self}."
            )
        outer_vertex_primary_key_name = self._get_current_primary_key_name("@fold")
        self._from_clause = sqlalchemy.join(
            self._from_clause,
            fold_subquery_alias,
            onclause=(
                self._current_alias.c[outer_vertex_primary_key_name]
                == fold_subquery_alias.c[outer_vertex_primary_key_name]
            ),
            isouter=False,
        )

        # 5. Clear the fold from the compilation state.
        self._current_fold = None

    def mark_location(self) -> None:
        """Execute a MarkLocation Block."""
        alias_key: Tuple[QueryPath, Optional[FoldPath]]
        if isinstance(self._current_location, FoldScopeLocation):
            alias_key = (
                self._current_location.base_location.query_path,
                self._current_location.fold_path,
            )
        elif isinstance(self._current_location, Location):
            alias_key = (self._current_location.query_path, None)
        else:
            raise AssertionError(
                f"Attempted to mark location at a _current_location that was not a Location or a "
                f"FoldScopeLocation. _current_location was set to {self._current_location}."
            )
        # If the current location is the beginning of a fold, the current alias
        # will eventually be replaced by the resulting fold subquery during Unfold.
        self._aliases[alias_key] = self._current_alias

    def construct_result(self, output_name: str, field: Expression) -> None:
        """Execute a ConstructResult Block."""
        self._outputs.append(
            field.to_sql(self._sql_schema_info.dialect, self._aliases, self._current_alias).label(
                output_name
            )
        )

    def get_query(self, extra_outputs: Optional[List[Label]] = None) -> Select:
        """After all IR Blocks are processed, return the resulting SQLAlchemy query."""
        if not extra_outputs:
            extra_outputs = []
        return (
            sqlalchemy.select(extra_outputs + self._outputs)
            .select_from(self._from_clause)
            .where(sqlalchemy.and_(*self._filters))
        )


def emit_code_from_ir(sql_schema_info: SQLAlchemySchemaInfo, ir: IrAndMetadata) -> Select:
    """Return a SQLAlchemy Query for the query described by the internal representation.

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
            state.traverse(f"{block.direction}_{block.edge_name}", block.optional)
        elif isinstance(block, blocks.Recurse):
            state.recurse(f"{block.direction}_{block.edge_name}", block.depth)
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
            raise NotImplementedError(f"Unsupported block {block}.")

    return state.get_query()
