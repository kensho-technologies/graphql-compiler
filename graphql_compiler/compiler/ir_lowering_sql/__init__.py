# Copyright 2018-present Kensho Technologies, LLC.

import six

from .constants import UNSUPPORTED_META_FIELDS
from .sql_tree import SqlNode, SqlQueryTree
from .. import blocks
from ..ir_lowering_sql.constants import SqlOutput
from ..metadata import LocationInfo
from ... import exceptions

##############
# Public API #
##############

_SKIPPABLE_BLOCKS = (
    # MarkLocation blocks are used in the first pass over the IR blocks to create a mapping of
    # IR block -> query path for all IR blocks. They can safely be skipped during tree construction.
    blocks.MarkLocation,
)


def lower_ir(ir_blocks, query_metadata_table, type_equivalence_hints=None):
    """Lower the IR into a form that can be represented by a SQL query.

    Args:
        ir_blocks: list of IR blocks to lower into the SQL tree structure.
        query_metadata_table: QueryMetadataTable object containing all metadata collected during
                              query processing, including location metadata (e.g. which locations
                              are folded or optional).
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union. Unused.

    Returns:
        tree representation of IR blocks for recursive traversal by SQL backend.
    """
    construct_result = ir_blocks.pop()
    query_path_to_location_info = _map_query_path_to_location_info(query_metadata_table)
    query_path_to_output_fields = _map_query_path_to_outputs(
        construct_result, query_path_to_location_info)

    # iteratively construct SqlTree
    query_path_to_node = {}
    block_index_to_location = _map_block_index_to_location(ir_blocks)
    tree_root = None
    for index, block in enumerate(ir_blocks):
        location = block_index_to_location[index]
        if isinstance(block, (blocks.QueryRoot,)):
            query_path = location.query_path
            if tree_root is not None:
                raise AssertionError(
                    u'Encountered QueryRoot {} but tree root is already set to {} during '
                    u'construction of SQL query tree for IR blocks {} with query'
                    u' metadata table {}'.format(
                        block, tree_root, ir_blocks, query_metadata_table))
            tree_root = SqlNode(block=block, query_path=query_path)
            query_path_to_node[query_path] = tree_root
        elif isinstance(block, _SKIPPABLE_BLOCKS):
            continue
        else:
            raise exceptions.GraphQLNotSupportedByBackendError(
                u'Encountered unsupported block {} during construction of SQL query tree for IR '
                u'blocks {} with query metadata table {} .'.format(
                    block, ir_blocks, query_metadata_table))

    return SqlQueryTree(tree_root, query_path_to_location_info, query_path_to_output_fields)


def _map_query_path_to_location_info(query_metadata_table):
    """Create a map from a query path to a LocationInfo at that path.

    Verifies that LocationInfos at the same query path are equivalent in type, parent,
    recursive_depth and optional_scopes_depth.

    Args:
        query_metadata_table: QueryMetadataTable object containing all metadata collected during
                              query processing, including location metadata (e.g. which locations
                              are folded or optional).

    Returns:
        Dict[Tuple[str], LocationInfo], dictionary mapping query path to LocationInfo at that path.
    """
    query_path_to_location_info = {}
    for location, location_info in query_metadata_table.registered_locations:
        if location.query_path in query_path_to_location_info:
            # make sure the stored location information equals the new location information
            # for the fields the SQL backend requires.
            equivalent_location_info = query_path_to_location_info[location.query_path]
            if not _location_infos_equal(location_info, equivalent_location_info):
                raise AssertionError(
                    u'Differing LocationInfos at query_path {} between {} and {}. Expected '
                    u'parent_location.query_path, optional_scopes_depth, recursive_scopes_depth '
                    u'and types to be equal for LocationInfos sharing the same query path.'.format(
                        location.query_path, location_info, equivalent_location_info))

        query_path_to_location_info[location.query_path] = location_info
    return query_path_to_location_info


def _location_infos_equal(left, right):
    """Return True if LocationInfo objects are equivalent for the SQL backend, False otherwise."""
    if not isinstance(left, LocationInfo) or not isinstance(right, LocationInfo):
        raise AssertionError(
            (u'Unsupported LocationInfo comparison between types {} and {} '
             u'with values {}, {}').format(type(left), type(right), left, right))
    optional_scopes_depth_equal = (left.optional_scopes_depth == right.optional_scopes_depth)

    parent_query_paths_equal = (
        (left.parent_location is None and right.parent_location is None) or
        (left.parent_location.query_path == right.parent_location.query_path))

    recursive_scopes_depths_equal = (left.recursive_scopes_depth == right.recursive_scopes_depth)

    types_equal = left.type == right.type

    all_equal = (optional_scopes_depth_equal and parent_query_paths_equal and
                 recursive_scopes_depths_equal and types_equal)
    return all_equal


def _map_query_path_to_outputs(construct_result, query_path_to_location_info):
    """Assign the output fields of a ConstructResult block to their respective query_path."""
    query_path_to_output_fields = {}
    for output_name, field in six.iteritems(construct_result.fields):
        field_name = field.location.field
        if field_name in UNSUPPORTED_META_FIELDS:
            raise exceptions.GraphQLNotSupportedByBackendError(
                u'"{}" is unsupported for output.'.format(UNSUPPORTED_META_FIELDS[field_name]))
        output_query_path = field.location.query_path
        output_field_info = SqlOutput(
            field_name=field_name,
            output_name=output_name,
            graphql_type=query_path_to_location_info[output_query_path].type)
        output_field_mapping = query_path_to_output_fields.setdefault(output_query_path, [])
        output_field_mapping.append(output_field_info)
    return query_path_to_output_fields


def _map_block_index_to_location(ir_blocks):
    """Associate each IR block with it's corresponding location, by index."""
    block_index_to_location = {}
    current_block_ixs = []
    for num, ir_block in enumerate(ir_blocks):
        current_block_ixs.append(num)
        if isinstance(ir_block, blocks.MarkLocation):
            for ix in current_block_ixs:
                block_index_to_location[ix] = ir_block.location
            current_block_ixs = []
    return block_index_to_location
