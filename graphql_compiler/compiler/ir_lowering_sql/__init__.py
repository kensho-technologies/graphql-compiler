# Copyright 2018-present Kensho Technologies, LLC.
import six

from graphql_compiler.compiler import blocks, expressions
from graphql_compiler.compiler.ir_lowering_sql.constants import RESERVED_COLUMN_NAMES
from graphql_compiler.compiler.ir_lowering_sql.sql_tree import SqlNode, SqlQueryTree

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
        SqlTree object containing the SqlNodes organized in a tree structure.
    """
    query_path_to_location_info = {
        location.query_path: location_info
        for location, location_info in query_metadata_table.registered_locations
    }
    block_index_to_location = get_block_index_to_location_map(ir_blocks)
    construct_result = ir_blocks.pop()
    query_path_to_node = {}
    tree_root = None
    for index, block in enumerate(ir_blocks):
        if isinstance(block, (blocks.Recurse, blocks.Traverse, blocks.QueryRoot)):
            location = block_index_to_location[index]
            query_path = location.query_path
            if tree_root is None:
                if not isinstance(block, blocks.QueryRoot):
                    raise AssertionError
                tree_root = SqlNode(block=block, query_path=query_path)
                query_path_to_node[query_path] = tree_root
            else:
                location_info = query_metadata_table.get_location_info(location)
                parent_location = location_info.parent_location
                parent_query_path = parent_location.query_path
                parent_node = query_path_to_node[parent_query_path]
                child_node = SqlNode(block=block, query_path=query_path)
                parent_node.add_child_node(child_node)
                query_path_to_node[query_path] = child_node
        elif isinstance(block, blocks.Filter):
            node = query_path_to_node[query_path]
            node.filters.append((block, query_path, query_path_to_location_info[query_path]))
        else:
            continue
    location_types = {
        location.query_path: location_info.type
        for location, location_info in query_metadata_table.registered_locations
    }
    assign_output_fields_to_nodes(construct_result, location_types, query_path_to_node)
    return SqlQueryTree(tree_root, query_path_to_location_info)


def assign_output_fields_to_nodes(construct_result, location_types, query_path_to_node):
    """Assign the output fields of a ConstructResult block to their respective SqlNodes."""
    for field_alias, field in six.iteritems(construct_result.fields):
        if field_alias in RESERVED_COLUMN_NAMES:
            raise AssertionError
        if isinstance(field, expressions.TernaryConditional):
            # todo: This probably isn't the way to go in the general case
            field = field.if_true
        output_query_path = field.location.query_path
        node = query_path_to_node[output_query_path]
        node.fields[field_alias] = (field, location_types[output_query_path])


def get_block_index_to_location_map(ir_blocks):
    """Associate each IR block with it's corresponding location, by index."""
    block_to_location = {}
    current_block_ixs = []
    for num, ir_block in enumerate(ir_blocks):
        current_block_ixs.append(num)
        if isinstance(ir_block, blocks.MarkLocation):
            for ix in current_block_ixs:
                block_to_location[ix] = ir_block.location
            current_block_ixs = []
    return block_to_location
