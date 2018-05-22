# Copyright 2017-present Kensho Technologies, LLC.
"""Workaround for OrientDB query scheduling issue with eval() statements.

OrientDB <2.2.17 (and perhaps future versions as well) fail to pick up $matched
query dependencies if those dependencies are only used within an eval() statement.
The workaround pulls out all such dependencies out of the eval() statement in a way
that doesn't introduce incorrect output, but ensures correct scheduling of the query.
More details: https://github.com/orientechnologies/orientdb/issues/7160

This workaround doesn't work in OrientDB <2.2.17 due to another bug.
The workaround should fix the problem starting with OrientDB 2.2.18.
"""
from ..blocks import Filter
from ..expressions import (BinaryComposition, ContextField, ContextFieldExistence, NullLiteral,
                           TernaryConditional)


def workaround_lowering_pass(ir_blocks):
    """Extract locations from TernaryConditionals and rewrite their Filter blocks as necessary."""
    new_ir_blocks = []

    for block in ir_blocks:
        if isinstance(block, Filter):
            new_block = _process_filter_block(block)
        else:
            new_block = block
        new_ir_blocks.append(new_block)

    return new_ir_blocks


def _process_filter_block(block):
    """Rewrite the provided Filter block if necessary."""
    # For a given Filter block with BinaryComposition predicate expression X,
    # let L be the set of all Locations referenced in any TernaryConditional
    # predicate expression enclosed in X.
    # For each location l in L, we construct a tautological expression that looks like:
    #     ((l IS NULL) OR (l IS NOT NULL))
    # and then join the original BinaryComposition X with all such expressions with ANDs.
    # We set this new BinaryComposition expression as the predicate of the Filter block.
    base_predicate = block.predicate

    # These variables are used by the visitor functions below.
    ternary_conditionals = []
    # "problematic_locations" is a list and not a set,
    # to preserve ordering and generate a deterministic order of added clauses.
    # We expect the maximum size of this list to be a small constant number,
    # so the linear "in" operator is really not a concern.
    problematic_locations = []

    def find_ternary_conditionals(expression):
        """Visitor function that extracts all enclosed TernaryConditional expressions."""
        if isinstance(expression, TernaryConditional):
            ternary_conditionals.append(expression)
        return expression

    def extract_locations_visitor(expression):
        """Visitor function that extracts all the problematic locations."""
        if isinstance(expression, (ContextField, ContextFieldExistence)):
            # We get the location at the vertex, ignoring property fields.
            # The vertex-level location is sufficient to work around the OrientDB bug,
            # and we want as few location as possible overall.
            location_at_vertex = expression.location.at_vertex()
            if location_at_vertex not in problematic_locations:
                problematic_locations.append(location_at_vertex)

        return expression

    # We aren't modifying the base predicate itself, just traversing it.
    # The returned "updated" value must be the exact same as the original.
    return_value = base_predicate.visit_and_update(find_ternary_conditionals)
    if return_value is not base_predicate:
        raise AssertionError(u'Read-only visitor function "find_ternary_conditionals" '
                             u'caused state to change: '
                             u'{} {}'.format(base_predicate, return_value))

    for ternary in ternary_conditionals:
        # We aren't modifying the ternary itself, just traversing it.
        # The returned "updated" value must be the exact same as the original.
        return_value = ternary.visit_and_update(extract_locations_visitor)
        if return_value is not ternary:
            raise AssertionError(u'Read-only visitor function "extract_locations_visitor" '
                                 u'caused state to change: '
                                 u'{} {}'.format(ternary, return_value))

    tautologies = [
        _create_tautological_expression_for_location(location)
        for location in problematic_locations
    ]

    if not tautologies:
        return block

    final_predicate = base_predicate
    for tautology in tautologies:
        final_predicate = BinaryComposition(u'&&', final_predicate, tautology)
    return Filter(final_predicate)


def _create_tautological_expression_for_location(location):
    """For a given location, create a BinaryComposition that always evaluates to 'true'."""
    location_exists = BinaryComposition(u'!=', ContextField(location), NullLiteral)
    location_does_not_exist = BinaryComposition(u'=', ContextField(location), NullLiteral)
    return BinaryComposition(u'||', location_exists, location_does_not_exist)
