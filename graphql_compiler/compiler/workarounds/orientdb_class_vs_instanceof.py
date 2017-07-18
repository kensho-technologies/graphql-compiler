# Copyright 2017 Kensho Technologies, Inc.
"""Workarounds for OrientDB operator inconsistencies between "class:" and "where: with INSTANCEOF.

For details, see:
https://github.com/orientechnologies/orientdb/issues/7225
"""
import funcy

from ..blocks import Filter, Recurse, Traverse
from ..expressions import BinaryComposition, Literal, LocalField


def _coerce_block_to_filter_block(coerce_type_block, where_block):
    """Create an "INSTANCEOF" Filter block from a CoerceType block."""
    coerce_type_target = coerce_type_block.target_class
    if len(coerce_type_target) != 1:
        raise AssertionError(u'Unexpected "coerce_type_target" for MATCH query: '
                             u'{}'.format(coerce_type_target))
    coerce_type_target = funcy.first(coerce_type_target)

    # INSTANCEOF requires the target class to be passed in as a string,
    # so we make the target class a string literal.
    new_predicate = BinaryComposition(
        u'INSTANCEOF', LocalField('@this'), Literal(coerce_type_target))

    if where_block:
        # There was already a Filter block -- we'll merge the two predicates together.
        new_predicate = BinaryComposition(u'&&', new_predicate, where_block.predicate)

    return Filter(new_predicate)


def lower_type_coercions(match_query):
    """Lower CoerceType blocks into Filter blocks within Recurse or optional Traverse steps."""
    # This step is required to satisfy the semantics of the @recurse decorator -- that filtering
    # does not affect the recursion depth, and instead simply omits outputs that don't match.
    # We can't use the regular "class:" clause since in MATCH, it limits the recursion depth.
    # Similarly, it is required to satisfy the semantics of the @optional decorator -- where
    # vertex non-existence is reported as a "null" value, rather than suppressing the entire output
    # as using "class:" would do in this case.
    #
    # These bugs are reported upstream: https://github.com/orientechnologies/orientdb/issues/7225
    #
    # Instead of "class:", we use "INSTANCEOF" in the "where:" clause to get correct behavior.
    # However, we don't want to switch all coercions to this format, since the "class:" clause
    # provides valuable info to the MATCH query scheduler about how to schedule efficiently.
    new_match_traversals = []

    for current_traversal in match_query.match_traversals:
        new_traversal = []

        for match_step in current_traversal:
            new_match_step = match_step

            has_coerce_type = match_step.coerce_type_block is not None
            has_recurse_root = isinstance(match_step.root_block, Recurse)
            has_optional_traverse_root = (
                isinstance(match_step.root_block, Traverse) and match_step.root_block.optional)

            if has_coerce_type and (has_recurse_root or has_optional_traverse_root):
                new_where_block = _coerce_block_to_filter_block(
                    match_step.coerce_type_block, match_step.where_block)
                new_match_step = match_step._replace(coerce_type_block=None,
                                                     where_block=new_where_block)

            new_traversal.append(new_match_step)

        new_match_traversals.append(new_traversal)

    return match_query._replace(match_traversals=new_match_traversals)
