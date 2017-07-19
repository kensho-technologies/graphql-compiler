# Copyright 2017 Kensho Technologies, Inc.
"""Language-independent IR lowering and optimization functions."""

from funcy import pairwise

from .blocks import (Backtrack, CoerceType, ConstructResult, Filter, MarkLocation, OutputSource,
                     QueryRoot, Recurse, Traverse)
from .expressions import (BinaryComposition, ContextField, ContextFieldExistence, FalseLiteral,
                          NullLiteral, TrueLiteral)
from .helpers import validate_safe_string


#################
# Sanity checks #
#################

def sanity_check_ir_blocks_from_frontend(ir_blocks):
    """Assert that IR blocks originating from the frontend do not have nonsensical structure.

    Args:
        ir_blocks: list of BasicBlocks representing the IR to sanity-check

    Raises:
        AssertionError, if the IR has unexpected structure. If the IR produced by the front-end
        cannot be successfully and correctly used to generate MATCH or Gremlin, this is the
        method that should catch the problem.
    """
    if not ir_blocks:
        raise AssertionError(u'Received no ir_blocks: {}'.format(ir_blocks))

    # QueryRoot is always and only the first block.
    if not isinstance(ir_blocks[0], QueryRoot):
        raise AssertionError(u'The first block was not QueryRoot: {}'.format(ir_blocks))
    for block in ir_blocks[1:]:
        if isinstance(block, QueryRoot):
            raise AssertionError(u'Found QueryRoot after the first block: {}'.format(ir_blocks))

    # ConstructResult is always and only the last block.
    if not isinstance(ir_blocks[-1], ConstructResult):
        raise AssertionError(u'The last block was not ConstructResult: {}'.format(ir_blocks))
    for block in ir_blocks[:-1]:
        if isinstance(block, ConstructResult):
            raise AssertionError(u'Found ConstructResult before the last block: '
                                 u'{}'.format(ir_blocks))

    # There are no Traverse / Backtrack / Recurse blocks after an OutputSource block.
    seen_output_source = False
    for block in ir_blocks:
        if isinstance(block, OutputSource):
            seen_output_source = True
        elif seen_output_source:
            if isinstance(block, (Backtrack, Traverse, Recurse)):
                raise AssertionError(u'Found Backtrack / Traverse / Recurse '
                                     u'after OutputSource block: '
                                     u'{}'.format(ir_blocks))

    for first_block, second_block in pairwise(ir_blocks):
        # Always Filter before MarkLocation, never after.
        if isinstance(first_block, MarkLocation) and isinstance(second_block, Filter):
            raise AssertionError(u'Found Filter after MarkLocation block: {}'.format(ir_blocks))

        # There's no point in marking the same location twice in a row.
        if isinstance(first_block, MarkLocation) and isinstance(second_block, MarkLocation):
            raise AssertionError(u'Found consecutive MarkLocation blocks: {}'.format(ir_blocks))

        # Traverse blocks with optional=True are immediately preceded by a MarkLocation block.
        if isinstance(second_block, Traverse) and second_block.optional:
            if not isinstance(first_block, MarkLocation):
                raise AssertionError(u'Expected MarkLocation before Traverse with optional=True, '
                                     u'but none was found: {}'.format(ir_blocks))

        # Traverse blocks with optional=True are immediately followed
        # by a MarkLocation, CoerceType or Filter block.
        if isinstance(first_block, Traverse) and first_block.optional:
            if not isinstance(second_block, (MarkLocation, CoerceType, Filter)):
                raise AssertionError(u'Expected MarkLocation, CoerceType or Filter after Traverse '
                                     u'with optional=True. Found: {}'.format(ir_blocks))

        # CoerceType blocks are immediately followed by a MarkLocation or Filter block.
        if isinstance(first_block, CoerceType):
            if not isinstance(second_block, (MarkLocation, Filter)):
                raise AssertionError(u'Expected MarkLocation or Filter after CoerceType, '
                                     u'but none was found: {}'.format(ir_blocks))

        # Backtrack blocks with optional=True are immediately followed by a MarkLocation block.
        if isinstance(first_block, Backtrack) and first_block.optional:
            if not isinstance(second_block, MarkLocation):
                raise AssertionError(u'Expected MarkLocation after Backtrack with optional=True, '
                                     u'but none was found: {}'.format(ir_blocks))

        # Recurse blocks are immediately preceded by a MarkLocation block.
        if isinstance(second_block, Recurse):
            if not isinstance(first_block, MarkLocation):
                raise AssertionError(u'Expected MarkLocation before Recurse, but none was found: '
                                     u'{}'.format(ir_blocks))

    # There's exactly one QueryRoot / Traverse / Recurse / Backtrack block (total)
    # between any two MarkLocation blocks.
    traversal_blocks = 0
    for block in ir_blocks:
        # Treat QueryRoot as a Backtrack / Recurse / Traverse block,
        # to handle the first MarkLocation.
        if isinstance(object, (Backtrack, Traverse, Recurse, QueryRoot)):
            traversal_blocks += 1
        elif isinstance(object, MarkLocation):
            if traversal_blocks != 1:
                raise AssertionError(u'Expected 1 traversal block between '
                                     u'MarkLocation blocks, but found: '
                                     u'{} {}'.format(traversal_blocks, ir_blocks))
            traversal_blocks = 0

    # Exactly one MarkLocation block is found between a QueryRoot / Traverse / Recurse block,
    # and the first subsequent Traverse, Recurse, Backtrack or ConstructResult block.
    found_start_block = False
    mark_location_blocks = 0
    for block in ir_blocks:
        # Terminate started intervals before opening new ones.
        end_interval_types = (Backtrack, ConstructResult, Recurse, Traverse)
        if isinstance(block, end_interval_types) and found_start_block:
            found_start_block = False
            if mark_location_blocks != 1:
                raise AssertionError(u'Expected 1 MarkLocation block between traversals, found: '
                                     u'{} {}'.format(mark_location_blocks, ir_blocks))

        # Now consider opening new intervals or processing MarkLocation blocks.
        if isinstance(block, MarkLocation):
            mark_location_blocks += 1
        elif isinstance(block, (QueryRoot, Traverse, Recurse)):
            found_start_block = True
            mark_location_blocks = 0


#######################################################
# Language-independent optimization / lowering passes #
#######################################################

def merge_consecutive_filter_clauses(ir_blocks):
    """Merge consecutive Filter(x), Filter(y) blocks into Filter(x && y) block."""
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
