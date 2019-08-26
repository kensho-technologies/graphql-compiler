# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
import six
import sqlalchemy

from . import blocks


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



class CompilationState(object):
    """Mutable class used to keep track of state while emitting a sql query."""

    def __init__(self, sql_schema_info, ir):
        """Initialize a CompilationState, setting the current location at the root of the query."""
        # Metadata
        self._sql_schema_info = sql_schema_info
        self._ir = ir

        # Current query location state. Only mutable by calling _relocate.
        self.current_location = None  # the current location in the query
        self._current_classname = None  # the classname at the current location
        self._current_alias = None  # a sqlalchemy table Alias at the current location
        self._aliases = {}  # mapping marked query paths to table _Aliases representing them
        self._relocate(ir.query_metadata_table.root_location)

        # The query being constructed as the IR is processed
        self._from_clause = self._current_alias  # the main sqlalchemy Selectable
        self._outputs = []  # sqlalchemy Columns labelled correctly for output
        self._filters = []  # sqlalchemy Expressions to be used in the where clause

    def _relocate(self, new_location):
        """Move to a different location in the query, updating the _classname and _alias."""
        self.current_location = new_location
        new_location_type = self._ir.query_metadata_table.get_location_info(new_location).type
        self._current_classname = new_location_type.name
        if self.current_location.query_path in self._aliases:
            self._current_alias = self._aliases[self.current_location.query_path]
        else:
            self._current_alias = self._sql_schema_info.tables[self._current_classname].alias()

    def backtrack(self, previous_location):
        """Execute a Backtrack Block"""
        self._relocate(previous_location)

    def traverse(self, vertex_field):
        """Execute a Traverse Block"""
        # Follow the edge
        previous_alias = self._current_alias
        edge = self._sql_schema_info.join_descriptors[self._current_classname][vertex_field]
        self._relocate(self.current_location.navigate_to_subpath(vertex_field))

        # Join to where we came from
        self._from_clause = self._from_clause.join(
            self._current_alias,
            onclause=(previous_alias.c[edge.from_column] == self._current_alias.c[edge.to_column]),
            isouter=False)

    def filter(self, predicate):
        """Execute a Filter Block"""
        self._filters.append(predicate.to_sql(self._aliases, self._current_alias))

    def mark_location(self):
        """Execute a MarkLocation Block"""
        self._aliases[self.current_location.query_path] = self._current_alias

    def construct_result(self, output_name, field):
        """Execute a ConstructResult Block"""
        self._outputs.append(field.to_sql(self._aliases, self._current_alias).label(output_name))

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
