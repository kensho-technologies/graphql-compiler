# Copyright 2018-present Kensho Technologies, LLC.

##############
# Public API #
##############


def lower_ir(ir_blocks, query_metadata_table, type_equivalence_hints=None):
    """Lower the IR into a form that can be represented by a SQL query.

    Args:
        ir_blocks: list of IR blocks to lower into SQL-compatible form
        query_metadata_table: QueryMetadataTable object containing all metadata collected during
                              query processing, including location metadata (e.g. which locations
                              are folded or optional).
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
        tree representation of IR blocks for recursive traversal by SQL backend.
    """
    raise NotImplementedError(u'SQL IR lowering is not yet implemented.')
