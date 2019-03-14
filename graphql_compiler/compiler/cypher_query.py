# Copyright 2019-present Kensho Technologies, LLC.
"""Create Cypher query objects from partially-lowered IR blocks, for easier manipulation."""

from collections import namedtuple

from .blocks import (
    Backtrack, CoerceType, ConstructResult, Filter, Fold, GlobalOperationsStart, MarkLocation,
    OutputSource, QueryRoot, Recurse, Traverse, Unfold
)

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


step_block_types = (QueryRoot, Traverse, Recurse, Fold)
linked_location_source_types = (MarkLocation, Backtrack)
discarded_block_types = (Unfold, OutputSource)


##############
# Public API #
##############

def convert_to_cypher_query(ir_blocks, query_metadata_table, type_equivalence_hints=None):
    """Convert the list of IR blocks into a CypherQuery object, for easier manipulation."""
    steps = []
    current_step_blocks = None
    linked_location = None

    global_operations_index = None

    for current_block_index, block in enumerate(ir_blocks):
        if isinstance(block, step_block_types):
            if current_step_blocks is not None:
                cypher_step = _make_cypher_step(
                    query_metadata_table, linked_location, current_step_blocks)
                steps.append(cypher_step)

            current_step_blocks = [block]
        elif isinstance(block, GlobalOperationsStart):
            global_operations_index = current_block_index
            break
        elif isinstance(block, linked_location_source_types):
            linked_location = block.location
        elif isinstance(block, discarded_block_types):
            pass
        elif isinstance(block, (Filter, CoerceType)):
            current_step_blocks.append(block)
        else:
            raise AssertionError(u'Unexpected block encountered: {} {}'
                                 .format(block, ir_blocks))

    global_operations_blocks = ir_blocks[global_operations_index + 1:]
