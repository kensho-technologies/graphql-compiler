# Copyright 2017-present Kensho Technologies, LLC.
"""Perform optimizations and lowering of the IR that allows the compiler to emit MATCH queries.

The compiler IR allows blocks and expressions that cannot be directly compiled to Gremlin or MATCH.
For example, ContextFieldExistence is an Expression that returns True iff its given vertex exists,
but the produced Gremlin and MATCH outputs for this purpose are entirely different and not easy
to generate directly from this Expression object. An output-language-aware IR lowering step allows
us to convert this Expression into other Expressions, using data already present in the IR,
to simplify the final code generation step.
"""
from typing import Dict, List, Optional, Set

import six

from ..blocks import Backtrack, CoerceType, Filter, MarkLocation, QueryRoot
from ..compiler_entities import BasicBlock, Expression
from ..expressions import BinaryComposition, FalseLiteral, Literal, TernaryConditional, TrueLiteral
from ..helpers import Location
from ..ir_lowering_common.location_renaming import (
    make_location_rewriter_visitor_fn,
    make_revisit_location_translations,
    translate_potential_location,
)
from ..match_query import MatchQuery, MatchStep
from ..metadata import QueryMetadataTable
from .utils import CompoundMatchQuery, convert_coerce_type_to_instanceof_filter


##################################
# Optimization / lowering passes #
##################################


def rewrite_binary_composition_inside_ternary_conditional(
    ir_blocks: List[BasicBlock],
) -> List[BasicBlock]:
    """Rewrite BinaryConditional expressions in the true/false values of TernaryConditionals."""

    def visitor_fn(expression: Expression) -> Expression:
        """Expression visitor function."""
        # MATCH queries do not allow BinaryComposition inside a TernaryConditional's true/false
        # value blocks, since OrientDB cannot produce boolean values for comparisons inside them.
        # We transform any structures that resemble the following:
        #    TernaryConditional(predicate, X, Y), with X or Y of type BinaryComposition
        # into the following:
        # - if X is of type BinaryComposition, and Y is not,
        #    BinaryComposition(
        #        '=',
        #        TernaryConditional(
        #            predicate,
        #            TernaryConditional(X, true, false),
        #            Y
        #        ),
        #        true
        #    )
        # - if Y is of type BinaryComposition, and X is not,
        #    BinaryComposition(
        #        '=',
        #        TernaryConditional(
        #            predicate,
        #            X,
        #            TernaryConditional(Y, true, false),
        #        ),
        #        true
        #    )
        # - if both X and Y are of type BinaryComposition,
        #    BinaryComposition(
        #        '=',
        #        TernaryConditional(
        #            predicate,
        #            TernaryConditional(X, true, false),
        #            TernaryConditional(Y, true, false)
        #        ),
        #        true
        #    )
        if not isinstance(expression, TernaryConditional):
            return expression

        if_true = expression.if_true
        if_false = expression.if_false

        true_branch_rewriting_necessary = isinstance(if_true, BinaryComposition)
        false_branch_rewriting_necessary = isinstance(if_false, BinaryComposition)

        if not (true_branch_rewriting_necessary or false_branch_rewriting_necessary):
            # No rewriting is necessary.
            return expression

        if true_branch_rewriting_necessary:
            if_true = TernaryConditional(if_true, TrueLiteral, FalseLiteral)

        if false_branch_rewriting_necessary:
            if_false = TernaryConditional(if_false, TrueLiteral, FalseLiteral)

        ternary = TernaryConditional(expression.predicate, if_true, if_false)
        return BinaryComposition("=", ternary, TrueLiteral)

    new_ir_blocks = [block.visit_and_update_expressions(visitor_fn) for block in ir_blocks]

    return new_ir_blocks


def _prepend_wildcard(expression: Expression) -> BinaryComposition:
    """Prepend an SQL-MATCH wildcard to an expression."""
    return BinaryComposition("+", Literal("%"), expression)


def _append_wildcard(expression: Expression) -> BinaryComposition:
    """Append an SQL-MATCH wildcard to an expression."""
    return BinaryComposition("+", expression, Literal("%"))


def lower_string_operators(ir_blocks: List[BasicBlock]) -> List[BasicBlock]:
    """Lower Filters with "has_substring", "starts_with", or "ends_with" operation into MATCH."""

    def visitor_fn(expression: Expression) -> Expression:
        if not isinstance(expression, BinaryComposition):
            return expression
        elif expression.operator == "has_substring":
            # The implementation of "has_substring" must use the LIKE operator in MATCH, and must
            # prepend and append "%" (wildcard) symbols to the substring being matched.
            # We transform any structures that resemble the following:
            #    BinaryComposition('has_substring', X, Y)
            # into the following:
            #    BinaryComposition(
            #        'LIKE',
            #        X,
            #        BinaryComposition(
            #            '+',
            #            Literal("%"),
            #            BinaryComposition(
            #                 '+',
            #                 Y,
            #                 Literal("%")
            #            )
            #        )
            #    )
            return BinaryComposition(
                "LIKE", expression.left, _prepend_wildcard(_append_wildcard(expression.right))
            )
        elif expression.operator == "starts_with":
            # Append a wildcard to the right of the argument string
            return BinaryComposition("LIKE", expression.left, _append_wildcard(expression.right))
        elif expression.operator == "ends_with":
            # Prepend a wildcard to the left of the argument string
            return BinaryComposition("LIKE", expression.left, _prepend_wildcard(expression.right))
        else:
            return expression

    new_ir_blocks = [block.visit_and_update_expressions(visitor_fn) for block in ir_blocks]

    return new_ir_blocks


def truncate_repeated_single_step_traversals(match_query: MatchQuery) -> MatchQuery:
    """Truncate one-step traversals that overlap a previous traversal location."""
    # Such traversals frequently happen as side-effects of the lowering process
    # of Backtrack blocks, and needlessly complicate the executed queries.
    new_match_traversals: List[List[MatchStep]] = []
    visited_locations: Set[Location] = set()

    for current_match_traversal in match_query.match_traversals:
        ignore_traversal = False
        if len(current_match_traversal) == 1:
            # Single-step traversal detected. If its location was visited already, ignore it.
            single_step = current_match_traversal[0]
            if single_step.as_block is None:
                raise AssertionError(
                    "Unexpectedly found a single-step traversal with no as_block:"
                    " {} {}".format(current_match_traversal, match_query)
                )

            if single_step.as_block.location in visited_locations:
                # This location was visited before, omit the traversal.
                ignore_traversal = True

        if not ignore_traversal:
            # For each step in this traversal, mark its location as visited.
            for step in current_match_traversal:
                if step.as_block is not None:
                    visited_locations.add(step.as_block.location)

            new_match_traversals.append(current_match_traversal)

    return match_query._replace(match_traversals=new_match_traversals)


def lower_backtrack_blocks(
    match_query: MatchQuery, query_metadata_table: QueryMetadataTable
) -> MatchQuery:
    """Lower Backtrack blocks into (QueryRoot, MarkLocation) pairs of blocks."""
    # The lowering works as follows:
    #   1. Upon seeing a Backtrack block, end the current traversal (if non-empty).
    #   2. Start new traversal from the type and location to which the Backtrack pointed.
    #   3. If the Backtrack block had an associated MarkLocation, ensure that location is marked
    #      as equivalent to the location where the Backtrack pointed.
    #   4. Rewrite all expressions that reference such revisit locations, making them refer to
    #      the revisit origin location instead.
    new_match_traversals: List[List[MatchStep]] = []

    locations_needing_translation: Set[Location] = set()

    for current_match_traversal in match_query.match_traversals:
        new_traversal: List[MatchStep] = []
        for step in current_match_traversal:
            if not isinstance(step.root_block, Backtrack):
                new_traversal.append(step)
            else:
                # 1. Upon seeing a Backtrack block, end the current traversal (if non-empty).
                if new_traversal:
                    new_match_traversals.append(new_traversal)
                    new_traversal = []

                backtrack_location = step.root_block.location
                backtrack_location_info = query_metadata_table.get_location_info(backtrack_location)

                # 2. Start new traversal from the type and location to which the Backtrack pointed.
                new_root_block = QueryRoot({backtrack_location_info.type.name})
                new_as_block = MarkLocation(backtrack_location)

                # 3. If the Backtrack block had an associated MarkLocation, mark that location
                #    as equivalent to the location where the Backtrack pointed.
                if step.as_block is not None:
                    locations_needing_translation.add(step.as_block.location)

                if step.coerce_type_block is not None:
                    raise AssertionError(
                        "Encountered type coercion in a MatchStep with "
                        "a Backtrack root block, this is unexpected: {} {}".format(
                            step, match_query
                        )
                    )

                new_step = step._replace(root_block=new_root_block, as_block=new_as_block)
                new_traversal.append(new_step)

        new_match_traversals.append(new_traversal)

    new_match_query = match_query._replace(match_traversals=new_match_traversals)

    location_translations = make_revisit_location_translations(query_metadata_table)

    if locations_needing_translation != set(six.iterkeys(location_translations)):
        raise AssertionError(
            "Unexpectedly, the revisit location translations table computed from "
            "the query metadata table did not match the locations needing "
            "translation. This is a bug. {} {}".format(
                location_translations, locations_needing_translation
            )
        )

    return _translate_equivalent_locations(new_match_query, location_translations)


def _translate_equivalent_locations(
    match_query: MatchQuery, location_translations: Dict[Location, Location]
) -> MatchQuery:
    """Translate Location objects into their equivalent locations, based on the given dict."""
    new_match_traversals: List[List[MatchStep]] = []

    visitor_fn = make_location_rewriter_visitor_fn(location_translations)

    # Rewrite the Locations in the steps of each MATCH traversal.
    for current_match_traversal in match_query.match_traversals:
        new_traversal: List[MatchStep] = []
        for step in current_match_traversal:
            new_step = step

            # If the root_block is a Backtrack, translate its Location if necessary.
            if isinstance(new_step.root_block, Backtrack):
                old_location = new_step.root_block.location
                if not isinstance(old_location, Location):
                    raise AssertionError(
                        f"Expected old_location to be of Location type, but got {old_location} "
                        f"instead. This is a bug."
                    )

                if old_location in location_translations:
                    new_location = location_translations[old_location]
                    new_step = new_step._replace(root_block=Backtrack(new_location))

            # If the as_block exists, translate its Location if necessary.
            if new_step.as_block is not None:
                old_location = new_step.as_block.location
                if not isinstance(old_location, Location):
                    raise AssertionError(
                        f"Expected old_location to be of Location type, but got {old_location} "
                        f"instead. This is a bug."
                    )

                if old_location in location_translations:
                    new_location = location_translations[old_location]
                    new_step = new_step._replace(as_block=MarkLocation(new_location))

            # If the where_block exists, update any Location objects in its predicate.
            if new_step.where_block is not None:
                new_where_block = new_step.where_block.visit_and_update_expressions(visitor_fn)
                new_step = new_step._replace(where_block=new_where_block)

            new_traversal.append(new_step)

        new_match_traversals.append(new_traversal)

    # Update the Location within each FoldScopeLocation
    new_folds = {
        translate_potential_location(location_translations, fold_scope_location): fold_ir_blocks
        for fold_scope_location, fold_ir_blocks in six.iteritems(match_query.folds)
    }

    # Rewrite the Locations in the ConstructResult output block.
    new_output_block = match_query.output_block.visit_and_update_expressions(visitor_fn)

    # Rewrite the Locations in the global where block.
    new_global_where_block: Optional[Filter] = None
    if match_query.where_block is not None:
        new_global_where_block = match_query.where_block.visit_and_update_expressions(visitor_fn)

    return match_query._replace(
        match_traversals=new_match_traversals,
        folds=new_folds,
        output_block=new_output_block,
        where_block=new_global_where_block,
    )


def lower_folded_coerce_types_into_filter_blocks(
    folded_ir_blocks: List[BasicBlock],
) -> List[BasicBlock]:
    """Lower CoerceType blocks into "INSTANCEOF" Filter blocks. Indended for folded IR blocks."""
    new_folded_ir_blocks: List[BasicBlock] = []
    for block in folded_ir_blocks:
        new_block: BasicBlock
        if isinstance(block, CoerceType):
            new_block = convert_coerce_type_to_instanceof_filter(block)
        else:
            new_block = block

        new_folded_ir_blocks.append(new_block)

    return new_folded_ir_blocks


def remove_backtrack_blocks_from_fold(folded_ir_blocks: List[BasicBlock]) -> List[BasicBlock]:
    """Return a list of IR blocks with all Backtrack blocks removed."""
    new_folded_ir_blocks: List[BasicBlock] = []
    for block in folded_ir_blocks:
        if not isinstance(block, Backtrack):
            new_folded_ir_blocks.append(block)
    return new_folded_ir_blocks


def truncate_repeated_single_step_traversals_in_sub_queries(
    compound_match_query: CompoundMatchQuery,
) -> CompoundMatchQuery:
    """For each sub-query, remove one-step traversals that overlap a previous traversal location."""
    lowered_match_queries = []
    for match_query in compound_match_query.match_queries:
        new_match_query = truncate_repeated_single_step_traversals(match_query)
        lowered_match_queries.append(new_match_query)

    return compound_match_query._replace(match_queries=lowered_match_queries)
