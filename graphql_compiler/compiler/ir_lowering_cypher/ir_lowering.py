# Copyright 2019-present Kensho Technologies, LLC.
from ..blocks import CoerceType, Filter, Fold, MarkLocation, Traverse

##################################
# Optimization / lowering passes #
##################################

def insert_explicit_type_bounds(ir_blocks, query_metadata_table, type_equivalence_hints=None):
    """Add a CoerceType block after every Traverse and Fold, to hint to the Cypher scheduler."""
    # Cypher might not be aware of the fact that all our edges' endpoints are strictly typed,
    # so we expose the implicit types of edges' endpoints explicitly, by adding CoerceType blocks.
    new_ir_blocks = []

    for current_index, block in enumerate(ir_blocks):
        new_ir_blocks.append(block)

        if isinstance(block, (Traverse, Fold)):
            # We need to add an explicit CoerceType immediately after this block, if one is not
            # already present. If one is present, we do nothing. Since filtering happens before
            # location-marking, if we find a MarkLocation without finding a CoerceType, we know
            # there is no CoerceType here.
            #
            # In that case, we look up that location's type in the query metadata table,
            # and make a new CoerceType block before continuing.
            next_mark_location = None
            next_coerce_type = None
            lookup_index = current_index + 1
            while lookup_index < len(ir_blocks):
                lookup_block = ir_blocks[lookup_index]
                if isinstance(lookup_block, CoerceType):
                    next_coerce_type = lookup_block
                    break
                elif isinstance(lookup_block, MarkLocation):
                    next_mark_location = lookup_block
                    break
                elif isinstance(lookup_block, Filter):
                    # This is expected, step over it.
                    lookup_index += 1
                else:
                    raise AssertionError(u'Expected only CoerceType and Filter blocks to appear '
                                         u'between {} and the corresponding MarkLocation, but '
                                         u'unexpectedly found {}. IR blocks: {}'
                                         .format(block, lookup_block, ir_blocks))

            if next_coerce_type:
                # There's already a type coercion here, nothing needs to be done here.
                pass
            elif new_mark_location:
                location_info = query_metadata_table.get_location_info(new_mark_location.location)
                new_ir_blocks.append(CoerceType({location_info.type.name}))
            else:
                raise AssertionError(u'Illegal IR blocks found. Block {} at index {} does not have '
                                     u'a MarkLocation or CoerceType block after it: {}'
                                     .format(block, current_index, ir_blocks))

    return new_ir_blocks


def remove_mark_location_after_optional_backtrack(ir_blocks, query_metadata_table):
    """Remove location revisits, since they are not required in Cypher."""
    location_translations = make_revisit_location_translations(query_metadata_table)

    for block in ir_blocks:
        pass

    raise NotImplementedError()
