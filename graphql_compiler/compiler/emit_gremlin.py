# Copyright 2017-present Kensho Technologies, LLC.
"""Convert lowered IR basic blocks to Gremlin query strings."""


##############
# Public API #
##############


def emit_code_from_ir(schema_info, ir_blocks):
    """Return a MATCH query string from a list of IR blocks."""
    gremlin_steps = (block.to_gremlin() for block in ir_blocks)

    # OutputSource blocks translate to empty steps.
    # Discard such empty steps so we don't end up with an incorrect concatenation.
    non_empty_steps = (step for step in gremlin_steps if step)

    return ".".join(non_empty_steps)
