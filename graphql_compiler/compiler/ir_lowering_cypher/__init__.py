# Copyright 2019-present Kensho Technologies, LLC.
from ..ir_sanity_checks import sanity_check_ir_blocks_from_frontend
from ..ir_lowering_common.common import (
    lower_context_field_existence, merge_consecutive_filter_clauses,
    optimize_boolean_expression_comparisons
)
from .ir_lowering import (
    insert_explicit_type_bounds, move_filters_in_optional_locations_to_global_operations,
    remove_mark_location_after_optional_backtrack, replace_local_fields_with_context_fields
)
from ..cypher_query import convert_to_cypher_query


##############
# Public API #
##############

def lower_ir(ir_blocks, query_metadata_table, type_equivalence_hints=None):
    """Lower the IR into an IR form that can be represented in Cypher queries.

    Args:
        ir_blocks: list of IR blocks to lower into Cypher-compatible form
        query_metadata_table: QueryMetadataTable object containing all metadata collected during
                              query processing, including location metadata (e.g. which locations
                              are folded or optional).
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Cypher's total lack of inheritance-awareness.
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
        CypherQuery object
    """
    sanity_check_ir_blocks_from_frontend(ir_blocks, query_metadata_table)

    ir_blocks = insert_explicit_type_bounds(
        ir_blocks, query_metadata_table,
        type_equivalence_hints=type_equivalence_hints)

    ir_blocks = remove_mark_location_after_optional_backtrack(ir_blocks, query_metadata_table)
    ir_blocks = lower_context_field_existence(ir_blocks, query_metadata_table)
    ir_blocks = replace_local_fields_with_context_fields(ir_blocks)
    ir_blocks = optimize_boolean_expression_comparisons(ir_blocks)
    ir_blocks = merge_consecutive_filter_clauses(ir_blocks)

    cypher_query = convert_to_cypher_query(
        ir_blocks, query_metadata_table, type_equivalence_hints=type_equivalence_hints)

    cypher_query = move_filters_in_optional_locations_to_global_operations(
        cypher_query, query_metadata_table)

    return cypher_query
