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


def split_blocks(ir_blocks):
    if not isinstance(ir_blocks[0], blocks.QueryRoot):
        raise AssertionError(u'TODO')

    start_classname = helpers.get_only_element_from_collection(ir_blocks[0].start_class)
    local_operations = []
    found_global_operations_block = False
    global_operations = []
    for block in ir_blocks[1:]:
        if isinstance(block, blocks.QueryRoot):
            raise AssertionError(u'TODO')
        elif isinstance(block, blocks.GlobalOperationsStart):
            if found_global_operations_block:
                raise AssertionError(u'TODO')
            found_global_operations_block = True
        if found_global_operations_block:
            global_operations.append(block)
        else:
            local_operations.append(block)
    return start_classname, local_operations, global_operations


def _get_local_fields_used(expression):
    # HACK it doesn't handle all cases
    if isinstance(expression, expressions.BinaryComposition):
        return _get_local_fields_used(expression.left) + _get_local_fields_used(expression.right)
    elif isinstance(expression, expressions.LocalField):
        return [expression]
    else:
        return []

def emit_code_from_ir(sql_schema_info, ir):
    """Return a SQLAlchemy Query from a passed SqlQueryTree.

    Args:
        sql_schema_info: SQLAlchemySchemaInfo containing all relevant schema information
        ir: IrAndMetadata containing query information with lowered blocks

    Returns:
        SQLAlchemy Query
    """
    ir_blocks = ir.ir_blocks
    query_metadata_table = ir.query_metadata_table
    tables = sql_schema_info.tables
    sql_edges = sql_schema_info.join_descriptors

    current_classname, local_operations, global_operations = split_blocks(ir_blocks)
    current_location = query_metadata_table.root_location
    if current_classname not in tables:
        raise AssertionError(u'Class {} exists in the schema, but not in the SqlMetadata tables'
                             .format(current_classname))
    current_alias = tables[current_classname].alias()
    alias_at_location = {}  # Updated only at MarkLocation blocks. Maps query path to alias

    from_clause = current_alias
    outputs = []
    filters = []

    for block in local_operations:
        if isinstance(block, (blocks.EndOptional)):
            pass  # Nothing to do
        elif isinstance(block, blocks.MarkLocation):
            alias_at_location[current_location.query_path] = current_alias
        elif isinstance(block, blocks.Backtrack):
            current_location = block.location
            current_alias = alias_at_location[current_location.query_path]
            current_classname = query_metadata_table.get_location_info(current_location).type.name
        elif isinstance(block, blocks.Traverse):
            previous_alias = current_alias
            edge_field = u'{}_{}'.format(block.direction, block.edge_name)
            current_location = current_location.navigate_to_subpath(edge_field)
            if edge_field not in sql_edges.get(current_classname, {}):
                raise AssertionError(u'Edge {} from {} exists in the schema, but not in the '
                                     u'SqlMetadata edges'.format(edge_field, current_classname))
            edge = sql_edges[current_classname][edge_field]
            to_vertex = sql_schema_info.schema.get_type(current_classname).fields[edge_field].type.of_type.name
            current_alias = tables[to_vertex].alias()
            current_classname = query_metadata_table.get_location_info(current_location).type.name

            from_clause = from_clause.join(
                current_alias,
                onclause=(previous_alias.c[edge.from_column] == current_alias.c[edge.to_column]),
                isouter=block.optional)
        elif isinstance(block, blocks.Filter):
            sql_predicate = block.predicate.to_sql(alias_at_location, current_alias)

            # HACK filters in optionals are hard. This is wrong.
            if query_metadata_table.get_location_info(current_location).optional_scopes_depth > 0:
                sql_predicate = sqlalchemy.or_(sql_predicate, *[
                    expressions.BinaryComposition(u'=', local_field, expressions.Literal(None)).to_sql(
                        alias_at_location, current_alias)
                    for local_field in _get_local_fields_used(block.predicate)
                ])

            filters.append(sql_predicate)
        else:
            raise NotImplementedError(u'{}'.format(block))

    current_location = None
    for block in global_operations:
        if isinstance(block, blocks.ConstructResult):
            for output_name, field in six.iteritems(block.fields):

                # HACK for outputs in optionals. Wrong on so many levels
                if isinstance(field, expressions.TernaryConditional):
                    field = field.if_true

                outputs.append(field.to_sql(alias_at_location, current_alias).label(output_name))

    return sqlalchemy.select(outputs).select_from(from_clause).where(sqlalchemy.and_(*filters))
