# Copyright 2017-present Kensho Technologies, LLC.
"""Functions that ensure the IR generated by the front-end satisfies all invariants."""

from funcy.py2 import pairwise

from .blocks import (
    Backtrack,
    CoerceType,
    ConstructResult,
    Filter,
    Fold,
    MarkLocation,
    OutputSource,
    QueryRoot,
    Recurse,
    Traverse,
    Unfold,
)
from .ir_lowering_common.common import extract_folds_from_ir_blocks


def sanity_check_ir_blocks_from_frontend(ir_blocks, query_metadata_table):
    """Assert that IR blocks originating from the frontend do not have nonsensical structure.

    Args:
        ir_blocks: list of BasicBlocks representing the IR to sanity-check
        query_metadata_table: QueryMetadataTable object that captures information about the query

    Raises:
        AssertionError, if the IR has unexpected structure. If the IR produced by the front-end
        cannot be successfully and correctly used to generate MATCH or Gremlin due to a bug,
        this is the method that should catch the problem.
    """
    if not ir_blocks:
        raise AssertionError(u"Received no ir_blocks: {}".format(ir_blocks))

    _sanity_check_fold_scope_locations_are_unique(ir_blocks)
    _sanity_check_no_nested_folds(ir_blocks)
    _sanity_check_query_root_block(ir_blocks)
    _sanity_check_output_source_follower_blocks(ir_blocks)
    _sanity_check_block_pairwise_constraints(ir_blocks)
    _sanity_check_mark_location_preceding_optional_traverse(ir_blocks)
    _sanity_check_every_location_is_marked(ir_blocks)
    _sanity_check_coerce_type_outside_of_fold(ir_blocks)
    _sanity_check_all_marked_locations_are_registered(ir_blocks, query_metadata_table)
    _sanity_check_registered_locations_parent_locations(query_metadata_table)


def _sanity_check_registered_locations_parent_locations(query_metadata_table):
    """Assert that all registered locations' parent locations are also registered."""
    for location, location_info in query_metadata_table.registered_locations:
        if (
            location != query_metadata_table.root_location
            and not query_metadata_table.root_location.is_revisited_at(location)
        ):
            # If the location is not the root location and is not a revisit of the root,
            # then it must have a parent location.
            if location_info.parent_location is None:
                raise AssertionError(
                    u"Found a location that is not the root location of the query "
                    u"or a revisit of the root, but does not have a parent: "
                    u"{} {}".format(location, location_info)
                )

        if location_info.parent_location is not None:
            # Make sure the parent_location is also registered.
            # If the location is not registered, the following line will raise an error.
            query_metadata_table.get_location_info(location_info.parent_location)


def _sanity_check_all_marked_locations_are_registered(ir_blocks, query_metadata_table):
    """Assert that all locations in MarkLocation blocks have registered and valid metadata."""
    # Grab all the registered locations, then make sure that:
    # - Any location that appears in a MarkLocation block is also registered.
    # - There are no registered locations that do not appear in a MarkLocation block.
    registered_locations = {location for location, _ in query_metadata_table.registered_locations}

    ir_encountered_locations = {
        block.location for block in ir_blocks if isinstance(block, MarkLocation)
    }

    unregistered_locations = ir_encountered_locations - registered_locations
    unencountered_locations = registered_locations - ir_encountered_locations
    if unregistered_locations:
        raise AssertionError(
            u"IR blocks unexpectedly contain locations not registered in the "
            u"QueryMetadataTable: {}".format(unregistered_locations)
        )
    if unencountered_locations:
        raise AssertionError(
            u"QueryMetadataTable unexpectedly contains registered locations that "
            u"never appear in the IR blocks: {}".format(unencountered_locations)
        )


def _sanity_check_fold_scope_locations_are_unique(ir_blocks):
    """Assert that every FoldScopeLocation that exists on a Fold block is unique."""
    observed_locations = dict()
    for block in ir_blocks:
        if isinstance(block, Fold):
            alternate = observed_locations.get(block.fold_scope_location, None)
            if alternate is not None:
                raise AssertionError(
                    u"Found two Fold blocks with identical FoldScopeLocations: "
                    u"{} {} {}".format(alternate, block, ir_blocks)
                )
            observed_locations[block.fold_scope_location] = block


def _sanity_check_no_nested_folds(ir_blocks):
    """Assert that there are no nested Fold contexts, and that every Fold has a matching Unfold."""
    fold_seen = False
    for block in ir_blocks:
        if isinstance(block, Fold):
            if fold_seen:
                raise AssertionError(u"Found a nested Fold contexts: {}".format(ir_blocks))
            else:
                fold_seen = True
        elif isinstance(block, Unfold):
            if not fold_seen:
                raise AssertionError(
                    u"Found an Unfold block without a matching Fold: " u"{}".format(ir_blocks)
                )
            else:
                fold_seen = False


def _sanity_check_query_root_block(ir_blocks):
    """Assert that QueryRoot is always the first block, and only the first block."""
    if not isinstance(ir_blocks[0], QueryRoot):
        raise AssertionError(u"The first block was not QueryRoot: {}".format(ir_blocks))
    for block in ir_blocks[1:]:
        if isinstance(block, QueryRoot):
            raise AssertionError(u"Found QueryRoot after the first block: {}".format(ir_blocks))


def _sanity_check_construct_result_block(ir_blocks):
    """Assert that ConstructResult is always the last block, and only the last block."""
    if not isinstance(ir_blocks[-1], ConstructResult):
        raise AssertionError(u"The last block was not ConstructResult: {}".format(ir_blocks))
    for block in ir_blocks[:-1]:
        if isinstance(block, ConstructResult):
            raise AssertionError(
                u"Found ConstructResult before the last block: " u"{}".format(ir_blocks)
            )


def _sanity_check_output_source_follower_blocks(ir_blocks):
    """Ensure there are no Traverse / Backtrack / Recurse blocks after an OutputSource block."""
    seen_output_source = False
    for block in ir_blocks:
        if isinstance(block, OutputSource):
            seen_output_source = True
        elif seen_output_source:
            if isinstance(block, (Backtrack, Traverse, Recurse)):
                raise AssertionError(
                    u"Found Backtrack / Traverse / Recurse "
                    u"after OutputSource block: "
                    u"{}".format(ir_blocks)
                )


def _sanity_check_block_pairwise_constraints(ir_blocks):
    """Assert that adjacent blocks obey all invariants."""
    for first_block, second_block in pairwise(ir_blocks):
        # Always Filter before MarkLocation, never after.
        if isinstance(first_block, MarkLocation) and isinstance(second_block, Filter):
            raise AssertionError(u"Found Filter after MarkLocation block: {}".format(ir_blocks))

        # There's no point in marking the same location twice in a row.
        if isinstance(first_block, MarkLocation) and isinstance(second_block, MarkLocation):
            raise AssertionError(u"Found consecutive MarkLocation blocks: {}".format(ir_blocks))

        # Traverse blocks with optional=True are immediately followed
        # by a MarkLocation, CoerceType or Filter block.
        if isinstance(first_block, Traverse) and first_block.optional:
            if not isinstance(second_block, (MarkLocation, CoerceType, Filter)):
                raise AssertionError(
                    u"Expected MarkLocation, CoerceType or Filter after Traverse "
                    u"with optional=True. Found: {}".format(ir_blocks)
                )

        # Backtrack blocks with optional=True are immediately followed by a MarkLocation block.
        if isinstance(first_block, Backtrack) and first_block.optional:
            if not isinstance(second_block, MarkLocation):
                raise AssertionError(
                    u"Expected MarkLocation after Backtrack with optional=True, "
                    u"but none was found: {}".format(ir_blocks)
                )

        # Recurse blocks are immediately preceded by a MarkLocation or Backtrack block.
        if isinstance(second_block, Recurse):
            if not (isinstance(first_block, MarkLocation) or isinstance(first_block, Backtrack)):
                raise AssertionError(
                    u"Expected MarkLocation or Backtrack before Recurse, but none "
                    u"was found: {}".format(ir_blocks)
                )


def _sanity_check_mark_location_preceding_optional_traverse(ir_blocks):
    """Assert that optional Traverse blocks are preceded by a MarkLocation."""
    # Once all fold blocks are removed, each optional Traverse must have
    # a MarkLocation block immediately before it.
    _, new_ir_blocks = extract_folds_from_ir_blocks(ir_blocks)
    for first_block, second_block in pairwise(new_ir_blocks):
        # Traverse blocks with optional=True are immediately preceded by a MarkLocation block.
        if isinstance(second_block, Traverse) and second_block.optional:
            if not isinstance(first_block, MarkLocation):
                raise AssertionError(
                    u"Expected MarkLocation before Traverse with optional=True, "
                    u"but none was found: {}".format(ir_blocks)
                )


def _sanity_check_every_location_is_marked(ir_blocks):
    """Ensure that every new location is marked with a MarkLocation block."""
    # Exactly one MarkLocation block is found between any block that starts an interval of blocks
    # that all affect the same query position, and the first subsequent block that affects a
    # different position in the query. Such intervals include the following examples:
    # - from Fold to Unfold
    # - from QueryRoot to Traverse/Recurse
    # - from one Traverse to the next Traverse
    # - from Traverse to Backtrack
    found_start_block = False
    mark_location_blocks_count = 0

    start_interval_types = (QueryRoot, Traverse, Recurse, Fold)
    end_interval_types = (Backtrack, ConstructResult, Recurse, Traverse, Unfold)

    for block in ir_blocks:
        # Terminate started intervals before opening new ones.
        if isinstance(block, end_interval_types) and found_start_block:
            found_start_block = False
            if mark_location_blocks_count != 1:
                raise AssertionError(
                    u"Expected 1 MarkLocation block between traversals, found: "
                    u"{} {}".format(mark_location_blocks_count, ir_blocks)
                )

        # Now consider opening new intervals or processing MarkLocation blocks.
        if isinstance(block, MarkLocation):
            mark_location_blocks_count += 1
        elif isinstance(block, start_interval_types):
            found_start_block = True
            mark_location_blocks_count = 0


def _sanity_check_coerce_type_outside_of_fold(ir_blocks):
    """Ensure that CoerceType not in a @fold are followed by a MarkLocation or Filter block."""
    is_in_fold = False
    for first_block, second_block in pairwise(ir_blocks):
        if isinstance(first_block, Fold):
            is_in_fold = True

        if not is_in_fold and isinstance(first_block, CoerceType):
            if not isinstance(second_block, (MarkLocation, Filter)):
                raise AssertionError(
                    u"Expected MarkLocation or Filter after CoerceType, "
                    u"but none was found: {}".format(ir_blocks)
                )

        if isinstance(second_block, Unfold):
            is_in_fold = False
