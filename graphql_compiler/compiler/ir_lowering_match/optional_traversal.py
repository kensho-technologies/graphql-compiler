# Copyright 2018-present Kensho Technologies, LLC.
from functools import partial

import six

from ..blocks import ConstructResult, Filter, Traverse
from ..expressions import (
    BinaryComposition,
    ContextField,
    FoldedContextField,
    Literal,
    LocalField,
    OutputContextField,
    TernaryConditional,
    TrueLiteral,
    UnaryTransformation,
    Variable,
)
from ..match_query import MatchQuery, MatchStep
from .utils import (
    BetweenClause,
    CompoundMatchQuery,
    construct_optional_traversal_tree,
    expression_list_to_conjunction,
    filter_edge_field_non_existence,
)


def _prune_traverse_using_omitted_locations(
    match_traversal, omitted_locations, complex_optional_roots, location_to_optional_roots
):
    """Return a prefix of the given traverse, excluding any blocks after an omitted optional.

    Given a subset (omitted_locations) of complex_optional_roots, return a new match traversal
    removing all MatchStep objects that are within any omitted location.

    Args:
        match_traversal: list of MatchStep objects to be pruned
        omitted_locations: subset of complex_optional_roots to be omitted
        complex_optional_roots: list of all @optional locations (location immmediately preceding
                                an @optional traverse) that expand vertex fields
        location_to_optional_roots: dict mapping from location -> optional_roots where location is
                                    within some number of @optionals and optional_roots is a list
                                    of optional root locations preceding the successive @optional
                                    scopes within which the location resides

    Returns:
        list of MatchStep objects as a copy of the given match traversal
        with all steps within any omitted location removed.
    """
    new_match_traversal = []
    for step in match_traversal:
        new_step = step
        if isinstance(step.root_block, Traverse) and step.root_block.optional:
            current_location = step.as_block.location
            optional_root_locations_stack = location_to_optional_roots.get(current_location, None)
            optional_root_location = optional_root_locations_stack[-1]

            if optional_root_location is None:
                raise AssertionError(
                    "Found optional Traverse location {} that was not present "
                    "in location_to_optional_roots dict: {}".format(
                        current_location, location_to_optional_roots
                    )
                )
            elif optional_root_location in omitted_locations:
                # Add filter to indicate that the omitted edge(s) shoud not exist
                field_name = step.root_block.get_field_name()

                # HACK(predrag): Plumbing in the type here is tricky and generally not worth it,
                #                since this code needs to be rewritten to resolve a bug related
                #                to edge inheritance. GitHub issue:
                #                https://github.com/kensho-technologies/graphql-compiler/issues/336
                new_predicate = filter_edge_field_non_existence(LocalField(field_name, None))

                old_filter = new_match_traversal[-1].where_block
                if old_filter is not None:
                    new_predicate = BinaryComposition("&&", old_filter.predicate, new_predicate)
                new_match_step = new_match_traversal[-1]._replace(where_block=Filter(new_predicate))
                new_match_traversal[-1] = new_match_step

                # Discard all steps following the omitted @optional traverse
                new_step = None
            elif optional_root_location in complex_optional_roots:
                # Any non-omitted @optional traverse (that expands vertex fields)
                # becomes a normal mandatory traverse (discard the optional flag).
                new_root_block = Traverse(step.root_block.direction, step.root_block.edge_name)
                new_step = step._replace(root_block=new_root_block)
            else:
                # The current optional traverse is a "simple optional" (one that does not
                # expand vertex fields). No further action is required since MATCH supports it.
                pass

        # If new_step was set to None,
        # we have encountered a Traverse that is within an omitted location.
        # We discard the remainder of the match traversal (everything following is also omitted).
        if new_step is None:
            break
        else:
            new_match_traversal.append(new_step)

    return new_match_traversal


def convert_optional_traversals_to_compound_match_query(
    match_query, complex_optional_roots, location_to_optional_roots
):
    """Return 2^n distinct MatchQuery objects in a CompoundMatchQuery.

    Given a MatchQuery containing `n` optional traverses that expand vertex fields,
    construct `2^n` different MatchQuery objects:
    one for each possible subset of optional edges that can be followed.
    For each edge `e` in a subset of optional edges chosen to be omitted,
    discard all traversals following `e`, and add filters specifying that `e` *does not exist*.

    Args:
        match_query: MatchQuery object containing n `@optional` scopes which expand vertex fields
        complex_optional_roots: list of @optional locations (location preceding an @optional
                                traverse) that expand vertex fields within
        location_to_optional_roots: dict mapping from location -> optional_roots where location is
                                    within some number of @optionals and optional_roots is a list
                                    of optional root locations preceding the successive @optional
                                    scopes within which the location resides

    Returns:
        CompoundMatchQuery object containing 2^n MatchQuery objects,
        one for each possible subset of the n optional edges being followed
    """
    tree = construct_optional_traversal_tree(complex_optional_roots, location_to_optional_roots)
    rooted_optional_root_location_subsets = tree.get_all_rooted_subtrees_as_lists()

    omitted_location_subsets = [
        set(complex_optional_roots) - set(subset)
        for subset in rooted_optional_root_location_subsets
    ]
    sorted_omitted_location_subsets = sorted(omitted_location_subsets)

    compound_match_traversals = []
    for omitted_locations in reversed(sorted_omitted_location_subsets):
        new_match_traversals = []
        for match_traversal in match_query.match_traversals:
            location = match_traversal[0].as_block.location
            optional_root_locations_stack = location_to_optional_roots.get(location, None)
            if optional_root_locations_stack is not None:
                optional_root_location = optional_root_locations_stack[-1]
            else:
                optional_root_location = None

            if optional_root_location is None or optional_root_location not in omitted_locations:
                new_match_traversal = _prune_traverse_using_omitted_locations(
                    match_traversal,
                    set(omitted_locations),
                    complex_optional_roots,
                    location_to_optional_roots,
                )
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
            where_block=match_query.where_block,
        )
        for match_traversals in compound_match_traversals
    ]

    return CompoundMatchQuery(match_queries=match_queries)


def _get_present_locations(match_traversals):
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
        tuple (present_locations, present_non_optional_locations):
        - present_locations: set of all locations present in the given match traversals
        - present_non_optional_locations: set of all locations present in the match traversals
                                          that are not reached through optional traverses.
                                          Guaranteed to be a subset of present_locations.
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

    if not present_non_optional_locations.issubset(present_locations):
        raise AssertionError(
            "present_non_optional_locations {} was not a subset of "
            "present_locations {}. THis hould never happen.".format(
                present_non_optional_locations, present_locations
            )
        )

    return present_locations, present_non_optional_locations


def prune_non_existent_outputs(compound_match_query):
    """Remove non-existent outputs from each MatchQuery in the given CompoundMatchQuery.

    Each of the 2^n MatchQuery objects (except one) has been pruned to exclude some Traverse blocks,
    For each of these, remove the outputs (that have been implicitly pruned away) from each
    corresponding ConstructResult block.

    Args:
        compound_match_query: CompoundMatchQuery object containing 2^n pruned MatchQuery objects
                              (see convert_optional_traversals_to_compound_match_query)

    Returns:
        CompoundMatchQuery with pruned ConstructResult blocks for each of the 2^n MatchQuery objects
    """
    if len(compound_match_query.match_queries) == 1:
        return compound_match_query
    elif len(compound_match_query.match_queries) == 0:
        raise AssertionError(
            "Received CompoundMatchQuery with an empty list of MatchQuery objects."
        )
    else:
        match_queries = []
        for match_query in compound_match_query.match_queries:
            match_traversals = match_query.match_traversals
            output_block = match_query.output_block

            present_locations_tuple = _get_present_locations(match_traversals)
            present_locations, present_non_optional_locations = present_locations_tuple

            new_output_fields = {}
            for output_name, expression in six.iteritems(output_block.fields):
                if isinstance(expression, OutputContextField):
                    # An OutputContextField as an output Expression indicates that we are not
                    # within an @optional scope. Therefore, the location this output uses must
                    # be in present_locations, and the output is never pruned.
                    location_name, _ = expression.location.get_location_name()
                    if location_name not in present_locations:
                        raise AssertionError(
                            "Non-optional output location {} was not found in "
                            "present_locations: {}".format(expression.location, present_locations)
                        )
                    new_output_fields[output_name] = expression
                elif isinstance(expression, FoldedContextField):
                    # A FoldedContextField as an output Expression indicates that we are not
                    # within an @optional scope. Therefore, the location this output uses must
                    # be in present_locations, and the output is never pruned.
                    base_location = expression.fold_scope_location.base_location
                    location_name, _ = base_location.get_location_name()
                    if location_name not in present_locations:
                        raise AssertionError(
                            "Folded output location {} was found in "
                            "present_locations: {}".format(base_location, present_locations)
                        )
                    new_output_fields[output_name] = expression
                elif isinstance(expression, TernaryConditional):
                    # A TernaryConditional indicates that this output is within some optional scope.
                    # This may be pruned away based on the contents of present_locations.
                    location_name, _ = expression.if_true.location.get_location_name()
                    if location_name in present_locations:
                        if location_name in present_non_optional_locations:
                            new_output_fields[output_name] = expression.if_true
                        else:
                            new_output_fields[output_name] = expression
                else:
                    raise AssertionError(
                        "Invalid expression of type {} in output block: "
                        "{}".format(type(expression).__name__, output_block)
                    )

            match_queries.append(
                MatchQuery(
                    match_traversals=match_traversals,
                    folds=match_query.folds,
                    output_block=ConstructResult(new_output_fields),
                    where_block=match_query.where_block,
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
                location_to_filters.setdefault(current_location, []).append(current_filter)

    return location_to_filters


def _filter_list_to_conjunction_expression(filter_list):
    """Convert a list of filters to an Expression that is the conjunction of all of them."""
    if not isinstance(filter_list, list):
        raise AssertionError("Expected `list`, Received: {}.".format(filter_list))
    if any((not isinstance(filter_block, Filter) for filter_block in filter_list)):
        raise AssertionError("Expected list of Filter objects. Received: {}".format(filter_list))

    expression_list = [filter_block.predicate for filter_block in filter_list]
    return expression_list_to_conjunction(expression_list)


def _apply_filters_to_first_location_occurrence(
    match_traversal, location_to_filters, already_filtered_locations
):
    """Apply all filters for a specific location into its first occurrence in a given traversal.

    For each location in the given match traversal,
    construct a conjunction of all filters applied to that location,
    and apply the resulting Filter to the first instance of the location.

    Args:
        match_traversal: list of MatchStep objects to be lowered
        location_to_filters: dict mapping each location in the MatchQuery which contains
                             the given match traversal to a list of filters applied at that location
        already_filtered_locations: set of locations that have already had their filters applied

    Returns:
        new list of MatchStep objects with all filters for any given location composed into
        a single filter which is applied to the first instance of that location
    """
    new_match_traversal = []
    newly_filtered_locations = set()
    for match_step in match_traversal:
        # Apply all filters for a location to the first occurence of that location
        current_location = match_step.as_block.location

        if current_location in newly_filtered_locations:
            raise AssertionError(
                "The same location {} was encountered twice in a single "
                "match traversal: {}. This should never happen.".format(
                    current_location, match_traversal
                )
            )

        if all(
            (
                current_location in location_to_filters,
                current_location not in already_filtered_locations,
            )
        ):
            where_block = Filter(
                _filter_list_to_conjunction_expression(location_to_filters[current_location])
            )
            # No further filters needed for this location. If the same location is found in
            # another call to this function, no filters will be added.
            newly_filtered_locations.add(current_location)
        else:
            where_block = None

        new_match_step = MatchStep(
            root_block=match_step.root_block,
            coerce_type_block=match_step.coerce_type_block,
            where_block=where_block,
            as_block=match_step.as_block,
        )
        new_match_traversal.append(new_match_step)

    return new_match_traversal, newly_filtered_locations


def collect_filters_to_first_location_occurrence(compound_match_query):
    """Collect all filters for a particular location to the first instance of the location.

    Adding edge field non-exsistence filters in `_prune_traverse_using_omitted_locations` may
    result in filters being applied to locations after their first occurence.
    OrientDB does not resolve this behavior correctly. Therefore, for each MatchQuery,
    we collect all the filters for each location in a list. For each location,
    we make a conjunction of the filter list (`_predicate_list_to_where_block`) and apply
    the new filter to only the first instance of that location.
    All other instances will have no filters (None).

    Args:
        compound_match_query: CompoundMatchQuery object containing 2^n MatchQuery objects

    Returns:
        CompoundMatchQuery with all filters for each location applied to the first instance
        of that location.
    """
    new_match_queries = []
    # Each MatchQuery has a different set of locations, and associated Filters.
    # Hence, each of them is processed independently.
    for match_query in compound_match_query.match_queries:
        # Construct mapping from location -> list of filter predicates applied at that location
        location_to_filters = _construct_location_to_filter_list(match_query)
        already_filtered_locations = set()

        new_match_traversals = []
        for match_traversal in match_query.match_traversals:
            result = _apply_filters_to_first_location_occurrence(
                match_traversal, location_to_filters, already_filtered_locations
            )
            new_match_traversal, newly_filtered_locations = result

            new_match_traversals.append(new_match_traversal)
            already_filtered_locations.update(newly_filtered_locations)

        new_match_queries.append(
            MatchQuery(
                match_traversals=new_match_traversals,
                folds=match_query.folds,
                output_block=match_query.output_block,
                where_block=match_query.where_block,
            )
        )

    return CompoundMatchQuery(match_queries=new_match_queries)


def _update_context_field_binary_composition(present_locations, expression):
    """Lower BinaryCompositions involving non-existent ContextFields to True.

    Args:
        present_locations: set of all locations in the current MatchQuery that have not been pruned
        expression: BinaryComposition with at least one ContextField operand

    Returns:
        TrueLiteral iff either ContextField operand is not in `present_locations`,
        and the original expression otherwise
    """
    if not any(
        (isinstance(expression.left, ContextField), isinstance(expression.right, ContextField))
    ):
        raise AssertionError(
            "Received a BinaryComposition {} without any ContextField "
            "operands. This should never happen.".format(expression)
        )

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
    if any((isinstance(expression.left, ContextField), isinstance(expression.right, ContextField))):
        raise AssertionError(
            "Received a BinaryComposition {} with a ContextField "
            "operand. This should never happen.".format(expression)
        )

    if expression.operator == "||":
        if expression.left == TrueLiteral or expression.right == TrueLiteral:
            return TrueLiteral
        else:
            return expression
    elif expression.operator == "&&":
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
        the if_true expression of the given TernaryConditional, if the predicate is True,
        and the original TernaryConditional otherwise
    """
    if expression.predicate == TrueLiteral:
        return expression.if_true
    else:
        return expression


def _update_context_field_expression(present_locations, expression):
    """Lower Expressions involving non-existent ContextFields to TrueLiteral and simplify result."""
    no_op_blocks = (ContextField, Literal, LocalField, UnaryTransformation, Variable)
    if isinstance(expression, BinaryComposition):
        if isinstance(expression.left, ContextField) or isinstance(expression.right, ContextField):
            return _update_context_field_binary_composition(present_locations, expression)
        else:
            return _simplify_non_context_field_binary_composition(expression)
    elif isinstance(expression, TernaryConditional):
        return _simplify_ternary_conditional(expression)
    elif isinstance(expression, BetweenClause):
        lower_bound = expression.lower_bound
        upper_bound = expression.upper_bound
        if isinstance(lower_bound, ContextField) or isinstance(upper_bound, ContextField):
            raise AssertionError(
                "Found BetweenClause with ContextFields as lower/upper bounds. "
                "This should never happen: {}".format(expression)
            )
        return expression
    elif isinstance(expression, (OutputContextField, FoldedContextField)):
        raise AssertionError(
            "Found unexpected expression of type {}. This should never happen: "
            "{}".format(type(expression).__name__, expression)
        )
    elif isinstance(expression, no_op_blocks):
        return expression

    raise AssertionError(
        "Found unhandled expression of type {}. This should never happen: "
        "{}".format(type(expression).__name__, expression)
    )


def _lower_non_existent_context_field_filters(match_traversals, visitor_fn):
    """Return new match traversals, lowering filters involving non-existent ContextFields.

    Expressions involving non-existent ContextFields are evaluated to TrueLiteral.
    BinaryCompositions, where one of the operands is lowered to a TrueLiteral,
    are lowered appropriately based on the present operator ('||' and '&&' are affected).
    TernaryConditionals, where the predicate is lowered to a TrueLiteral,
    are replaced by their if_true predicate.
    The `visitor_fn` implements these behaviors (see `_update_context_field_expression`).

    Args:
        match_traversals: list of match traversal enitities to be lowered
        visitor_fn: visit_and_update function for lowering expressions in given match traversal

    Returns:
        new list of match_traversals, with all filter expressions lowered
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


def lower_context_field_expressions(compound_match_query):
    """Lower Expressons involving non-existent ContextFields."""
    if len(compound_match_query.match_queries) == 0:
        raise AssertionError(
            "Received CompoundMatchQuery {} with no MatchQuery objects.".format(
                compound_match_query
            )
        )
    elif len(compound_match_query.match_queries) == 1:
        # All ContextFields exist if there is only one MatchQuery
        # becuase none of the traverses were omitted, and all locations exist (are defined).
        return compound_match_query
    else:
        new_match_queries = []
        for match_query in compound_match_query.match_queries:
            match_traversals = match_query.match_traversals
            present_locations, _ = _get_present_locations(match_traversals)
            current_visitor_fn = partial(_update_context_field_expression, present_locations)

            new_match_traversals = _lower_non_existent_context_field_filters(
                match_traversals, current_visitor_fn
            )
            new_match_queries.append(
                MatchQuery(
                    match_traversals=new_match_traversals,
                    folds=match_query.folds,
                    output_block=match_query.output_block,
                    where_block=match_query.where_block,
                )
            )

    return CompoundMatchQuery(match_queries=new_match_queries)
