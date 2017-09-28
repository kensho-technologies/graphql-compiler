# Copyright 2017 Kensho Technologies, Inc.
"""Language-independent IR lowering and optimization functions."""

from funcy.py2 import pairwise

from .blocks import ConstructResult, Filter
from .expressions import (BinaryComposition, ContextField, ContextFieldExistence, FalseLiteral,
                          NullLiteral, TrueLiteral)
from .helpers import validate_safe_string


def merge_consecutive_filter_clauses(ir_blocks):
    """Merge consecutive Filter(x), Filter(y) blocks into Filter(x && y) block."""
    if not ir_blocks:
        return ir_blocks

    new_ir_blocks = [ir_blocks[0]]

    for previous_block, current_block in pairwise(ir_blocks):
        if isinstance(previous_block, Filter) and isinstance(current_block, Filter):
            new_ir_blocks[-1] = Filter(
                BinaryComposition(u'&&', previous_block.predicate, current_block.predicate))
        else:
            new_ir_blocks.append(current_block)

    return new_ir_blocks


class OutputContextVertex(ContextField):
    """An expression referring to a vertex location for output from the global context."""

    def validate(self):
        """Validate that the OutputContextVertex is correctly representable."""
        super(OutputContextVertex, self).validate()

        if self.location.field is not None:
            raise ValueError(u'Expected location at a vertex, but got: {}'.format(self.location))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        validate_safe_string(mark_name)

        if field_name is not None:
            raise AssertionError(u'Vertex location has non-None field_name: '
                                 u'{} {}'.format(field_name, self.location))

        return mark_name


def lower_context_field_existence(ir_blocks):
    """Lower ContextFieldExistence expressions into lower-level expressions."""
    def regular_visitor_fn(expression):
        """Expression visitor function that rewrites ContextFieldExistence expressions."""
        if not isinstance(expression, ContextFieldExistence):
            return expression

        # Since this function is only used in blocks that aren't ConstructResult,
        # the location check is performed using a regular ContextField expression.
        return BinaryComposition(
            u'!=',
            ContextField(expression.location),
            NullLiteral)

    def construct_result_visitor_fn(expression):
        """Expression visitor function that rewrites ContextFieldExistence expressions."""
        if not isinstance(expression, ContextFieldExistence):
            return expression

        # Since this function is only used in ConstructResult blocks,
        # the location check is performed using the special OutputContextVertex expression.
        return BinaryComposition(
            u'!=',
            OutputContextVertex(expression.location),
            NullLiteral)

    new_ir_blocks = []
    for block in ir_blocks:
        new_block = None
        if isinstance(block, ConstructResult):
            new_block = block.visit_and_update_expressions(construct_result_visitor_fn)
        else:
            new_block = block.visit_and_update_expressions(regular_visitor_fn)
        new_ir_blocks.append(new_block)

    return new_ir_blocks


def optimize_boolean_expression_comparisons(ir_blocks):
    """Optimize comparisons of a boolean binary comparison expression against a boolean literal.

    Rewriting example:
        BinaryComposition(
            '=',
            BinaryComposition('!=', something, NullLiteral)
            False)

    The above is rewritten into:
        BinaryComposition('=', something, NullLiteral)

    Args:
        ir_blocks: list of basic block objects

    Returns:
        a new list of basic block objects, with the optimization applied
    """
    operator_inverses = {
        u'=': u'!=',
        u'!=': u'=',
    }

    def visitor_fn(expression):
        """Expression visitor function that performs the above rewriting."""
        if not isinstance(expression, BinaryComposition):
            return expression

        left_is_binary_composition = isinstance(expression.left, BinaryComposition)
        right_is_binary_composition = isinstance(expression.right, BinaryComposition)

        if not left_is_binary_composition and not right_is_binary_composition:
            # Nothing to rewrite, return the expression as-is.
            return expression

        identity_literal = None  # The boolean literal for which we just use the inner expression.
        inverse_literal = None  # The boolean literal for which we negate the inner expression.
        if expression.operator == u'=':
            identity_literal = TrueLiteral
            inverse_literal = FalseLiteral
        elif expression.operator == u'!=':
            identity_literal = FalseLiteral
            inverse_literal = TrueLiteral
        else:
            return expression

        expression_to_rewrite = None
        if expression.left == identity_literal and right_is_binary_composition:
            return expression.right
        elif expression.right == identity_literal and left_is_binary_composition:
            return expression.left
        elif expression.left == inverse_literal and right_is_binary_composition:
            expression_to_rewrite = expression.right
        elif expression.right == inverse_literal and left_is_binary_composition:
            expression_to_rewrite = expression.left

        if expression_to_rewrite is None:
            # We couldn't find anything to rewrite, return the expression as-is.
            return expression
        elif expression_to_rewrite.operator not in operator_inverses:
            # We can't rewrite the inner expression since we don't know its inverse operator.
            return expression
        else:
            return BinaryComposition(
                operator_inverses[expression_to_rewrite.operator],
                expression_to_rewrite.left,
                expression_to_rewrite.right)

    new_ir_blocks = []
    for block in ir_blocks:
        new_block = block.visit_and_update_expressions(visitor_fn)
        new_ir_blocks.append(new_block)

    return new_ir_blocks
