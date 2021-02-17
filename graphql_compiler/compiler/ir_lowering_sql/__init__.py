# Copyright 2018-present Kensho Technologies, LLC.
import six

from .. import blocks, expressions
from ...compiler.compiler_frontend import IrAndMetadata
from ...schema.schema_info import CompositeJoinDescriptor, DirectJoinDescriptor
from ..helpers import FoldScopeLocation, get_edge_direction_and_name
from ..ir_lowering_common import common


def _remove_output_context_field_existence(ir_blocks, query_metadata_table):
    """Convert ContextFieldExistence in ConstructResult blocks to TrueLiteral."""

    def visitor_fn(expression):
        """Convert ContextFieldExistence expressions to TrueLiteral."""
        if isinstance(expression, expressions.ContextFieldExistence):
            return expressions.TrueLiteral
        return expression

    new_ir_blocks = []
    for block in ir_blocks:
        new_block = block
        if isinstance(block, blocks.ConstructResult):
            new_block = block.visit_and_update_expressions(visitor_fn)
        new_ir_blocks.append(new_block)

    return new_ir_blocks


def _find_non_null_columns(schema_info, query_metadata_table):
    """Find a column for each non-root location that's non-null if and only if the vertex exists."""
    non_null_column = {}

    # Find foreign keys used
    for location, location_info in query_metadata_table.registered_locations:
        for child_location in query_metadata_table.get_child_locations(location):
            if isinstance(child_location, FoldScopeLocation):
                continue

            edge_direction, edge_name = get_edge_direction_and_name(child_location.query_path[-1])
            vertex_field_name = "{}_{}".format(edge_direction, edge_name)
            edge = schema_info.join_descriptors[location_info.type.name][vertex_field_name]

            # The value of any column used to join to this table is an indicator of whether
            # the left join was a hit or a miss.
            if isinstance(edge, DirectJoinDescriptor):
                non_null_column[child_location.query_path] = edge.to_column
            elif isinstance(edge, CompositeJoinDescriptor):
                non_null_column[child_location.query_path] = sorted(edge.column_pairs)[0][1]
            else:
                raise AssertionError(f"Unknown join descriptor type {edge}: {type(edge)}")

    return non_null_column


class ContextColumn(expressions.Expression):
    """A column drawn from the global context.

    It is different than an expressions.ContextField because it does not reference a property
    type in the GraphQL schema, but a column name in the actual SQL table. Some columns are
    not even represented in the GraphQL schema as properties. An example is Animals.parent
    in the test schema.
    """

    def __init__(self, vertex_query_path, column_name):
        """Construct a new ContextColumn."""
        super(ContextColumn, self).__init__(vertex_query_path, column_name)
        self._vertex_query_path = vertex_query_path
        self._column_name = column_name
        self.validate()

    def validate(self):
        """Validate that the ContextColumn is correctly representable."""
        if not isinstance(self._vertex_query_path, tuple):
            raise AssertionError(
                "vertex_query_path was expected to be a tuple, but was {}: {}".format(
                    type(self._vertex_query_path), self._vertex_query_path
                )
            )

        if not isinstance(self._column_name, six.string_types):
            raise AssertionError(
                "column_name was expected to be a string, but was {}: {}".format(
                    type(self._column_name), self._column_name
                )
            )

    def to_match(self):
        """Not implemented, should not be used."""
        raise AssertionError(
            "ContextColumns are not used during the query emission process "
            "in MATCH, so this is a bug. This function should not be called."
        )

    def to_gremlin(self):
        """Not implemented, should not be used."""
        raise AssertionError(
            "ContextColumns are not used during the query emission process "
            "in Gremlin, so this is a bug. This function should not be called."
        )

    def to_cypher(self):
        """Not implemented, should not be used."""
        raise AssertionError(
            "ContextColumns are not used during the query emission process "
            "in cypher, so this is a bug. This function should not be called."
        )

    def to_sql(self, dialect, aliases, current_alias):
        """Return a sqlalchemy Column picked from the appropriate alias."""
        self.validate()
        return aliases[(self._vertex_query_path, None)].c[self._column_name]


def _lower_sql_context_field_existence(schema_info, ir_blocks, query_metadata_table):
    """Lower ContextFieldExistence to BinaryComposition."""
    non_null_columns = _find_non_null_columns(schema_info, query_metadata_table)

    def visitor_fn(expression):
        """Convert ContextFieldExistence expressions to TrueLiteral."""
        if not isinstance(expression, expressions.ContextFieldExistence):
            return expression

        query_path = expression.location.query_path
        return expressions.BinaryComposition(
            "!=", ContextColumn(query_path, non_null_columns[query_path]), expressions.NullLiteral
        )

    return [block.visit_and_update_expressions(visitor_fn) for block in ir_blocks]


##############
# Public API #
##############


def lower_ir(schema_info, ir):
    """Lower the IR blocks into a form that can be represented by a SQL query.

    Args:
        schema_info: SqlAlchemySchemaInfo containing all relevant schema information
        ir: IrAndMetadata representing the query to lower into SQL-compatible form

    Returns:
        ir IrAndMetadata containing lowered blocks, ready to emit
    """
    ir_blocks = ir.ir_blocks
    ir_blocks = _remove_output_context_field_existence(ir_blocks, ir.query_metadata_table)
    ir_blocks = _lower_sql_context_field_existence(schema_info, ir_blocks, ir.query_metadata_table)
    ir_blocks = common.short_circuit_ternary_conditionals(ir_blocks, ir.query_metadata_table)
    ir_blocks = common.optimize_boolean_expression_comparisons(ir_blocks)
    return IrAndMetadata(ir_blocks, ir.input_metadata, ir.output_metadata, ir.query_metadata_table)
