# Copyright 2017 Kensho Technologies, LLC.
"""Perform optimizations and lowering of the IR that allows the compiler to emit MATCH queries.

The compiler IR allows blocks and expressions that cannot be directly compiled to Gremlin or MATCH.
For example, ContextFieldExistence is an Expression that returns True iff its given vertex exists,
but the produced Gremlin and MATCH outputs for this purpose are entirely different and not easy
to generate directly from this Expression object. An output-language-aware IR lowering step allows
us to convert this Expression into other Expressions, using data already present in the IR,
to simplify the final code generation step.
"""

from collections import deque, namedtuple
import itertools

import funcy.py2 as funcy
import six

from .blocks import (Backtrack, CoerceType, ConstructResult, Filter, MarkLocation, QueryRoot,
                     Traverse)
from .expressions import (BinaryComposition, ContextField, ContextFieldExistence, Expression,
                          FalseLiteral, FoldedOutputContextField, Literal, LocalField, NullLiteral,
                          OutputContextField, TernaryConditional, TrueLiteral, UnaryTransformation,
                          Variable, ZeroLiteral)
from .ir_lowering_common import (extract_location_to_optional_from_ir_blocks,
                                 lower_context_field_existence, merge_consecutive_filter_clauses,
                                 optimize_boolean_expression_comparisons, remove_end_optionals)
from .ir_sanity_checks import sanity_check_ir_blocks_from_frontend
from .match_query import MatchQuery, MatchStep, convert_to_match_query
from .workarounds import orientdb_class_with_while, orientdb_eval_scheduling


###
# A CompoundMatchQuery is a representation of several MatchQuery objects containing
#   - match_queries: a list MatchQuery objects
CompoundMatchQuery = namedtuple('CompoundMatchQuery', ('match_queries'))


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


###
# A CompoundMatchQuery is a representation of several MatchQuery objects containing
#   - match_queries: a list MatchQuery objects
CompoundMatchQuery = namedtuple('CompoundMatchQuery', ('match_queries'))


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
            if isinstance(step.root_block, Backtrack) and step.root_block.optional:
                # 1. Upon seeing a step with an optional Backtrack root block,
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


def _filter_local_edge_field_non_existence(field_name):
    """Return an Expression that is True iff the specified edge (field_name) does not exist."""
    # When an edge does not exist at a given vertex, OrientDB represents that in one of two ways:
    #   - the edge's field does not exist (is null) on the vertex document, or
    #   - the edge's field does exist, but is an empty list.
    # We check both of these possibilities.
    local_field = LocalField(field_name)

    field_null_check = BinaryComposition(u'=', local_field, NullLiteral)

    local_field_size = UnaryTransformation(u'size', local_field)
    field_size_check = BinaryComposition(u'=', local_field_size, ZeroLiteral)

    return BinaryComposition(u'||', field_null_check, field_size_check)


def _prune_traverse_using_omitted_locations(match_traversal, omitted_locations, optional_locations,
                                            location_to_optional):
    """Return a prefix of the given traverse, excluding any blocks after an omitted optional.

    Given a subset (omitted_locations) of optional_locations, return a new match traversal
    removing all MatchStep objects that are within any omitted location.

    Args:
        match_traversal: list of MatchStep objects to be pruned
        omitted_locations: subset of optional_locations to be omitted
        optional_locations: list of all @optional locations (location immmediately preceding
            an @optional traverse) that expand vertex fields
        location_to_optional: dict mapping location -> optional_location
            where location is within @optional (not necessarily one that expands vertex fields),
            and optional_location is the location preceding the associated @optional scope

    Returns:
    list of MatchStep objects as a copy of the given match traversal
        with all steps within any omitted location removed.
    """
    new_match_traversal = []
    for step in match_traversal:
        new_step = step
        if isinstance(step.root_block, Traverse) and step.root_block.optional:
            current_location = step.as_block.location
            in_optional_location = location_to_optional.get(current_location, None)

            if in_optional_location is None:
                continue
            elif in_optional_location in omitted_locations:
                # Add filter to indicate that the omitted edge(s) shoud not exist
                field_name = step.root_block.get_field_name()
                new_predicate = _filter_local_edge_field_non_existence(field_name)
                old_filter = new_match_traversal[-1].where_block
                if old_filter is not None:
                    new_predicate = BinaryComposition(u'&&', old_filter.predicate, new_predicate)
                new_match_step = new_match_traversal[-1]._replace(
                    where_block=Filter(new_predicate))
                new_match_traversal[-1] = new_match_step

                # Discard all steps following the omitted @optional traverse
                new_step = None
            elif in_optional_location in optional_locations:
                # Any non-omitted @optional traverse (that expands vertex fields)
                # becomes a normal mandatory traverse (discard the optional flag).
                new_root_block = Traverse(step.root_block.direction, step.root_block.edge_name)
                new_step = step._replace(root_block=new_root_block)

        # If new_step was set to None,
        # we have encountered a Traverse that is within an omitted location.
        # We discard the remainder of the match traversal (everything following is also omitted).
        if new_step is None:
            break
        else:
            new_match_traversal.append(new_step)

    return new_match_traversal


def convert_optional_traversals_to_compound_match_query(
        match_query, optional_locations, location_to_optional):
    """Return 2^n distinct MatchQuery objects in a CompoundMatchQuery.

    Given a MatchQuery containing `n` optional traverses that expand vertex fields,
    construct `2^n` different MatchQuery objects:
    one for each possible subset of optional edges that can be followed.
    For each edge `e` in a subset of optional edges chosen to be omitted,
    discard all traversals following `e`, and add filters specifying that `e` *does not exist*.

    Args:
        match_query: MatchQuery object containing n `@optional` scopes which expand vertex fields
        optional_locations: list of @optional locations (location preceding an @optional traverse)
            that expand vertex fields within
        location_to_optional: dict mapping all locations within optional scopes
            to the corresponding optional location

    Returns:
        CompoundMatchQuery object containing 2^n MatchQuery objects,
        one for each possible subset of the n optional edges being followed
    """
    optional_location_combinations_list = [
        itertools.combinations(optional_locations, x)
        for x in range(0, len(optional_locations) + 1)
    ]
    optional_location_subsets = list(itertools.chain(*optional_location_combinations_list))

    compound_match_traversals = []
    for omitted_locations in reversed(optional_location_subsets):
        new_match_traversals = []
        for match_traversal in match_query.match_traversals:
            location = match_traversal[0].as_block.location
            location_in_dict = location in location_to_optional

            if not location_in_dict or location_to_optional[location] not in omitted_locations:
                new_match_traversal = _prune_traverse_using_omitted_locations(
                    match_traversal, set(omitted_locations),
                    optional_locations, location_to_optional)
                new_match_traversals.append(new_match_traversal)
            else:
                # The root_block is within an omitted scope.
                # Discard the entire match traversal (do not append to new_match_traversals)
                pass

        compound_match_traversals.append(new_match_traversals)

    match_queries = [
        MatchQuery(
            match_traversals=match_traversals,
            folds=match_query.folds,
            output_block=match_query.output_block,
        )
        for match_traversals in compound_match_traversals
    ]

    return CompoundMatchQuery(match_queries=match_queries)


def _get_present_locations_from_match_traversals(match_traversals):
    """Return the set of locations and non-optional locations present in the given match traversals.

    When enumerating the possibilities for optional traversals,
    the resulting match traversals may have sections of the query omitted.
    These locations will not be included in the returned `present_locations`.
    All of the above locations that are not optional traverse locations
    will be included in present_non_optional_locations.

    Args:
        match_traversals: one possible list of match traversals generated from a query
            containing @optional traversal(s)

    Returns:
        present_locations: set of all locations present in the given match traversals
        present_non_optiona_locations: set of all locations present in the given match traversals
            that are not reached through optional traverses.
    """
    present_locations = set()
    present_non_optional_locations = set()

    for match_traversal in match_traversals:
        for step in match_traversal:
            if step.as_block is not None:
                location_name, _ = step.as_block.location.get_location_name()
                present_locations.add(location_name)
                if isinstance(step.root_block, Traverse) and not step.root_block.optional:
                    present_non_optional_locations.add(location_name)

    return present_locations, present_non_optional_locations


def prune_output_blocks_in_compound_match_query(compound_match_query):
    """Remove non-existent outputs from each MatchQuery in the given CompoundMatchQuery."""
    if len(compound_match_query.match_queries) == 1:
        return compound_match_query
    elif len(compound_match_query.match_queries) == 0:
        raise AssertionError(u'Received CompoundMatchQuery with '
                             u'an empty list of MatchQuery objects.')
    else:
        match_queries = []
        for match_query in compound_match_query.match_queries:
            match_traversals = match_query.match_traversals
            output_block = match_query.output_block
            folds = match_query.folds

            present_locations_tuple = _get_present_locations_from_match_traversals(match_traversals)
            present_locations, present_non_optional_locations = present_locations_tuple

            new_output_fields = {}
            for output_name, expression in six.iteritems(output_block.fields):
                if isinstance(expression, OutputContextField):
                    location_name, _ = expression.location.get_location_name()
                    if location_name not in present_locations:
                        raise AssertionError(u'Non-optional output location {} was not found in '
                                             u'present_locations: {}'
                                             .format(expression.location, present_locations))
                    new_output_fields[output_name] = expression
                elif isinstance(expression, FoldedOutputContextField):
                    base_location = expression.fold_scope_location.base_location
                    location_name, _ = base_location.get_location_name()
                    if location_name not in present_locations:
                        raise AssertionError(u'Non-optional output location {} was not found in '
                                             u'present_locations: {}'
                                             .format(expression.location, present_locations))
                    new_output_fields[output_name] = expression
                elif isinstance(expression, TernaryConditional):
                    location_name, _ = expression.if_true.location.get_location_name()
                    if location_name in present_locations:
                        if location_name in present_non_optional_locations:
                            new_output_fields[output_name] = expression.if_true
                        else:
                            new_output_fields[output_name] = expression
                else:
                    raise AssertionError(u'Invalid expression of type {} in output block: '
                                         u'{}'.format(type(expression).__name__, output_block))

            match_queries.append(
                MatchQuery(
                    match_traversals=match_traversals,
                    folds=folds,
                    output_block=ConstructResult(new_output_fields)
                )
            )

        return CompoundMatchQuery(match_queries=match_queries)


def _construct_location_to_filter_list(match_query):
    """Return a dict mapping location -> list of filters applied at that location.

    Args:
        match_query: MatchQuery object from which to extract location -> filters dict

    Returns:
        dict mapping each location in match_query to a list of
            Filter objects applied at that location
    """
    # For each location, all filters for that location should be applied at the first instance.
    # This function collects a list of all filters corresponding to each location
    # present in the given MatchQuery.
    location_to_filters = {}
    for match_traversal in match_query.match_traversals:
        for match_step in match_traversal:
            current_filter = match_step.where_block
            if current_filter is not None:
                current_location = match_step.as_block.location
                location_to_filters.setdefault(current_location, []).append(
                    current_filter)

    return location_to_filters


def _filter_list_to_conjunction_expression(filter_list):
    """Convert a list of filters to an Expression that is the conjunction of all of them."""
    if not isinstance(filter_list, list):
        raise AssertionError(u'Expected `list`, Received {}.'.format(filter_list))

    if not isinstance(filter_list[0], Filter):
        raise AssertionError(u'Non-Filter object {} found in filter_list'
                             .format(filter_list[0]))

    if len(filter_list) == 1:
        return filter_list[0].predicate
    else:
        return BinaryComposition(u'&&',
                                 _filter_list_to_conjunction_expression(filter_list[1:]),
                                 filter_list[0].predicate)


def _collect_filters_to_first_location_in_match_traversal(match_traversal, location_to_filters):
    """Compose all filters for a specific location into its first occurence in given traversal.

    For each location in the given match traversal,
    construct a conjunction of all filters applied to that location,
    and apply the resulting Filter to the first instance of the location.

    Args:
        match_traversal: list of MatchStep objects to be lowered
        location_to_filters: dict mapping each location in the MatchQuery which contains
            the given match traversal to a list of filters applied at that location

    Returns:
        new list of MatchStep objects with all filters for any given location composed into
        a single filter which is applied to the first instance of that location
    """
    new_match_traversal = []
    for match_step in match_traversal:
        # Apply all filters for a location to the first occurence of that location
        if match_step.as_block.location in location_to_filters:
            where_block = Filter(
                _filter_list_to_conjunction_expression(
                    location_to_filters[match_step.as_block.location]
                )
            )
            # Delete the location entry. No further filters needed for this location.
            # If the same location is found in another call to this function,
            # no filters will be added.
            del location_to_filters[match_step.as_block.location]
        else:
            where_block = None
        new_match_step = MatchStep(
            root_block=match_step.root_block,
            coerce_type_block=match_step.coerce_type_block,
            where_block=where_block,
            as_block=match_step.as_block
        )
        new_match_traversal.append(new_match_step)
    return new_match_traversal


def collect_filters_to_first_location_instance(compound_match_query):
    """Collect all filters for a particular location to the first instance of the location."""
    # Adding edge field non-exsistence filters in `_prune_traverse_using_omitted_locations`
    # may result in filters being applied to locations after their first occurence.
    # OrientDB does not resolve this behavior correctly.
    # Therefore, for each MatchQuery, we collect all the filters for each location in a list.
    # For each location, we make a conjunction of the filter list (`_predicate_list_to_where_block`)
    # and apply the new filter to only the first instance of that location.
    # All other instances will have no filters (None).
    new_match_queries = []
    # Each MatchQuery has a different set of locations, and associated Filters.
    # Hence, each of them is processed independently.
    for match_query in compound_match_query.match_queries:
        # Construct mapping from location -> list of filter predicates applied at that location
        location_to_predicates = _construct_location_to_filter_list(match_query)

        new_match_traversals = []
        for match_traversal in match_query.match_traversals:
            new_match_traversal = _collect_filters_to_first_location_in_match_traversal(
                match_traversal, location_to_predicates)
            new_match_traversals.append(new_match_traversal)

        new_match_queries.append(
            MatchQuery(
                match_traversals=new_match_traversals,
                folds=match_query.folds,
                output_block=match_query.output_block
            )
        )

    return CompoundMatchQuery(match_queries=new_match_queries)


def _update_context_field_binary_composition(expression, present_locations):
    """Lower BinaryCompositions involving non-existent ContextFields to True.

    Args:
        expression: BinaryComposition with at least one ContextField operand

    Returns:
        TrueLiteral iff either ContextField operand is not in `present_locations`,
        and the original expression otherwise
    """
    if isinstance(expression.left, ContextField):
        context_field = expression.left
        location_name, _ = context_field.location.get_location_name()
        if location_name not in present_locations:
            return TrueLiteral

    if isinstance(expression.right, ContextField):
        context_field = expression.right
        location_name, _ = context_field.location.get_location_name()
        if location_name not in present_locations:
            return TrueLiteral

    return expression


def _simplify_non_context_field_binary_composition(expression):
    """Return a simplified BinaryComposition if either operand is a TrueLiteral.

    Args:
        expression: BinaryComposition without any ContextField operand(s)

    Returns:
        simplified expression if the given expression is a disjunction/conjunction
        and one of it's operands is a TrueLiteral,
        and the original expression otherwise
    """
    if expression.operator == u'||':
        if expression.left == TrueLiteral or expression.right == TrueLiteral:
            return TrueLiteral
        else:
            return expression
    elif expression.operator == u'&&':
        if expression.left == TrueLiteral:
            return expression.right
        if expression.right == TrueLiteral:
            return expression.left
        else:
            return expression
    else:
        return expression


def _simplify_ternary_conditional(expression):
    """Return the `if_true` clause if the predicate of the TernaryConditional is a TrueLiteral.

    Args:
        expression: TernaryConditional to be simplified.

    Returns:
        simplified TernaryConditional, if the predicate is True,
        and the original expression otherwise
    """
    if expression.predicate == TrueLiteral:
        return expression.if_true
    else:
        return expression


def _update_context_field_expression(expression, present_locations):
    """Lower Expressions involving non-existent ContextFields True, and simplify result."""
    no_op_blocks = (ContextField, Literal, LocalField, UnaryTransformation, Variable)
    if isinstance(expression, BinaryComposition):
        if isinstance(expression.left, ContextField) or isinstance(expression.right, ContextField):
            return _update_context_field_binary_composition(expression, present_locations)
        else:
            return _simplify_non_context_field_binary_composition(expression)
    elif isinstance(expression, TernaryConditional):
        return _simplify_ternary_conditional(expression)
    elif isinstance(expression, BetweenClause):
        lower_bound = expression.lower_bound
        upper_bound = expression.upper_bound
        if isinstance(lower_bound, ContextField) or isinstance(upper_bound, ContextField):
            raise AssertionError(u'Found BetweenClause with ContextFields as lower/upper bounds. '
                                 u'This should never happen: {}'.format(expression))
    elif isinstance(expression, (OutputContextField, FoldedOutputContextField)):
        raise AssertionError(u'Found unexpected expression of type {}. This should never happen: '
                             u'{}'.format(type(expression).__name__, expression))
    elif isinstance(expression, no_op_blocks):
        return expression
    else:
        raise AssertionError(u'Found unexpected expression of type {}. This should never happen: '
                             u'{}'.format(type(expression).__name__, expression))


def _construct_update_context_field_visitor_fn(present_locations):
    """Return an Expression updater using the given `present_locations`."""
    def visitor_fn(expression):
        return _update_context_field_expression(expression, present_locations)
    return visitor_fn


def _lower_filters_in_match_traversals(match_traversals, visitor_fn):
    """Return new match traversals, lowering filters involving non-existent ContextFields.

    Expressions involving non-existent ContextFields are evaluated to True.
    BinaryCompositions, where one of the operands is lowered to a TrueLiteral,
    are lowered appropriately based on the present operator (u'||' and u'&&' are affected).
    TernaryConditionals, where the predicate is lowerd to a TrueLiteral,
    are replaced by their if_true predicate.
    The `visitor_fn` implements these behaviors (see `_update_context_field_expression`).

    Args:
        match_traversals: list of match traversal enities to be lowered
        visitor_fn: visit_and_update function for lowering expressions in given match traversal

    Returns:
        new_match_traversals: new list of match_traversals, with all filter expressions lowered
    """
    new_match_traversals = []
    for match_traversal in match_traversals:
        new_match_traversal = []
        for step in match_traversal:
            if step.where_block is not None:
                new_filter = step.where_block.visit_and_update_expressions(visitor_fn)
                if new_filter.predicate == TrueLiteral:
                    new_filter = None
                new_step = step._replace(where_block=new_filter)
            else:
                new_step = step
            new_match_traversal.append(new_step)
        new_match_traversals.append(new_match_traversal)
    return new_match_traversals


def lower_context_field_expressions_in_compound_match_query(compound_match_query):
    """Lower Expressons involving non-existent ContextFields."""
    if len(compound_match_query.match_queries) == 0:
        raise AssertionError(u'Received CompoundMatchQuery with '
                             u'an empty list of MatchQuery objects.')
    elif len(compound_match_query.match_queries) == 1:
        # All ContextFields exist if there is only one MatchQuery.
        return compound_match_query
    else:
        new_match_queries = []
        for match_query in compound_match_query.match_queries:
            match_traversals = match_query.match_traversals
            present_locations, _ = _get_present_locations_from_match_traversals(match_traversals)
            current_visitor_fn = _construct_update_context_field_visitor_fn(
                present_locations)

            new_match_traversals = _lower_filters_in_match_traversals(
                match_traversals, current_visitor_fn)
            new_match_queries.append(
                MatchQuery(
                    match_traversals=new_match_traversals,
                    folds=match_query.folds,
                    output_block=match_query.output_block
                )
            )

    return CompoundMatchQuery(match_queries=new_match_queries)


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
    location_to_optional_results = extract_location_to_optional_from_ir_blocks(ir_blocks)
    optional_locations, location_to_optional = location_to_optional_results
    ir_blocks = remove_end_optionals(ir_blocks)

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

    compound_match_query = convert_optional_traversals_to_compound_match_query(
        match_query, optional_locations, location_to_optional)
    compound_match_query = prune_output_blocks_in_compound_match_query(
        compound_match_query)
    compound_match_query = collect_filters_to_first_location_instance(compound_match_query)
    compound_match_query = lower_context_field_expressions_in_compound_match_query(
        compound_match_query)

    return compound_match_query
