# Copyright 2019-present Kensho Technologies, LLC.
"""Create Cypher query objects from partially-lowered IR blocks, for easier manipulation."""

from collections import namedtuple

from .blocks import (
    Backtrack, CoerceType, ConstructResult, EndOptional, Filter, Fold, GlobalOperationsStart,
    MarkLocation, OutputSource, QueryRoot, Recurse, Traverse, Unfold
)
from .helpers import get_only_element_from_collection
from .ir_lowering_common.common import extract_folds_from_ir_blocks


CypherQuery = namedtuple(
    'CypherQuery',
    ('steps', 'folds', 'global_where_block', 'output_block'))


###
# A CypherStep contains all basic blocks necessary to either create a new component, or attach
# a new part to an existing component of the graph query pattern. It consists of the following:
#   - linked_location: BaseLocation to which the current step is in relation, or None if the current
#                      step stands on its own.
#   - step_block: QueryRoot, Traverse, Recurse, or Fold block representing the new step to be taken
#   - step_types: set of string type names describing the type labels the vertex is required to have
#   - where_block: optional Filter block that specifies any filtering that needs to be applied,
#                  or None if no filtering is required
#   - as_block: BaseLocation containing the name of the query step
CypherStep = namedtuple(
    'CypherStep',
    ('linked_location', 'step_block', 'step_types', 'where_block', 'as_block'))


step_block_types = (Traverse, Recurse)
linked_location_source_types = (MarkLocation, Backtrack)
discarded_block_types = (Unfold, OutputSource, EndOptional)


def _get_all_supertypes_of_exact_type(query_metadata_table, exact_type):
    """Return the set of all supertypes of the given exact type."""
    # TODO(predrag): Plumb the SchemaGraph work through here.
    return {exact_type}


def _make_cypher_step(query_metadata_table, linked_location, current_step_blocks):
    """Return a CypherStep for the current list of IR blocks and metadata."""
    step_block = current_step_blocks[0]
    remaining_blocks = current_step_blocks[1:]

    if isinstance(step_block, QueryRoot):
        return _make_query_root_cypher_step(
            query_metadata_table, linked_location, current_step_blocks)

    remaining_block_types = tuple(type(block) for block in remaining_blocks)
    if remaining_block_types == (CoerceType, Filter, MarkLocation):
        coercion_block, where_block, as_block = remaining_blocks
    elif remaining_block_types == (CoerceType, MarkLocation):
        where_block = None
        coercion_block, as_block = remaining_blocks
    else:
        raise AssertionError(u'Unexpected current_step_blocks received: {}'
                             .format(current_step_blocks))

    exact_step_type = get_only_element_from_collection(coercion_block.target_class)
    step_types = _get_all_supertypes_of_exact_type(query_metadata_table, exact_step_type)

    return CypherStep(
        linked_location=linked_location, step_block=step_block, step_types=step_types,
        where_block=where_block, as_block=as_block)


def _make_query_root_cypher_step(query_metadata_table, linked_location, current_step_blocks):
    """Return a CypherStep for a list of IR blocks that start with a QueryRoot block."""
    current_step_block_types = tuple(type(block) for block in current_step_blocks)

    if current_step_block_types == (QueryRoot, Filter, MarkLocation):
        step_block, where_block, as_block = current_step_blocks
    elif current_step_block_types == (QueryRoot, MarkLocation):
        where_block = None
        step_block, as_block = current_step_blocks
    else:
        raise AssertionError(u'Unexpected current_step_blocks received: {}'
                             .format(current_step_blocks))

    exact_step_type = get_only_element_from_collection(step_block.start_class)
    step_types = _get_all_supertypes_of_exact_type(query_metadata_table, exact_step_type)

    return CypherStep(
        linked_location=linked_location, step_block=step_block, step_types=step_types,
        where_block=where_block, as_block=as_block)


##############
# Public API #
##############

def convert_to_cypher_query(ir_blocks, query_metadata_table, type_equivalence_hints=None):
    """Convert the list of IR blocks into a CypherQuery object, for easier manipulation."""
    steps = []
    current_step_blocks = None
    linked_location = None
    next_linked_location = None

    folds, remaining_ir_blocks = extract_folds_from_ir_blocks(ir_blocks)

    global_operations_index = None

    for current_block_index, block in enumerate(remaining_ir_blocks):
        if isinstance(block, QueryRoot):
            if current_step_blocks is not None:
                raise AssertionError(u'Unexpectedly encountered a QueryRoot block that was not '
                                     u'the first block in the IR: {} {}'
                                     .format(block, remaining_ir_blocks))

            current_step_blocks = [block]
        elif isinstance(block, step_block_types):
            cypher_step = _make_cypher_step(
                query_metadata_table, linked_location, current_step_blocks)
            steps.append(cypher_step)

            linked_location = next_linked_location
            next_linked_location = None

            current_step_blocks = [block]
        elif isinstance(block, GlobalOperationsStart):
            global_operations_index = current_block_index
            break
        elif isinstance(block, linked_location_source_types):
            next_linked_location = block.location
            if isinstance(block, MarkLocation):
                current_step_blocks.append(block)
        elif isinstance(block, discarded_block_types):
            pass
        elif isinstance(block, (Filter, CoerceType)):
            current_step_blocks.append(block)
        else:
            raise AssertionError(u'Unexpected block encountered: {} {}'
                                 .format(block, ir_blocks))

    steps.append(_make_cypher_step(query_metadata_table, linked_location, current_step_blocks))

    if global_operations_index is None:
        raise AssertionError(u'Unexpectedly, no GlobalOperationsStart block was found in '
                             u'the IR blocks: {}'.format(remaining_ir_blocks))

    global_operations_blocks = remaining_ir_blocks[global_operations_index + 1:]
    global_operations_types = tuple(type(block) for block in global_operations_blocks)

    if global_operations_types == (Filter, ConstructResult):
        global_where_block, output_block = global_operations_blocks
    elif global_operations_types == (ConstructResult,):
        global_where_block = None
        output_block = global_operations_blocks[0]
    else:
        raise AssertionError(u'Unexpected global operations blocks in IR: {} {}'
                             .format(global_operations_blocks, ir_blocks))

    return CypherQuery(
        steps=steps, folds=folds, global_where_block=global_where_block, output_block=output_block)
