# Copyright 2018-present Kensho Technologies, LLC.
from .ir_lowering import (lower_coerce_type_block_type_data, lower_coerce_type_blocks,
                          lower_folded_outputs, rewrite_filters_in_optional_blocks)
from ..ir_sanity_checks import sanity_check_ir_blocks_from_frontend
from ..ir_lowering_common import (lower_context_field_existence, merge_consecutive_filter_clauses,
                                  optimize_boolean_expression_comparisons)


##############
# Public API #
##############

def lower_ir(ir_blocks, location_types, coerced_locations, type_equivalence_hints=None):
    """Lower the IR into an IR form that can be represented in Gremlin queries.

    Args:
        ir_blocks: list of IR blocks to lower into Gremlin-compatible form
        location_types: dict of location objects -> GraphQL type objects at that location
        coerced_locations: set of locations where type coercions were applied to constrain the type
                           relative to the type inferred by the GraphQL schema and the given field
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        list of IR blocks suitable for outputting as Gremlin
    """
    sanity_check_ir_blocks_from_frontend(ir_blocks)

    ir_blocks = lower_context_field_existence(ir_blocks)
    ir_blocks = optimize_boolean_expression_comparisons(ir_blocks)

    if type_equivalence_hints:
        ir_blocks = lower_coerce_type_block_type_data(ir_blocks, type_equivalence_hints)

    ir_blocks = lower_coerce_type_blocks(ir_blocks)
    ir_blocks = rewrite_filters_in_optional_blocks(ir_blocks)
    ir_blocks = merge_consecutive_filter_clauses(ir_blocks)
    ir_blocks = lower_folded_outputs(ir_blocks)

    return ir_blocks
