# Copyright 2017-present Kensho Technologies, LLC.
"""Perform optimizations and lowering of the IR that allows the compiler to emit MATCH queries.

The compiler IR allows blocks and expressions that cannot be directly compiled to Gremlin or MATCH.
For example, ContextFieldExistence is an Expression that returns True iff its given vertex exists,
but the produced Gremlin and MATCH outputs for this purpose are entirely different and not easy
to generate directly from this Expression object. An output-language-aware IR lowering step allows
us to convert this Expression into other Expressions, using data already present in the IR,
to simplify the final code generation step.
"""
import six

from ..blocks import Backtrack, CoerceType, MarkLocation, QueryRoot
from ..expressions import (BinaryComposition, ContextField, ContextFieldExistence, FalseLiteral,
                           FoldedOutputContextField, Literal, TernaryConditional, TrueLiteral)
from ..helpers import FoldScopeLocation
from .utils import convert_coerce_type_to_instanceof_filter


##################################
# Optimization / lowering passes #
##################################


def rewrite_binary_composition_inside_ternary_conditional(ir_blocks):
    """Rewrite BinaryConditional expressions in the true/false values of TernaryConditionals."""
    def visitor_fn(expression):
        """Expression visitor function."""
        # MATCH queries do not allow BinaryComposition inside a TernaryConditional's true/false
        # value blocks, since OrientDB cannot produce boolean values for comparisons inside them.
        # We transform any structures that resemble the following:
        #    TernaryConditional(predicate, X, Y), with X or Y of type BinaryComposition
        # into the following:
        # - if X is of type BinaryComposition, and Y is not,
        #    BinaryComposition(
        #        u'=',
        #        TernaryConditional(
        #            predicate,
        #            TernaryConditional(X, true, false),
        #            Y
        #        ),
        #        true
        #    )
        # - if Y is of type BinaryComposition, and X is not,
        #    BinaryComposition(
        #        u'=',
        #        TernaryConditional(
        #            predicate,
        #            X,
        #            TernaryConditional(Y, true, false),
        #        ),
        #        true
        #    )
        # - if both X and Y are of type BinaryComposition,
        #    BinaryComposition(
        #        u'=',
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
        return BinaryComposition(u'=', ternary, TrueLiteral)

    new_ir_blocks = [
        block.visit_and_update_expressions(visitor_fn)
        for block in ir_blocks
    ]

    return new_ir_blocks


def lower_has_substring_binary_compositions(ir_blocks):
    """Lower Filter blocks that use the "has_substring" operation into MATCH-representable form."""
    def visitor_fn(expression):
        """Rewrite BinaryComposition expressions with "has_substring" into representable form."""
        # The implementation of "has_substring" must use the LIKE operator in MATCH, and must
        # prepend and append "%" symbols to the substring being matched.
        # We transform any structures that resemble the following:
        #    BinaryComposition(u'has_substring', X, Y)
        # into the following:
        #    BinaryComposition(
        #        u'LIKE',
        #        X,
        #        BinaryComposition(
        #            u'+',
        #            Literal("%"),
        #            BinaryComposition(
        #                 u'+',
        #                 Y,
        #                 Literal("%")
        #            )
        #        )
        #    )
        if not isinstance(expression, BinaryComposition) or expression.operator != u'has_substring':
            return expression

        return BinaryComposition(
            u'LIKE',
            expression.left,
            BinaryComposition(
                u'+',
                Literal('%'),
                BinaryComposition(
                    u'+',
                    expression.right,
                    Literal('%')
                )
            )
        )

    new_ir_blocks = [
        block.visit_and_update_expressions(visitor_fn)
        for block in ir_blocks
    ]

    return new_ir_blocks


def truncate_repeated_single_step_traversals(match_query):
    """Truncate one-step traversals that overlap a previous traversal location."""
    # Such traversals frequently happen as side-effects of the lowering process
    # of Backtrack blocks, and needlessly complicate the executed queries.
    new_match_traversals = []
    visited_locations = set()

    for current_match_traversal in match_query.match_traversals:
        ignore_traversal = False
        if len(current_match_traversal) == 1:
            # Single-step traversal detected. If its location was visited already, ignore it.
            single_step = current_match_traversal[0]
            if single_step.as_block is None:
                raise AssertionError(u'Unexpectedly found a single-step traversal with no as_block:'
                                     u' {} {}'.format(current_match_traversal, match_query))

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


def lower_backtrack_blocks(match_query, location_types):
    """Lower Backtrack blocks into (QueryRoot, MarkLocation) pairs of blocks."""
    # The lowering works as follows:
    #   1. Upon seeing a Backtrack block, end the current traversal (if non-empty).
    #   2. Start new traversal from the type and location to which the Backtrack pointed.
    #   3. If the Backtrack block had an associated MarkLocation, mark that location
    #      as equivalent to the location where the Backtrack pointed.
    new_match_traversals = []

    location_translations = dict()

    for current_match_traversal in match_query.match_traversals:
        new_traversal = []
        for step in current_match_traversal:
            if not isinstance(step.root_block, Backtrack):
                new_traversal.append(step)
            else:
                # 1. Upon seeing a Backtrack block, end the current traversal (if non-empty).
                if new_traversal:
                    new_match_traversals.append(new_traversal)
                    new_traversal = []

                backtrack_location = step.root_block.location
                backtrack_location_type = location_types[backtrack_location]

                # 2. Start new traversal from the type and location to which the Backtrack pointed.
                new_root_block = QueryRoot({backtrack_location_type.name})
                new_as_block = MarkLocation(backtrack_location)

                # 3. If the Backtrack block had an associated MarkLocation, mark that location
                #    as equivalent to the location where the Backtrack pointed.
                if step.as_block is not None:
                    location_translations[step.as_block.location] = backtrack_location

                if step.coerce_type_block is not None:
                    raise AssertionError(u'Encountered type coercion in a MatchStep with '
                                         u'a Backtrack root block, this is unexpected: {} {}'
                                         .format(step, match_query))

                new_step = step._replace(root_block=new_root_block, as_block=new_as_block)
                new_traversal.append(new_step)

        new_match_traversals.append(new_traversal)

    _flatten_location_translations(location_translations)
    new_match_query = match_query._replace(match_traversals=new_match_traversals)

    return _translate_equivalent_locations(new_match_query, location_translations)


def _flatten_location_translations(location_translations):
    """If location A translates to B, and B to C, then make A translate directly to C.

    Args:
        location_translations: dict of Location -> Location, where the key translates to the value.
                               Mutated in place for efficiency and simplicity of implementation.
    """
    sources_to_process = set(six.iterkeys(location_translations))

    def _update_translation(source):
        """Return the proper (fully-flattened) translation for the given location."""
        destination = location_translations[source]
        if destination not in location_translations:
            # "destination" cannot be translated, no further flattening required.
            return destination
        else:
            # "destination" can itself be translated -- do so,
            # and then flatten "source" to the final translation as well.
            sources_to_process.discard(destination)
            final_destination = _update_translation(destination)
            location_translations[source] = final_destination
            return final_destination

    while sources_to_process:
        _update_translation(sources_to_process.pop())


def _translate_equivalent_locations(match_query, location_translations):
    """Translate Location objects into their equivalent locations, based on the given dict."""
    new_match_traversals = []

    def visitor_fn(expression):
        """Expression visitor function used to rewrite expressions with updated Location data."""
        if isinstance(expression, (ContextField, ContextFieldExistence)):
            old_location = expression.location
            new_location = location_translations.get(old_location, old_location)

            # The Expression could be one of many types, including:
            #   - ContextField
            #   - ContextFieldExistence
            # We determine its exact class to make sure we return an object of the same class
            # as the replacement expression.
            expression_cls = type(expression)
            return expression_cls(new_location)
        elif isinstance(expression, FoldedOutputContextField):
            # Update the Location within FoldedOutputContextField
            old_location = expression.fold_scope_location.base_location
            new_location = location_translations.get(old_location, old_location)

            relative_position = expression.fold_scope_location.relative_position
            new_fold_scope_location = FoldScopeLocation(new_location, relative_position)
            field_name = expression.field_name
            field_type = expression.field_type

            return FoldedOutputContextField(new_fold_scope_location, field_name, field_type)
        else:
            return expression

    # Rewrite the Locations in the steps of each MATCH traversal.
    for current_match_traversal in match_query.match_traversals:
        new_traversal = []
        for step in current_match_traversal:
            new_step = step

            # If the root_block is a Backtrack, translate its Location if necessary.
            if isinstance(new_step.root_block, Backtrack):
                old_location = new_step.root_block.location
                if old_location in location_translations:
                    new_location = location_translations[old_location]
                    new_step = new_step._replace(root_block=Backtrack(new_location))

            # If the as_block exists, translate its Location if necessary.
            if new_step.as_block is not None:
                old_location = new_step.as_block.location
                if old_location in location_translations:
                    new_location = location_translations[old_location]
                    new_step = new_step._replace(as_block=MarkLocation(new_location))

            # If the where_block exists, update any Location objects in its predicate.
            if new_step.where_block is not None:
                new_where_block = new_step.where_block.visit_and_update_expressions(visitor_fn)
                new_step = new_step._replace(where_block=new_where_block)

            new_traversal.append(new_step)

        new_match_traversals.append(new_traversal)

    new_folds = {}
    # Update the Location within each FoldScopeLocation
    for fold_scope_location, fold_ir_blocks in six.iteritems(match_query.folds):
        relative_position = fold_scope_location.relative_position
        old_location = fold_scope_location.base_location
        new_location = location_translations.get(old_location, old_location)
        new_fold_scope_location = FoldScopeLocation(new_location, relative_position)

        new_folds[new_fold_scope_location] = fold_ir_blocks

    # Rewrite the Locations in the ConstructResult output block.
    new_output_block = match_query.output_block.visit_and_update_expressions(visitor_fn)

    return match_query._replace(match_traversals=new_match_traversals, folds=new_folds,
                                output_block=new_output_block)


def lower_folded_coerce_types_into_filter_blocks(folded_ir_blocks):
    """Lower CoerceType blocks into "INSTANCEOF" Filter blocks. Indended for folded IR blocks."""
    new_folded_ir_blocks = []
    for block in folded_ir_blocks:
        if isinstance(block, CoerceType):
            new_block = convert_coerce_type_to_instanceof_filter(block)
        else:
            new_block = block

        new_folded_ir_blocks.append(new_block)

    return new_folded_ir_blocks


def remove_backtrack_blocks_from_fold(folded_ir_blocks):
    """Return a list of IR blocks with all Backtrack blocks removed."""
    new_folded_ir_blocks = []
    for block in folded_ir_blocks:
        if not isinstance(block, Backtrack):
            new_folded_ir_blocks.append(block)
    return new_folded_ir_blocks


def truncate_repeated_single_step_traversals_in_sub_queries(compound_match_query):
    """For each sub-query, remove one-step traversals that overlap a previous traversal location."""
    lowered_match_queries = []
    for match_query in compound_match_query.match_queries:
        new_match_query = truncate_repeated_single_step_traversals(match_query)
        lowered_match_queries.append(new_match_query)

    return compound_match_query._replace(match_queries=lowered_match_queries)
