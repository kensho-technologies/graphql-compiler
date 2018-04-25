# Copyright 2017 Kensho Technologies, LLC.
"""Perform optimizations and lowering of the IR that allows the compiler to emit MATCH queries.

The compiler IR allows blocks and expressions that cannot be directly compiled to Gremlin or MATCH.
For example, ContextFieldExistence is an Expression that returns True iff its given vertex exists,
but the produced Gremlin and MATCH outputs for this purpose are entirely different and not easy
to generate directly from this Expression object. An output-language-aware IR lowering step allows
us to convert this Expression into other Expressions, using data already present in the IR,
to simplify the final code generation step.
"""
from collections import deque

import funcy.py2 as funcy
import six

from .blocks import Backtrack, CoerceType, Filter, MarkLocation, QueryRoot, Traverse
from .expressions import (BinaryComposition, ContextField, ContextFieldExistence, Expression,
                          FalseLiteral, Literal, LocalField, TernaryConditional, TrueLiteral)
from .ir_lowering_common import (lower_context_field_existence, merge_consecutive_filter_clauses,
                                 optimize_boolean_expression_comparisons)
from .ir_sanity_checks import sanity_check_ir_blocks_from_frontend
from .match_query import MatchStep, convert_to_match_query
from .workarounds import orientdb_class_with_while, orientdb_eval_scheduling


class BetweenClause(Expression):
    """A `BETWEEN` Expression, constraining a field value to lie within a lower and upper bound."""

    def __init__(self, field, lower_bound, upper_bound):
        """Construct an expression that is true when the field value is within the given bounds.

        Args:
            field: LocalField Expression, denoting the field in consideration
            lower_bound: lower bound constraint for given field
            upper_bound: upper bound constraint for given field

        Returns:
            a new BetweenClause object
        """
        super(BetweenClause, self).__init__(field, lower_bound, upper_bound)
        self.field = field
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound

    def validate(self):
        """Validate that the Between Expression is correctly representable."""
        if not isinstance(self.field, LocalField):
            raise TypeError(u'Expected LocalField field, got: {} {}'.format(
                type(self.field).__name__, self.field))

        if not isinstance(self.lower_bound, Expression):
            raise TypeError(u'Expected Expression lower_bound, got: {} {}'.format(
                type(self.lower_bound).__name__, self.lower_bound))

        if not isinstance(self.upper_bound, Expression):
            raise TypeError(u'Expected Expression upper_bound, got: {} {}'.format(
                type(self.upper_bound).__name__, self.upper_bound))

    def visit_and_update(self, visitor_fn):
        """Create an updated version (if needed) of BetweenClause via the visitor pattern."""
        new_lower_bound = self.lower_bound.visit_and_update(visitor_fn)
        new_upper_bound = self.upper_bound.visit_and_update(visitor_fn)

        if new_lower_bound is not self.lower_bound or new_upper_bound is not self.upper_bound:
            return visitor_fn(BetweenClause(self.field, new_lower_bound, new_upper_bound))
        else:
            return visitor_fn(self)

    def to_match(self):
        """Return a unicode object with the MATCH representation of this BetweenClause."""
        template = u'({field_name} BETWEEN {lower_bound} AND {upper_bound})'
        return template.format(
            field_name=self.field.to_match(),
            lower_bound=self.lower_bound.to_match(),
            upper_bound=self.upper_bound.to_match())

    def to_gremlin(self):
        """Must never be called."""
        raise NotImplementedError()


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
    # of Backtrack or optional Traverse blocks, and needlessly complicate the executed queries.
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
        else:
            # For each step in this traversal, mark its location as visited.
            for step in current_match_traversal:
                if step.as_block is not None:
                    visited_locations.add(step.as_block.location)

        if not ignore_traversal:
            new_match_traversals.append(current_match_traversal)

    return match_query._replace(match_traversals=new_match_traversals)


def lower_optional_traverse_blocks(match_query, location_types):
    """Lower optional Traverse blocks by starting a new QueryRoot after the Traverse."""
    # Specifically, we apply the following process, noting that filtering inside an optional
    # block is not allowed:
    #   1. Upon seeing a step with an optional Traverse root block,
    #      make that step the last step in its MATCH traversal.
    #   2. Start a new MATCH traversal at the location the optional Traverse was going.
    # The rest of the query resumes from there. The corresponding optional Backtrack block
    # is handled in lower_backtrack_blocks().
    new_match_traversals = []

    for current_match_traversal in match_query.match_traversals:
        new_traversal = []
        for step in current_match_traversal:
            new_traversal.append(step)
            if isinstance(step.root_block, Traverse) and step.root_block.optional:
                # 1. Upon seeing a step with an optional Traverse root block,
                #    make that step the last step in its MATCH traversal.
                new_match_traversals.append(new_traversal)
                new_traversal = []

                if step.as_block is None:
                    raise AssertionError(u'Unexpectedly found a Traverse step with no as_block: '
                                         u'{} {}'.format(step, match_query))

                traverse_location = step.as_block.location
                traverse_location_type = location_types[traverse_location]

                # 2. Start a new MATCH traversal at the location the optional Traverse was going.
                new_root_block = QueryRoot({traverse_location_type.name})
                new_as_block = MarkLocation(traverse_location)
                new_step = MatchStep(root_block=new_root_block,
                                     as_block=new_as_block,
                                     coerce_type_block=None,
                                     where_block=None)
                new_traversal.append(new_step)

        new_match_traversals.append(new_traversal)

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

                new_step = step._replace(root_block=new_root_block, as_block=new_as_block)
                new_traversal.append(new_step)

        new_match_traversals.append(new_traversal)

    return _translate_equivalent_locations(
        match_query._replace(match_traversals=new_match_traversals), location_translations)


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

    _flatten_location_translations(location_translations)

    def visitor_fn(expression):
        """Expression visitor function used to rewrite expressions with updated Location data."""
        if not isinstance(expression, (ContextField, ContextFieldExistence)):
            return expression

        old_location = expression.location
        if old_location not in location_translations:
            return expression

        # The Expression could be one of many types, including:
        #   - ContextField
        #   - ContextFieldExistence
        #   - OutputContextField (subclass of ContextField)
        # We determine its exact class to make sure we return an object of the same class
        # as the replacement expression.
        expression_cls = type(expression)
        return expression_cls(location_translations[old_location])

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

    # Rewrite the Locations in the ConstructResult output block.
    new_output_block = match_query.output_block.visit_and_update_expressions(visitor_fn)

    return match_query._replace(match_traversals=new_match_traversals,
                                output_block=new_output_block)


def lower_folded_coerce_types_into_filter_blocks(folded_ir_blocks):
    """Lower CoerceType blocks into "INSTANCEOF" Filter blocks. Indended for folded IR blocks."""
    new_folded_ir_blocks = []
    for block in folded_ir_blocks:
        new_block = block

        if isinstance(block, CoerceType):
            coerce_type_target = block.target_class
            if len(coerce_type_target) != 1:
                raise AssertionError(u'Unexpected "coerce_type_target" for MATCH query: '
                                     u'{}'.format(coerce_type_target))
            coerce_type_target = funcy.first(coerce_type_target)

            # INSTANCEOF requires the target class to be passed in as a string,
            # so we make the target class a string literal.
            new_predicate = BinaryComposition(
                u'INSTANCEOF', LocalField('@this'), Literal(coerce_type_target))

            new_block = Filter(new_predicate)

        new_folded_ir_blocks.append(new_block)

    return new_folded_ir_blocks


def remove_backtrack_blocks_from_fold(folded_ir_blocks):
    """Return a list of IR blocks with all Backtrack blocks removed."""
    new_folded_ir_blocks = []
    for block in folded_ir_blocks:
        if not isinstance(block, Backtrack):
            new_folded_ir_blocks.append(block)
    return new_folded_ir_blocks


def _expression_list_to_conjunction(expression_list):
    """Return an Expression that is the `&&` of all the expressions in the given list."""
    if not isinstance(expression_list, list):
        raise AssertionError(u'Expected list. Received {}: '
                             u'{}'.format(type(expression_list).__name__, expression_list))
    if len(expression_list) == 0:
        raise AssertionError(u'Received empty expression_list '
                             u'(function should never be called with empty list): '
                             u'{}'.format(expression_list))
    elif len(expression_list) == 1:
        return expression_list[0]
    else:
        remaining_conjunction = _expression_list_to_conjunction(expression_list[1:])
        return BinaryComposition(u'&&', expression_list[0], remaining_conjunction)


def _extract_conjuction_elements_from_expression(expression):
    """Return a generator for expressions that are connected by `&&`s in the given expression."""
    if isinstance(expression, BinaryComposition) and expression.operator == u'&&':
        for element in _extract_conjuction_elements_from_expression(expression.left):
            yield element
        for element in _extract_conjuction_elements_from_expression(expression.right):
            yield element
    else:
        yield expression


def _construct_field_operator_expression_dict(expression_list):
    """Construct a mapping from local fields to specified operators, and corresponding expressions.

    Args:
        expression_list: list of expressions to analyze

    Returns:
        local_field_to_expressions:
            dict mapping local field names to "operator -> BinaryComposition" dictionaries,
            for each BinaryComposition operator involving the LocalField
        remaining_expression_list:
            list of remaining expressions that were *not*
            BinaryCompositions on a LocalField using any of the between operators
    """
    between_operators = (u'<=', u'>=')
    inverse_operator = {u'>=': u'<=', u'<=': u'>='}
    local_field_to_expressions = {}
    remaining_expression_list = deque([])
    for expression in expression_list:
        if all((
            isinstance(expression, BinaryComposition),
            expression.operator in between_operators,
            isinstance(expression.left, LocalField) or isinstance(expression.right, LocalField)
        )):
            if isinstance(expression.right, LocalField):
                new_operator = inverse_operator[expression.operator]
                new_expression = BinaryComposition(new_operator, expression.right, expression.left)
            else:
                new_expression = expression
            field_name = new_expression.left.field_name
            expressions_dict = local_field_to_expressions.setdefault(field_name, {})
            expressions_dict.setdefault(new_expression.operator, []).append(new_expression)
        else:
            remaining_expression_list.append(expression)
    return local_field_to_expressions, remaining_expression_list


def _lower_expressions_to_between(base_expression):
    """Return a new expression, with any eligible comparisons lowered to `between` clauses."""
    expression_list = list(_extract_conjuction_elements_from_expression(base_expression))
    if len(expression_list) == 0:
        raise AssertionError(u'Received empty expression_list {} from base_expression: '
                             u'{}'.format(expression_list, base_expression))
    elif len(expression_list) == 1:
        return base_expression
    else:
        between_operators = (u'<=', u'>=')
        local_field_to_expressions, new_expression_list = _construct_field_operator_expression_dict(
            expression_list)

        lowering_occurred = False
        for field_name in local_field_to_expressions:
            expressions_dict = local_field_to_expressions[field_name]
            if all(operator in expressions_dict and len(expressions_dict[operator]) == 1
                   for operator in between_operators):
                field = LocalField(field_name)
                lower_bound = expressions_dict[u'>='][0].right
                upper_bound = expressions_dict[u'<='][0].right
                new_expression_list.appendleft(BetweenClause(field, lower_bound, upper_bound))
                lowering_occurred = True
            else:
                for expression in expressions_dict.values():
                    new_expression_list.append(expression)

        if lowering_occurred:
            return _expression_list_to_conjunction(list(new_expression_list))
        else:
            return base_expression


def lower_comparisons_to_between(match_query):
    """Return a new MatchQuery, with all eligible comparison filters lowered to between clauses."""
    new_match_traversals = []

    for current_match_traversal in match_query.match_traversals:
        new_traversal = []
        for step in current_match_traversal:
            if step.where_block:
                expression = step.where_block.predicate
                new_where_block = Filter(_lower_expressions_to_between(expression))
                new_traversal.append(step._replace(where_block=new_where_block))
            else:
                new_traversal.append(step)

        new_match_traversals.append(new_traversal)

    return match_query._replace(match_traversals=new_match_traversals)


##############
# Public API #
##############

def lower_ir(ir_blocks, location_types, type_equivalence_hints=None):
    """Lower the IR into an IR form that can be represented in MATCH queries.

    Args:
        ir_blocks: list of IR blocks to lower into MATCH-compatible form
        location_types: a dict of location objects -> GraphQL type objects at that location
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        MatchQuery object containing the IR blocks organized in a MATCH-like structure
    """
    sanity_check_ir_blocks_from_frontend(ir_blocks)

    # These lowering / optimization passes work on IR blocks.
    ir_blocks = lower_context_field_existence(ir_blocks)
    ir_blocks = optimize_boolean_expression_comparisons(ir_blocks)
    ir_blocks = rewrite_binary_composition_inside_ternary_conditional(ir_blocks)
    ir_blocks = merge_consecutive_filter_clauses(ir_blocks)
    ir_blocks = lower_has_substring_binary_compositions(ir_blocks)
    ir_blocks = orientdb_eval_scheduling.workaround_lowering_pass(ir_blocks)

    # Here, we lower from raw IR blocks into a MatchQuery object.
    # From this point on, the lowering / optimization passes work on the MatchQuery representation.
    match_query = convert_to_match_query(ir_blocks)

    match_query = lower_comparisons_to_between(match_query)

    match_query = lower_optional_traverse_blocks(match_query, location_types)
    match_query = lower_backtrack_blocks(match_query, location_types)
    match_query = truncate_repeated_single_step_traversals(match_query)
    match_query = orientdb_class_with_while.workaround_type_coercions_in_recursions(match_query)

    # Optimize and lower the IR blocks inside @fold scopes.
    new_folds = {
        key: merge_consecutive_filter_clauses(
            remove_backtrack_blocks_from_fold(
                lower_folded_coerce_types_into_filter_blocks(folded_ir_blocks)
            )
        )
        for key, folded_ir_blocks in six.iteritems(match_query.folds)
    }
    match_query = match_query._replace(folds=new_folds)

    return match_query
