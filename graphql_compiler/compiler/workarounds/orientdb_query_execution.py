# Copyright 2018-present Kensho Technologies, LLC.
"""Workarounds for OrientDB scheduler issue that causes poor query planning for certain queries.

For purposes of query planning, the OrientDB query planner ignores "where:" clauses
that hit indexes but do not use the "=" operator. For example, "CONTAINS" can be used to check
that a field covered by an index is in a specified list of values, and can therefore be covered
by an index, but OrientDB will ignore this. When no equality ("=") checks on indexed columns
are present, OrientDB will generate a query plan that starts execution at the class with
lowest cardinality, which can lead to excessive numbers of scanned and discarded records.

Assuming the query planner creates a query plan where a location with CONTAINS is
the first in the execution order, the execution system will apply indexes
to speed up this operation. Therefore, it's sufficient to trick the query planner into
always creating such a query plan, even though it thinks indexes cannot be used in the query.

Valid query execution start points for the OrientDB query planner must satisfy the following:
    - Must not be "optional: true".
    - Must not have a "while:" clause nor follow a location that has one.
    - Must have a "class:" defined. This class is used for cardinality estimation, and to
      look for available indexes that may cover any "where:" clause that may be present.

The optimizations in this file improve performance by enabling execution start points according
to the following assumptions:
    1. Start points with "where:" clauses that reference only local fields (i.e. not tagged values
       from other query locations) are always better than start points without a "where:".
       This is because the filter will have to be applied one way or the other, so we might as well
       apply it early.
    2. If no such start points are available, we'd like to make available as many start points
       as possible, since we'd like OrientDB to start at the start point whose class has
       the lowest possible cardinality.

The process of applying the optimizations is as follows:
    - Exclude and ignore all query steps that are inside a fold, optional, or recursion scope,
      or have a "where:" clause that references a non-local (i.e. tagged) field.
    - Find all remaining query steps with "where:" clauses that reference only local fields.
    - If any are found, we guide our actions from assumption 1 above:
        - Ensure they have a defined "class:" -- i.e. the OrientDB scheduler will consider them
          valid start points.
        - Then, prune all other query steps (ones without such "where:" clauses) by removing their
          "class:" clause, making them invalid as query start points for OrientDB's scheduler.
    - If none are found, we guide our actions from assumption 2 above:
        - Ensure that all query points not inside fold, optional, or recursion scope contain
          a "class:" clause. That increases the number of available query start points,
          so OrientDB can choose the start point of lowest cardinality.
"""

from ..blocks import CoerceType, QueryRoot, Recurse, Traverse
from ..expressions import ContextField, ContextFieldExistence
from ..helpers import get_only_element_from_collection
from ..ir_lowering_match.utils import convert_coerce_type_and_add_to_where_block


def _is_local_filter(filter_block):
    """Return True if the Filter block references no non-local fields, and False otherwise."""
    # We need the "result" value of this function to be mutated within the "visitor_fn".
    # Since we support both Python 2 and Python 3, we can't use the "nonlocal" keyword here:
    # https://www.python.org/dev/peps/pep-3104/
    # Instead, we use a dict to store the value we need mutated, since the "visitor_fn"
    # can mutate state in the parent scope, but not rebind variables in it without "nonlocal".
    # TODO(predrag): Revisit this if we drop support for Python 2.
    result = {
        'is_local_filter': True
    }
    filter_predicate = filter_block.predicate

    def visitor_fn(expression):
        """Expression visitor function that looks for uses of non-local fields."""
        non_local_expression_types = (ContextField, ContextFieldExistence)

        if isinstance(expression, non_local_expression_types):
            result['is_local_filter'] = False

        # Don't change the expression.
        return expression

    filter_predicate.visit_and_update(visitor_fn)

    return result['is_local_filter']


def _classify_query_locations(match_query):
    """Classify query locations into three groups: preferred, eligible, ineligible.

    - Ineligible locations are ones that cannot be the starting point of query execution.
      These include locations within recursions, locations that are the target of
      an optional traversal, and locations with an associated "where:" clause with non-local filter.
    - Preferred locations are ones that are eligible to be the starting point, and also have
      an associated "where:" clause that references no non-local fields -- only local fields,
      literals, and variables.
    - Eligible locations are all locations that do not fall into either of these two categories.

    Args:
        match_query: MatchQuery object describing the query being analyzed for optimization

    Returns:
        tuple (preferred, eligible, ineligible) where each element is a set of Location objects.
        The three sets are disjoint.
    """
    preferred_locations = set()
    eligible_locations = set()
    ineligible_locations = set()

    # Any query must have at least one traversal with at least one step.
    # The first step in this traversal must be a QueryRoot.
    first_match_step = match_query.match_traversals[0][0]
    if not isinstance(first_match_step.root_block, QueryRoot):
        raise AssertionError(u'First step of first traversal unexpectedly was not QueryRoot: '
                             u'{} {}'.format(first_match_step, match_query))

    # The first step in the first traversal cannot possibly be inside an optional, recursion,
    # or fold. Its location is always an eligible start location for a query.
    # We need to determine whether it is merely eligible, or actually a preferred location.
    if first_match_step.where_block is not None:
        if _is_local_filter(first_match_step.where_block):
            preferred_locations.add(first_match_step.as_block.location)
        else:
            # TODO(predrag): Fix once we have a proper fix for tag-and-filter in the same scope.
            #                Either the locally-scoped tag will have to generate a LocalField
            #                instead of a ContextField, or we'll have to rework the local filter
            #                detection code in this module.
            raise AssertionError(u'The first step of the first traversal somehow had a non-local '
                                 u'filter. This should not be possible, since there is nowhere '
                                 u'for the tagged value to have come from. Values: {} {}'
                                 .format(first_match_step, match_query))
    else:
        eligible_locations.add(first_match_step.as_block.location)

    # This loop will repeat the analysis of the first step of the first traversal.
    # QueryRoots other than the first are required to always be at a location whose status
    # (preferred / eligible / ineligible) is already known. Since we already processed
    # the first QueryRoot above, the rest of the loop can assume all QueryRoots are like that.
    for current_traversal in match_query.match_traversals:
        for match_step in current_traversal:
            current_step_location = match_step.as_block.location

            if isinstance(match_step.root_block, QueryRoot):
                already_encountered_location = any((
                    current_step_location in preferred_locations,
                    current_step_location in eligible_locations,
                    current_step_location in ineligible_locations,
                ))

                if not already_encountered_location:
                    raise AssertionError(u'Unexpectedly encountered a location in QueryRoot whose '
                                         u'status has not been determined: {} {} {}'
                                         .format(current_step_location, match_step, match_query))

                at_eligible_or_preferred_location = (
                    current_step_location in preferred_locations or
                    current_step_location in eligible_locations)

                # This location has already been encountered and processed.
                # Other than setting the "at_eligible_or_preferred_location" state for the sake of
                # the following MATCH steps, there is nothing further to be done.
                continue
            elif isinstance(match_step.root_block, Recurse):
                # All Recurse blocks cause locations within to be ineligible.
                at_eligible_or_preferred_location = False
            elif isinstance(match_step.root_block, Traverse):
                # Optional Traverse blocks cause locations within to be ineligible.
                # Non-optional Traverse blocks do not change the eligibility of locations within:
                # if the pre-Traverse location was eligible, so will the location within,
                # and if it was not eligible, neither will the location within.
                if match_step.root_block.optional:
                    at_eligible_or_preferred_location = False
            else:
                raise AssertionError(u'Unreachable condition reached: {} {} {}'
                                     .format(match_step.root_block, match_step, match_query))

            if not at_eligible_or_preferred_location:
                ineligible_locations.add(current_step_location)
            elif match_step.where_block is not None:
                if _is_local_filter(match_step.where_block):
                    # This location has a local filter, and is not otherwise ineligible (it's not
                    # in a recursion etc.). Therefore, it's a preferred query start location.
                    preferred_locations.add(current_step_location)
                else:
                    # Locations with non-local filters are never eligible locations, since they
                    # depend on another location being executed before them.
                    ineligible_locations.add(current_step_location)
            else:
                # No local filtering (i.e. not preferred), but also not ineligible. Eligible it is.
                eligible_locations.add(current_step_location)

    return preferred_locations, eligible_locations, ineligible_locations


def _calculate_type_bound_at_step(match_step):
    """Return the GraphQL type bound at the given step, or None if no bound is given."""
    current_type_bounds = []

    if isinstance(match_step.root_block, QueryRoot):
        # The QueryRoot start class is a type bound.
        current_type_bounds.extend(match_step.root_block.start_class)

    if match_step.coerce_type_block is not None:
        # The CoerceType target class is also a type bound.
        current_type_bounds.extend(match_step.coerce_type_block.target_class)

    if current_type_bounds:
        # A type bound exists. Assert that there is exactly one bound, defined in precisely one way.
        return get_only_element_from_collection(current_type_bounds)
    else:
        # No type bound exists at this MATCH step.
        return None


def _assert_type_bounds_are_not_conflicting(current_type_bound, previous_type_bound,
                                            location, match_query):
    """Ensure that the two bounds either are an exact match, or one of them is None."""
    if all((current_type_bound is not None,
            previous_type_bound is not None,
            current_type_bound != previous_type_bound)):
        raise AssertionError(
            u'Conflicting type bounds calculated at location {}: {} vs {} '
            u'for query {}'.format(location, previous_type_bound, current_type_bound, match_query))


def _expose_only_preferred_locations(match_query, location_types, coerced_locations,
                                     preferred_locations, eligible_locations):
    """Return a MATCH query where only preferred locations are valid as query start locations."""
    preferred_location_types = dict()
    eligible_location_types = dict()

    new_match_traversals = []
    for current_traversal in match_query.match_traversals:
        new_traversal = []
        for match_step in current_traversal:
            new_step = match_step
            current_step_location = match_step.as_block.location

            if current_step_location in preferred_locations:
                # This location is preferred. We have to make sure that at least one occurrence
                # of this location in the MATCH query has an associated "class:" clause,
                # which would be generated by a type bound at the corresponding MATCH step.
                current_type_bound = _calculate_type_bound_at_step(match_step)
                previous_type_bound = preferred_location_types.get(current_step_location, None)

                if previous_type_bound is not None:
                    # The location is already valid. If so, make sure that this step either does
                    # not have any type bounds (e.g. via QueryRoot or CoerceType blocks),
                    # or has type bounds that match the previously-decided type bound.
                    _assert_type_bounds_are_not_conflicting(
                        current_type_bound, previous_type_bound, current_step_location, match_query)
                else:
                    # The location is not yet known to be valid. If it does not have
                    # a type bound in this MATCH step, add a type coercion to the type
                    # registered in "location_types".
                    if current_type_bound is None:
                        current_type_bound = location_types[current_step_location].name
                        new_step = match_step._replace(
                            coerce_type_block=CoerceType({current_type_bound}))

                    preferred_location_types[current_step_location] = current_type_bound
            elif current_step_location in eligible_locations:
                # This location is eligible, but not preferred. We have not make sure
                # none of the MATCH steps with this location have type bounds, and therefore
                # will not produce a corresponding "class:" clause in the resulting MATCH query.
                current_type_bound = _calculate_type_bound_at_step(match_step)
                previous_type_bound = eligible_location_types.get(current_step_location, None)
                if current_type_bound is not None:
                    # There is a type bound here that we need to neutralize.
                    _assert_type_bounds_are_not_conflicting(
                        current_type_bound, previous_type_bound, current_step_location, match_query)

                    # Record the deduced type bound, so that if we encounter this location again,
                    # we ensure that we again infer the same type bound.
                    eligible_location_types[current_step_location] = current_type_bound

                    if (current_step_location not in coerced_locations or
                            previous_type_bound is not None):
                        # The type bound here is already implied by the GraphQL query structure,
                        # or has already been applied at a previous occurrence of this location.
                        # We can simply delete the QueryRoot / CoerceType blocks that impart it.
                        if isinstance(match_step.root_block, QueryRoot):
                            new_root_block = None
                        else:
                            new_root_block = match_step.root_block

                        new_step = match_step._replace(
                            root_block=new_root_block, coerce_type_block=None)
                    else:
                        # The type bound here is not already implied by the GraphQL query structure.
                        # This should only be possible via a CoerceType block. Lower this CoerceType
                        # block into a Filter with INSTANCEOF to ensure the resulting query has the
                        # same semantics, while making the location invalid as a query start point.
                        if (isinstance(match_step.root_block, QueryRoot) or
                                match_step.coerce_type_block is None):
                            raise AssertionError(u'Unexpected MATCH step applying a type bound not '
                                                 u'already implied by the GraphQL query structure: '
                                                 u'{} {}'.format(match_step, match_query))

                        new_where_block = convert_coerce_type_and_add_to_where_block(
                            match_step.coerce_type_block, match_step.where_block)
                        new_step = match_step._replace(
                            coerce_type_block=None, where_block=new_where_block)
                else:
                    # There is no type bound that OrientDB can find defined at this location.
                    # No action is necessary.
                    pass
            else:
                # This location is neither preferred nor eligible.
                # No action is necessary at this location.
                pass

            new_traversal.append(new_step)
        new_match_traversals.append(new_traversal)
    return match_query._replace(match_traversals=new_match_traversals)


def _expose_all_eligible_locations(match_query, location_types, eligible_locations):
    """Return a MATCH query where all eligible locations are valid as query start locations."""
    eligible_location_types = dict()

    new_match_traversals = []
    for current_traversal in match_query.match_traversals:
        new_traversal = []
        for match_step in current_traversal:
            new_step = match_step
            current_step_location = match_step.as_block.location

            if current_step_location in eligible_locations:
                # This location is eligible. We need to make sure it has an associated type bound,
                # so that it produces a "class:" clause that will make it a valid query start
                # location. It either already has such a type bound, or we can use the type
                # implied by the GraphQL query structure to add one.
                current_type_bound = _calculate_type_bound_at_step(match_step)
                previous_type_bound = eligible_location_types.get(current_step_location, None)
                if current_type_bound is None:
                    current_type_bound = location_types[current_step_location].name
                    new_coerce_type_block = CoerceType({current_type_bound})
                    new_step = match_step._replace(coerce_type_block=new_coerce_type_block)
                else:
                    # There is a type bound here. We simply ensure that the bound is not conflicting
                    # with any other type bound at a different MATCH step with the same location.
                    _assert_type_bounds_are_not_conflicting(
                        current_type_bound, previous_type_bound, current_step_location, match_query)

                # Record the deduced type bound, so that if we encounter this location again,
                # we ensure that we again infer the same type bound.
                eligible_location_types[current_step_location] = current_type_bound
            else:
                # This function may only be called if there are no preferred locations. Since this
                # location cannot be preferred, and is not eligible, it must be ineligible.
                # No action is necessary in this case.
                pass

            new_traversal.append(new_step)
        new_match_traversals.append(new_traversal)
    return match_query._replace(match_traversals=new_match_traversals)


def expose_ideal_query_execution_start_points(compound_match_query, location_types,
                                              coerced_locations):
    """Ensure that OrientDB only considers desirable query start points in query planning."""
    new_queries = []

    for match_query in compound_match_query.match_queries:
        location_classification = _classify_query_locations(match_query)
        preferred_locations, eligible_locations, _ = location_classification

        if preferred_locations:
            # Convert all eligible locations into non-eligible ones, by removing
            # their "class:" clause. The "class:" clause is provided either by having
            # a QueryRoot block or a CoerceType block in the MatchStep corresponding
            # to the location. We remove it by converting the class check into
            # an "INSTANCEOF" Filter block, which OrientDB is unable to optimize away.
            new_query = _expose_only_preferred_locations(
                match_query, location_types, coerced_locations,
                preferred_locations, eligible_locations)
        elif eligible_locations:
            # Make sure that all eligible locations have a "class:" clause by adding
            # a CoerceType block that is a no-op as guaranteed by the schema. This merely
            # ensures that OrientDB is able to use each of these locations as a query start point,
            # and will choose the one whose class is of lowest cardinality.
            new_query = _expose_all_eligible_locations(
                match_query, location_types, eligible_locations)
        else:
            raise AssertionError(u'This query has no preferred or eligible query start locations. '
                                 u'This is almost certainly a bug: {}'.format(match_query))

        new_queries.append(new_query)

    return compound_match_query._replace(match_queries=new_queries)
