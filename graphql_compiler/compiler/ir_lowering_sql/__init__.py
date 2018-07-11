##############
# Public API #
##############
from .ir_lowering import SqlBlockLowering
from .query_state_manager import QueryStateManager


def lower_ir(ir_blocks, location_types, type_equivalence_hints=None):
    """Lower the IR into an IR form that can be represented in MATCH queries.

    Args:
        ir_blocks: list of IR blocks to lower into MATCH-compatible form
        location_types: a dict of location objects -> GraphQL type objects at that location
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
        MatchQuery object containing the IR blocks organized in a MATCH-like structure
    """
    sql_query_blocks = []
    state_manager = QueryStateManager(location_types)
    for block in ir_blocks:

        sql_query_blocks.extend(
            SqlBlockLowering.lower_block(block, state_manager)
        )
    return sql_query_blocks
