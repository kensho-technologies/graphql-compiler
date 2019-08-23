# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a SqlNode tree into an executable SQLAlchemy query."""
from collections import namedtuple
from datetime import date, datetime
from decimal import Decimal
import six

import sqlalchemy
from sqlalchemy import Column, bindparam, select
from sqlalchemy.sql import expression as sql_expressions
from sqlalchemy.sql.elements import BindParameter, and_

from ..compiler import expressions
from ..compiler.ir_lowering_sql import constants

from . import compiler_frontend, blocks, helpers, expressions


class CompilationState(object):
    def __init__(self, sql_schema_info, ir):
        # Metadata
        self._sql_schema_info = sql_schema_info
        self._ir = ir

        # Current state
        self._aliases = {}
        self._alias = None
        self._location = None
        self._classname = None  # Invariant: classname is the classname at the current location
        self._relocate(ir.query_metadata_table.root_location)

        # Result
        self._from_clause = self._alias
        self._outputs = []
        self._filters = []

    def _relocate(self, new_location):
        self._location = new_location
        self._classname = self._ir.query_metadata_table.get_location_info(new_location).type.name
        if self._location.query_path in self._aliases:
            self._alias = self._aliases[self._location.query_path]
        else:
            self._alias = self._sql_schema_info.tables[self._classname].alias()

    def backtrack(self, previous_location):
        self._relocate(previous_location)

    def traverse(self, vertex_field):
        # See where we're going
        edge = self._sql_schema_info.join_descriptors[self._classname][vertex_field]
        to_vertex = self._sql_schema_info.schema.get_type(
            self._classname).fields[vertex_field].type.of_type.name
        if to_vertex not in self._sql_schema_info.tables:
            raise NotImplementedError()  # It's a union

        # Go there
        previous_alias = self._alias
        self._relocate(self._location.navigate_to_subpath(vertex_field))

        # Join to where we came from
        self._from_clause = self._from_clause.join(
            self._alias,
            onclause=(previous_alias.c[edge.from_column] == self._alias.c[edge.to_column]),
            isouter=False)

    def filter(self, predicate):
        self._filters.append(predicate.to_sql(self._aliases, self._alias))

    def mark_location(self):
        self._aliases[self._location.query_path] = self._alias

    def begin_global_operations(self):
        self._alias = None
        self._location = None
        self._classname = None

    def construct_result(self, output_name, field):
        self._outputs.append(field.to_sql(self._aliases, self._alias).label(output_name))

    def get_query(self):
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
                raise NotImplementedError()
            state.traverse(u'{}_{}'.format(block.direction, block.edge_name))
        elif isinstance(block, blocks.Filter):
            state.filter(block.predicate)
        elif isinstance(block, blocks.GlobalOperationsStart):
            state.begin_global_operations()
        elif isinstance(block, blocks.ConstructResult):
            for output_name, field in six.iteritems(block.fields):
                state.construct_result(output_name, field)
        else:
            raise NotImplementedError(u'{}'.format(block))

    return state.get_query()
