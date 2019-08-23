# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
from graphql.type.definition import GraphQLUnionType
import six
import sqlalchemy

from . import blocks


class CompilationState(object):
    """Mutable class used to keep track of state while emitting a sql query."""

    def __init__(self, sql_schema_info, ir):
        """Initialize a CompilationState, setting the current location at the root of the query."""
        # Metadata
        self._sql_schema_info = sql_schema_info
        self._ir = ir

        # Current query location state. Only mutable by calling _relocate.
        self._location = None  # the current location in the query
        self._classname = None  # the classname at the current location
        self._alias = None  # a sqlalchemy table Alias at the current location
        self._aliases = {}  # mapping marked query paths to table Aliases representing them
        self._relocate(ir.query_metadata_table.root_location)

        # The query being constructed as the IR is processed
        self._from_clause = self._alias  # the main sqlalchemy Selectable
        self._outputs = []  # sqlalchemy Columns labelled correctly for output
        self._filters = []  # sqlalchemy Expressions to be used in the where clause

    def _relocate(self, new_location):
        """Move to a different location in the query, updating the _classname and _alias."""
        self._location = new_location
        new_location_type = self._ir.query_metadata_table.get_location_info(new_location).type
        self._classname = new_location_type.name
        if self._location.query_path in self._aliases:
            self._alias = self._aliases[self._location.query_path]
        else:
            if isinstance(new_location_type, GraphQLUnionType):
                raise NotImplementedError(u'Traversing to union types is not implemented.')
            self._alias = self._sql_schema_info.tables[self._classname].alias()

    def backtrack(self, previous_location):
        """Execute a Backtrack Block"""
        self._relocate(previous_location)

    def traverse(self, vertex_field):
        """Execute a Traverse Block"""
        # Follow the edge
        previous_alias = self._alias
        edge = self._sql_schema_info.join_descriptors[self._classname][vertex_field]
        self._relocate(self._location.navigate_to_subpath(vertex_field))

        # Join to where we came from
        self._from_clause = self._from_clause.join(
            self._alias,
            onclause=(previous_alias.c[edge.from_column] == self._alias.c[edge.to_column]),
            isouter=False)

    def filter(self, predicate):
        """Execute a Filter Block"""
        self._filters.append(predicate.to_sql(self._aliases, self._alias))

    def mark_location(self):
        """Execute a MarkLocation Block"""
        self._aliases[self._location.query_path] = self._alias

    def construct_result(self, output_name, field):
        """Execute a ConstructResult Block"""
        self._outputs.append(field.to_sql(self._aliases, self._alias).label(output_name))

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
    for block in ir.ir_blocks:
        if isinstance(block, blocks.QueryRoot):
            pass
        elif isinstance(block, blocks.MarkLocation):
            state.mark_location()
        elif isinstance(block, blocks.Backtrack):
            state.backtrack(block.location)
        elif isinstance(block, blocks.Traverse):
            if block.optional:
                raise NotImplementedError(u'The SQL backend does not support @optional.')
            state.traverse(u'{}_{}'.format(block.direction, block.edge_name))
        elif isinstance(block, blocks.Filter):
            state.filter(block.predicate)
        elif isinstance(block, blocks.GlobalOperationsStart):
            pass
        elif isinstance(block, blocks.ConstructResult):
            for output_name, field in six.iteritems(block.fields):
                state.construct_result(output_name, field)
        else:
            raise NotImplementedError(u'Unsupported block {}.'.format(block))

    return state.get_query()
