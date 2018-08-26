##############
# Public API #
##############
import six

from graphql_compiler.compiler import blocks, expressions
from graphql_compiler.compiler.helpers import Location
from graphql_compiler.compiler.ir_lowering_sql.sql_blocks import SqlBlocks
from graphql_compiler.compiler.ir_lowering_sql.sql_tree import SqlNode
from .ir_lowering import SqlBlockLowering
from .query_state_manager import QueryStateManager


def lower_ir(ir_blocks, query_metadata_table, type_equivalence_hints=None):
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
    location_types = {
        location.query_path: location_info.type
        for location, location_info in query_metadata_table.registered_locations
    }
    block_index_to_location = get_block_index_to_location_map(ir_blocks)
    construct_result = ir_blocks.pop()
    state_manager = QueryStateManager(location_types)
    query_path_to_node = {}
    tree_root = None
    for index, block in enumerate(ir_blocks):
        # todo we can skip queryroot and construct result, which simplifies this
        if index in block_index_to_location:
            location = block_index_to_location[index]
            query_path = location.query_path
        sql_blocks = SqlBlockLowering.lower_block(block, state_manager)
        for block in sql_blocks:
            if isinstance(block, (blocks.Recurse, blocks.Traverse, blocks.QueryRoot)):
                if tree_root is None:
                    location_info = query_metadata_table.get_location_info(location)
                    tree_root = SqlNode(
                        parent_node=None, block=block, location_info=location_info,
                        parent_location_info=None, query_path=query_path)
                    query_path_to_node[query_path] = tree_root
                elif query_path not in query_path_to_node:
                    location_info = query_metadata_table.get_location_info(location)
                    parent_location = location_info.parent_location
                    parent_query_path = parent_location.query_path
                    parent_location_info = query_metadata_table.get_location_info(parent_location)
                    parent_node = query_path_to_node[parent_query_path]
                    child_node = SqlNode(
                        parent_node=parent_node, block=block, location_info=location_info,
                        parent_location_info=parent_location_info, query_path=query_path)
                    parent_node.add_child_node(child_node)
                    query_path_to_node[query_path] = child_node
                else:
                    raise AssertionError('Relations should never share a location')
            elif isinstance(block, SqlBlocks.Predicate):
                node = query_path_to_node[query_path]
                if block.is_tag:
                    block.tag_node = query_path_to_node[block.tag_location]
                node.add_predicate(block)
    assign_output_fields_to_nodes(construct_result, location_types, query_path_to_node)
    return tree_root


def assign_output_fields_to_nodes(construct_result, location_types, query_path_to_node):
    for field_alias, field in six.iteritems(construct_result.fields):
        if isinstance(field, expressions.TernaryConditional):
            # todo: This probably isn't the way to go in the general case
            field = field.if_true
        output_query_path = field.location.query_path
        node = query_path_to_node[output_query_path]
        node.fields[field_alias] = (field, location_types[output_query_path])


def get_block_index_to_location_map(ir_blocks):
    block_to_location = {}
    current_block_ixs = []
    for num, ir_block in enumerate(ir_blocks):
        current_block_ixs.append(num)
        if isinstance(ir_block, blocks.MarkLocation):
            for ix in current_block_ixs:
                block_to_location[ix] = ir_block.location
            current_block_ixs = []
    return block_to_location
