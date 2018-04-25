# Copyright 2017 Kensho Technologies, LLC.
"""Tools to create MATCH query objects from partially-lowered IR blocks, for easier manipulation."""

from collections import namedtuple

from .blocks import (Backtrack, CoerceType, ConstructResult, Filter, MarkLocation, OutputSource,
                     QueryRoot, Recurse, Traverse)
from .ir_lowering_common import extract_folds_from_ir_blocks


###
# A MatchQuery is a representation of the entire MATCH query formed by all IR blocks in a given
# compilation unit. It consists of two parts:
#   - match_traversals: a list of lists of MatchStep objects, where each list of MatchStep objects
#                       defines a single traversal chain in the MATCH query.
#   - folds: a dict of FoldScopeLocation -> list of IR blocks defining that @fold scope,
#            not including the Fold and Unfold blocks that signal the start and end of the @fold.
#   - output_block: a ConstructResult IR block, which defines how the query's results are returned.
MatchQuery = namedtuple('MatchQuery', ('match_traversals', 'folds', 'output_block'))


###
# A MatchStep contains all basic blocks that correspond to a given location in the query.
# MatchStep boundaries occur when traversing edges, and when constructing the final output
# of the query. Its fields can hold the following types of basic blocks:
#   - root_block: QueryRoot, Traverse, Recurse or Backtrack block, which forms the root of the step
#   - coerce_type_block: a CoerceType block, which acts as a "where_block" on the type of the step
#   - where_block: an optional Filter block that corresponds to the 'where' clause in the MATCH step
#   - as_block: an optional MarkLocation block that corresponds to the 'as' clause in the MATCH step
MatchStep = namedtuple('MatchStep', ('root_block', 'coerce_type_block', 'where_block', 'as_block'))


root_block_types = (QueryRoot, Traverse, Recurse, Backtrack)


def _per_location_tuple_to_step(ir_tuple):
    """Construct a MatchStep from a tuple of its constituent blocks."""
    root_block = ir_tuple[0]
    if not isinstance(root_block, root_block_types):
        raise AssertionError(u'Unexpected root block type for MatchStep: '
                             u'{} {}'.format(root_block, ir_tuple))

    coerce_type_block = None
    where_block = None
    as_block = None
    for block in ir_tuple[1:]:
        if isinstance(block, CoerceType):
            if coerce_type_block is not None:
                raise AssertionError(u'Unexpectedly found two blocks eligible for "class" clause: '
                                     u'{} {} {}'.format(block, coerce_type_block, ir_tuple))
            coerce_type_block = block
        elif isinstance(block, MarkLocation):
            if as_block is not None:
                raise AssertionError(u'Unexpectedly found two blocks eligible for "as" clause: '
                                     u'{} {} {}'.format(block, as_block, ir_tuple))
            as_block = block
        elif isinstance(block, Filter):
            if where_block is not None:
                raise AssertionError(u'Unexpectedly found two blocks eligible for "where" clause: '
                                     u'{} {} {}'.format(block, as_block, ir_tuple))

            # Filter always comes before MarkLocation in a given MatchStep.
            if as_block is not None:
                raise AssertionError(u'Unexpectedly found MarkLocation before Filter in '
                                     u'MatchStep: {} {} {}'.format(block, where_block, ir_tuple))

            where_block = block
        else:
            raise AssertionError(u'Unexpected block encountered: {} {}'.format(block, ir_tuple))

    step = MatchStep(root_block=root_block,
                     coerce_type_block=coerce_type_block,
                     where_block=where_block,
                     as_block=as_block)

    # MatchSteps with Backtrack as the root block should only contain MarkLocation,
    # and not do filtering or type coercion.
    if isinstance(root_block, Backtrack):
        if where_block is not None or coerce_type_block is not None:
            raise AssertionError(u'Unexpected blocks in Backtrack-based MatchStep: {}'.format(step))

    return step


def _split_ir_into_match_steps(ir_blocks):
    """Split a list of IR blocks into per-location MATCH steps.

    Args:
        ir_blocks: list of IR basic block objects that have gone through a lowering step.

    Returns:
        list of MatchStep namedtuples, each of which contains all basic blocks that correspond
        to a single MATCH step.
    """
    output = []
    current_tuple = None
    for block in ir_blocks:
        if isinstance(block, OutputSource):
            # OutputSource blocks do not require any MATCH code, and only serve to help
            # optimizations and debugging. Simply omit them at this stage.
            continue
        elif isinstance(block, root_block_types):
            if current_tuple is not None:
                output.append(current_tuple)
            current_tuple = (block,)
        elif isinstance(block, (CoerceType, Filter, MarkLocation)):
            current_tuple += (block,)
        else:
            raise AssertionError(u'Unexpected block type when converting to MATCH query: '
                                 u'{} {}'.format(block, ir_blocks))

    if current_tuple is None:
        raise AssertionError(u'current_tuple was unexpectedly None: {}'.format(ir_blocks))
    output.append(current_tuple)

    return [_per_location_tuple_to_step(x) for x in output]


def _split_match_steps_into_match_traversals(match_steps):
    """Split a list of MatchSteps into multiple lists, each denoting a single MATCH traversal."""
    output = []
    current_list = None
    for step in match_steps:
        if isinstance(step.root_block, QueryRoot):
            if current_list is not None:
                output.append(current_list)
            current_list = [step]
        else:
            current_list.append(step)

    if current_list is None:
        raise AssertionError(u'current_list was unexpectedly None: {}'.format(match_steps))
    output.append(current_list)

    return output


##############
# Public API #
##############

def convert_to_match_query(ir_blocks):
    """Convert the list of IR blocks into a MatchQuery object, for easier manipulation."""
    output_block = ir_blocks[-1]
    if not isinstance(output_block, ConstructResult):
        raise AssertionError(u'Expected last IR block to be ConstructResult, found: '
                             u'{} {}'.format(output_block, ir_blocks))

    ir_except_output = ir_blocks[:-1]
    folds, ir_except_output_and_folds = extract_folds_from_ir_blocks(ir_except_output)

    match_steps = _split_ir_into_match_steps(ir_except_output_and_folds)

    match_traversals = _split_match_steps_into_match_traversals(match_steps)

    return MatchQuery(match_traversals=match_traversals, folds=folds, output_block=output_block)
