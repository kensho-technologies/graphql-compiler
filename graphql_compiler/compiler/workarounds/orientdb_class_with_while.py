# Copyright 2017-present Kensho Technologies, LLC.
"""Workarounds for OrientDB bug disallowing "class:" clauses together with "while:" clauses.

For details, see:
https://github.com/orientechnologies/orientdb/issues/8129
"""
from ..blocks import Recurse
from ..ir_lowering_match.utils import convert_coerce_type_and_add_to_where_block


def workaround_type_coercions_in_recursions(match_query):
    """Lower CoerceType blocks into Filter blocks within Recurse steps."""
    # This step is required to work around an OrientDB bug that causes queries with both
    # "while:" and "class:" in the same query location to fail to parse correctly.
    #
    # This bug is reported upstream: https://github.com/orientechnologies/orientdb/issues/8129
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

            if has_coerce_type and has_recurse_root:
                new_where_block = convert_coerce_type_and_add_to_where_block(
                    match_step.coerce_type_block, match_step.where_block)
                new_match_step = match_step._replace(coerce_type_block=None,
                                                     where_block=new_where_block)

            new_traversal.append(new_match_step)

        new_match_traversals.append(new_traversal)

    return match_query._replace(match_traversals=new_match_traversals)
