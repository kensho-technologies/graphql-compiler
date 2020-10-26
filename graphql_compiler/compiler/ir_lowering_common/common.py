# Copyright 2017-present Kensho Technologies, LLC.
"""Language-independent IR lowering and optimization functions."""
from typing import Any, Dict, List, Optional, Tuple

import six

from ...typedefs import TypedDict
from ..blocks import (
    BasicBlock,
    ConstructResult,
    EndOptional,
    Expression,
    Filter,
    Fold,
    MarkLocation,
    Recurse,
    Traverse,
    Unfold,
)
from ..compiler_entities import BasicBlockT
from ..expressions import (
    BinaryComposition,
    ContextField,
    ContextFieldExistence,
    FalseLiteral,
    Literal,
    NullLiteral,
    TernaryConditional,
    TrueLiteral,
)
from ..helpers import FoldScopeLocation, Location, validate_safe_string
from ..metadata import QueryMetadataTable


def merge_consecutive_filter_clauses(ir_blocks: List[BasicBlock]) -> List[BasicBlock]:
    """Merge consecutive Filter(x), Filter(y) blocks into Filter(x && y) block."""
    if not ir_blocks:
        return ir_blocks

    new_ir_blocks = [ir_blocks[0]]

    for block in ir_blocks[1:]:
        last_block = new_ir_blocks[-1]
        if isinstance(last_block, Filter) and isinstance(block, Filter):
            new_ir_blocks[-1] = Filter(
                BinaryComposition("&&", last_block.predicate, block.predicate)
            )
        else:
            new_ir_blocks.append(block)

    return new_ir_blocks


class OutputContextVertex(ContextField):
    """An expression referring to a vertex location for output from the global context."""

    def validate(self) -> None:
        """Validate that the OutputContextVertex is correctly representable."""
        super(OutputContextVertex, self).validate()

        if self.location.field is not None:
            raise ValueError("Expected location at a vertex, but got: {}".format(self.location))

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        validate_safe_string(mark_name)

        if field_name is not None:
            raise AssertionError(
                "Vertex location has non-None field_name: "
                "{} {}".format(field_name, self.location)
            )

        return mark_name


def lower_context_field_existence(
    ir_blocks: List[BasicBlock], query_metadata_table: QueryMetadataTable
) -> List[BasicBlock]:
    """Lower ContextFieldExistence expressions into lower-level expressions."""

    def regular_visitor_fn(expression: Expression) -> Expression:
        """Expression visitor function that rewrites ContextFieldExistence expressions."""
        if not isinstance(expression, ContextFieldExistence):
            return expression

        location_type = query_metadata_table.get_location_info(expression.location).type

        # Since this function is only used in blocks that aren't ConstructResult,
        # the location check is performed using a regular ContextField expression.
        return BinaryComposition(
            "!=", ContextField(expression.location, location_type), NullLiteral
        )

    def construct_result_visitor_fn(expression: Any) -> Any:
        """Expression visitor function that rewrites ContextFieldExistence expressions."""
        if not isinstance(expression, ContextFieldExistence):
            return expression

        location_type = query_metadata_table.get_location_info(expression.location).type

        # Since this function is only used in ConstructResult blocks,
        # the location check is performed using the special OutputContextVertex expression.
        return BinaryComposition(
            "!=", OutputContextVertex(expression.location, location_type), NullLiteral
        )

    new_ir_blocks = []
    for block in ir_blocks:
        new_block: BasicBlock
        if isinstance(block, ConstructResult):
            new_block = block.visit_and_update_expressions(construct_result_visitor_fn)
        else:
            new_block = block.visit_and_update_expressions(regular_visitor_fn)
        new_ir_blocks.append(new_block)

    return new_ir_blocks


def short_circuit_ternary_conditionals(
    ir_blocks: List[BasicBlockT], query_metadata_table: QueryMetadataTable
) -> List[BasicBlockT]:
    """If the predicate outcome in a TernaryConditional is a Literal, evaluate and simplify it."""

    def visitor_fn(expression: Expression) -> Expression:
        """Simplify TernaryConditionals."""
        if isinstance(expression, TernaryConditional) and isinstance(expression.predicate, Literal):
            if isinstance(expression.predicate.value, bool):
                if expression.predicate.value:
                    return expression.if_true
                else:
                    return expression.if_false
        return expression

    return [block.visit_and_update_expressions(visitor_fn) for block in ir_blocks]


def optimize_boolean_expression_comparisons(ir_blocks: List[BasicBlock]) -> List[BasicBlock]:
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
        new list of basic block objects, with the optimization applied
    """
    operator_inverses = {"=": "!=", "!=": "="}

    def visitor_fn(expression: Expression) -> Expression:
        """Expression visitor function that performs the above rewriting."""
        if not isinstance(expression, BinaryComposition):
            return expression

        left_is_binary_composition: Optional[BinaryComposition] = (
            expression.left if isinstance(expression.left, BinaryComposition) else None
        )
        right_is_binary_composition: Optional[BinaryComposition] = (
            expression.right if isinstance(expression.right, BinaryComposition) else None
        )

        if not left_is_binary_composition and not right_is_binary_composition:
            # Nothing to rewrite, return the expression as-is.
            return expression

        identity_literal = None  # The boolean literal for which we just use the inner expression.
        inverse_literal = None  # The boolean literal for which we negate the inner expression.
        if expression.operator == "=":
            identity_literal = TrueLiteral
            inverse_literal = FalseLiteral
        elif expression.operator == "!=":
            identity_literal = FalseLiteral
            inverse_literal = TrueLiteral
        else:
            return expression

        expression_to_rewrite: Optional[BinaryComposition] = None
        if expression.left == identity_literal and right_is_binary_composition:
            return expression.right
        elif expression.right == identity_literal and left_is_binary_composition:
            return expression.left
        elif expression.left == inverse_literal and right_is_binary_composition:
            expression_to_rewrite = right_is_binary_composition
        elif expression.right == inverse_literal and left_is_binary_composition:
            expression_to_rewrite = left_is_binary_composition

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
                expression_to_rewrite.right,
            )

    new_ir_blocks = []
    for block in ir_blocks:
        new_block = block.visit_and_update_expressions(visitor_fn)
        new_ir_blocks.append(new_block)

    return new_ir_blocks


def extract_folds_from_ir_blocks(
    ir_blocks: List[BasicBlock],
) -> Tuple[Dict[FoldScopeLocation, List[BasicBlock]], List[BasicBlock],]:
    """Extract all @fold data from the IR blocks, and cut the folded IR blocks out of the IR.

    Args:
        ir_blocks: list of IR blocks to extract fold data from

    Returns:
        tuple (folds, remaining_ir_blocks):
        - folds: dict of FoldScopeLocation -> list of IR blocks corresponding to that @fold scope.
                 The list does not contain Fold or Unfold blocks.
        - remaining_ir_blocks: list of IR blocks that were not part of a Fold-Unfold section.
    """
    folds = dict()
    remaining_ir_blocks: List[BasicBlock] = []
    current_folded_blocks: List[BasicBlock] = []
    in_fold_location = None

    for block in ir_blocks:
        if isinstance(block, Fold):
            if in_fold_location is not None:
                raise AssertionError(
                    "in_fold_location was not None at a Fold block: {} {} "
                    "{}".format(current_folded_blocks, remaining_ir_blocks, ir_blocks)
                )

            in_fold_location = block.fold_scope_location
        elif isinstance(block, Unfold):
            if in_fold_location is None:
                raise AssertionError(
                    "in_fold_location was None at an Unfold block: {} {} "
                    "{}".format(current_folded_blocks, remaining_ir_blocks, ir_blocks)
                )

            folds[in_fold_location] = current_folded_blocks
            current_folded_blocks = []
            in_fold_location = None
        else:
            if in_fold_location is not None:
                current_folded_blocks.append(block)
            else:
                remaining_ir_blocks.append(block)

    return folds, remaining_ir_blocks


def extract_optional_location_root_info(
    ir_blocks: List[BasicBlock],
) -> Tuple[List[Location], Dict[Location, Tuple[Location, ...]]]:
    """Construct a mapping from locations within @optional to their correspoding optional Traverse.

    Args:
        ir_blocks: list of IR blocks to extract optional data from

    Returns:
        tuple (complex_optional_roots, location_to_optional_roots):
        complex_optional_roots: list of @optional locations (location immmediately preceding
                                an @optional Traverse) that expand vertex fields
        location_to_optional_roots: dict mapping from location -> optional_roots where location is
                                    within some number of @optionals and optional_roots is a tuple
                                    of optional root locations preceding the successive @optional
                                    scopes within which the location resides
    """
    complex_optional_roots = []
    location_to_optional_roots = dict()

    # These are both stacks that perform depth-first search on the tree of @optional edges.
    # At any given location they contain
    # - in_optional_root_locations: all the optional root locations
    # - encountered_traverse_within_optional: whether the optional is complex or not
    # in order that they appear on the path from the root to that location.
    in_optional_root_locations: List[Location] = []
    encountered_traverse_within_optional: List[bool] = []

    # Blocks within folded scopes should not be taken into account in this function.
    _, non_folded_ir_blocks = extract_folds_from_ir_blocks(ir_blocks)

    preceding_location: Optional[Location] = None
    for current_block in non_folded_ir_blocks:
        if len(in_optional_root_locations) > 0 and isinstance(current_block, (Traverse, Recurse)):
            encountered_traverse_within_optional[-1] = True

        if isinstance(current_block, Traverse) and current_block.optional:
            if preceding_location is None:
                raise AssertionError(
                    "No MarkLocation found before an optional Traverse: {} {}".format(
                        current_block, non_folded_ir_blocks
                    )
                )

            in_optional_root_locations.append(preceding_location)
            encountered_traverse_within_optional.append(False)
        elif isinstance(current_block, EndOptional):
            if len(in_optional_root_locations) == 0:
                raise AssertionError(
                    "in_optional_root_locations was empty at an EndOptional "
                    "block: {}".format(ir_blocks)
                )

            if encountered_traverse_within_optional[-1]:
                complex_optional_roots.append(in_optional_root_locations[-1])

            in_optional_root_locations.pop()
            encountered_traverse_within_optional.pop()
        elif isinstance(current_block, MarkLocation):
            current_location = current_block.location
            if not isinstance(current_location, Location):
                raise AssertionError(
                    f"Expected current_location to be an instance of Location, but instead "
                    f"found value {current_location} of type {type(current_location)}. "
                    f"This is a bug!"
                )

            preceding_location = current_location
            if len(in_optional_root_locations) != 0:
                # in_optional_root_locations will not be empty if and only if we are within an
                # @optional scope. In this case, we add the current location to the dictionary
                # mapping it to the sequence of optionals locations leading up to it.
                optional_root_locations_stack = tuple(in_optional_root_locations)
                location_to_optional_roots[current_location] = optional_root_locations_stack
        else:
            # No locations need to be marked, and no optional scopes begin or end here.
            pass

    return complex_optional_roots, location_to_optional_roots


SimpleOptionalLocationInfo = TypedDict(
    "SimpleOptionalLocationInfo",
    {
        "inner_location": Location,
        "edge_field": str,
    },
)


def extract_simple_optional_location_info(
    ir_blocks: List[BasicBlock],
    complex_optional_roots: List[Location],
    location_to_optional_roots: Dict[Location, Tuple[Location, ...]],
) -> Dict[Location, SimpleOptionalLocationInfo]:
    """Construct a map from simple optional locations to their inner location and traversed edge.

    Args:
        ir_blocks: list of IR blocks to extract optional data from
        complex_optional_roots: list of @optional locations (location immmediately preceding
                                an @optional traverse) that expand vertex fields
        location_to_optional_roots: dict mapping from location -> optional_roots where location is
                                    within some number of @optionals and optional_roots is a tuple
                                    of optional root locations preceding the successive @optional
                                    scopes within which the location resides

    Returns:
        dict mapping from simple_optional_root_location -> dict containing keys
         - 'inner_location': Location object correspoding to the unique MarkLocation present within
                             a simple optional (one that does not expand vertex fields) scope
         - 'edge_field': string representing the optional edge being traversed
        where simple_optional_root_to_inner_location is the location preceding the @optional scope
    """
    # Simple optional roots are a subset of location_to_optional_roots.values() (all optional roots)
    # We filter out the ones that are also present in complex_optional_roots.
    location_to_preceding_optional_root_iteritems = six.iteritems(
        {
            location: optional_root_locations_stack[-1]
            for location, optional_root_locations_stack in six.iteritems(location_to_optional_roots)
        }
    )
    simple_optional_root_to_inner_location = {
        optional_root_location: inner_location
        for inner_location, optional_root_location in location_to_preceding_optional_root_iteritems
        if optional_root_location not in complex_optional_roots
    }
    simple_optional_root_locations = set(simple_optional_root_to_inner_location.keys())

    # Blocks within folded scopes should not be taken into account in this function.
    _, non_folded_ir_blocks = extract_folds_from_ir_blocks(ir_blocks)

    simple_optional_root_info = {}
    preceding_location: Optional[Location] = None
    for current_block in non_folded_ir_blocks:
        if isinstance(current_block, MarkLocation):
            current_location = current_block.location
            if not isinstance(current_location, Location):
                raise AssertionError(
                    f"Expected current_location to be an instance of Location, but instead "
                    f"found value {current_location} of type {type(current_location)}. "
                    f"This is a bug!"
                )
            preceding_location = current_location
        elif isinstance(current_block, Traverse) and current_block.optional:
            if preceding_location in simple_optional_root_locations:
                # The current optional Traverse is "simple"
                # i.e. it does not contain any Traverses within.
                inner_location = simple_optional_root_to_inner_location[preceding_location]
                simple_optional_info_dict: SimpleOptionalLocationInfo = {
                    "inner_location": inner_location,
                    "edge_field": current_block.get_field_name(),
                }
                simple_optional_root_info[preceding_location] = simple_optional_info_dict

    return simple_optional_root_info


def remove_end_optionals(ir_blocks: List[BasicBlockT]) -> List[BasicBlockT]:
    """Return a list of IR blocks as a copy of the original, with EndOptional blocks removed."""
    new_ir_blocks = []
    for block in ir_blocks:
        if not isinstance(block, EndOptional):
            new_ir_blocks.append(block)
    return new_ir_blocks
