##############
# Public API #
##############
from graphql_compiler.compiler.helpers import Location
from graphql_compiler.compiler.ir_lowering_sql.sql_blocks import SqlBlocks
from graphql_compiler.compiler.ir_lowering_sql.sql_tree import SqlNode
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
    state_manager = QueryStateManager(location_types)
    location_to_node = {}
    tree_root = None
    for block in ir_blocks:
        sql_blocks = SqlBlockLowering.lower_block(block, state_manager)
        for block in sql_blocks:
            if isinstance(block, SqlBlocks.Relation):
                if tree_root is None:
                    tree_root = SqlNode(parent_node=None, relation=block)
                    location_to_node[block.location] = tree_root
                elif block.location not in location_to_node:
                    prev_location = Location(block.location.query_path[:-1])
                    parent_node = location_to_node[prev_location]
                    child_node = SqlNode(parent_node=parent_node, relation=block)
                    parent_node.add_child_node(child_node)
                    location_to_node[block.location] = child_node
                else:
                    raise AssertionError('Relations should never share a location')
            elif isinstance(block, SqlBlocks.Selection):
                node = location_to_node[block.location]
                node.add_selection(block)
            elif isinstance(block, SqlBlocks.Predicate):
                node = location_to_node[block.location]
                if block.is_tag:
                    block.tag_node = location_to_node[block.tag_location]
                node.add_predicate(block)
    return tree_root
