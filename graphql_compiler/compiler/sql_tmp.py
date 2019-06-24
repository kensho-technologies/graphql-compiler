# Copyright 2017-present Kensho Technologies, LLC.
import sqlalchemy
import six
import unittest
from . import compiler_frontend, blocks, helpers, expressions


def lower_ir(ir_blocks, metadata_table, type_equivalence_hints=None):
    return ir_blocks


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


def emit_sql(ir_blocks, query_metadata_table, compiler_metadata):
    """Emit SQLAlchemy from IR.

    Args:
        - ir: IR
        - tables: dict from graphql vertex names to sqlalchemy tables. The tables can come from different
          metadatas, and live in different tables, it doesn't really matter. If they do come from different
          databases, their table.schema should contain '<database_name>.<schema_name>'.
        - sql_edges: dict mapping graphql classes to:
                        dict mapping edge fields at that class to a dict with the following info:
                           to_table: GrapqQL vertex where the edge ends up
                           from_column: column name in this table
                           to_column: column name in tables[to_table]. The join is done on the from_column
                                      and to_column being equal. If you really need other kinds of joins,
                                      feel free to extend the interface.
    """
    tables = compiler_metadata.table_name_to_table
    sql_edges = compiler_metadata.joins

    current_classname, local_operations, global_operations = split_blocks(ir_blocks)
    current_location = query_metadata_table.root_location
    if current_classname not in tables:
        # TODO this is bad
        raise NotImplementedError(u'Edges need to be added in test_helpers {}'
                                  .format(current_classname))
    current_alias = tables[current_classname].alias()
    alias_at_location = {}  # Updated only at MarkLocation blocks

    from_clause = current_alias
    outputs = []
    filters = []

    for block in local_operations:
        if isinstance(block, (blocks.EndOptional)):
            pass  # Nothing to do
        elif isinstance(block, blocks.MarkLocation):
            alias_at_location[current_location] = current_alias
        elif isinstance(block, blocks.Backtrack):
            current_location = block.location
            current_alias = alias_at_location[current_location]
            current_classname = query_metadata_table.get_location_info(current_location).type.name
        elif isinstance(block, blocks.Traverse):
            previous_alias = current_alias
            edge_field = u'{}_{}'.format(block.direction, block.edge_name)
            current_location = current_location.navigate_to_subpath(edge_field)
            if edge_field not in sql_edges.get(current_classname, {}):
                # TODO this is bad
                raise NotImplementedError(u'Edges need to be added in test_helpers')
            edge = sql_edges[current_classname][edge_field]
            current_alias = tables[edge['to_table']].alias()
            current_classname = query_metadata_table.get_location_info(current_location).type.name

            from_clause = from_clause.join(
                current_alias,
                onclause=(previous_alias.c[edge['from_column']] == current_alias.c[edge['to_column']]),
                isouter=block.optional)
        elif isinstance(block, blocks.Filter):
            # TODO check it works for filter inside optional.
            filters.append(block.predicate.to_sql(current_alias))
        else:
            raise NotImplementedError(u'{}'.format(block))

    current_location = None
    for block in global_operations:
        if isinstance(block, blocks.ConstructResult):
            for output_name, field in six.iteritems(block.fields):
                # import pdb; pdb.set_trace()

                # HACK for outputs in optionals
                if isinstance(field, expressions.TernaryConditional):
                    if isinstance(field.predicate, expressions.ContextFieldExistence):
                        field = field.if_true

                table = alias_at_location[field.location.at_vertex()]
                outputs.append(table.c.get(field.location.field).label(output_name))

    return sqlalchemy.select(outputs).select_from(from_clause).where(sqlalchemy.and_(*filters))
