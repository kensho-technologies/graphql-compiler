# Copyright 2019-present Kensho Technologies, LLC.
"""Helper functions for Cypher, such as generating unique vertex names within fold scopes."""
from .helpers import FoldScopeLocation, Location


def get_fold_scope_location_full_path_name(fold_scope_location):
    """Return a unique name with the full traversal path to this FoldScopeLocation."""
    # HACK(Leon): Get a unique name for each vertex in a fold traversal in Cypher.
    # For FoldScopeLocation objects, get_location_name() only uses the first edge in the traversal,
    # which doesn't work for Cypher because we need to explicitly label every intermediate vertex
    # along that path.
    # For other query languages like MATCH and Gremlin, the fold directive doesn't require
    # us to name all the intermediate vertices on the path, which is why this is Cypher-specific.
    if not (isinstance(fold_scope_location, FoldScopeLocation)):
        raise TypeError(u'Expected cypher_step.as_block.location to be of type '
                        u'FoldScopeLocation. Instead, got object {} of type {}.'
                        .format(fold_scope_location, type(fold_scope_location)))
    base_location = fold_scope_location.base_location
    base_query_path = base_location.query_path  # the path traversed so far
    fold_path = fold_scope_location.fold_path  # the path specified at or within the folded scope.
    full_path = base_query_path + tuple(u'_'.join(edge_name) for edge_name in fold_path)
    location = Location(full_path, field=base_location.field,
                        visit_counter=base_location.visit_counter)
    if base_location.field is not None:
        raise ValueError(u'Expected base_location\'s field to be None since this method is used to '
                         u'traverse vertices for a fold scope and at no point do we navigate to a '
                         u'field. However, field was {}'.format(base_location.field))
    step_location_name, _ = location.get_location_name()
    return step_location_name


def get_unique_vertex_name_from_location(location):
    """Return a unique name for this location, whether or not it's in a fold scope."""
    if isinstance(location, FoldScopeLocation):
        return get_fold_scope_location_full_path_name(location)
    elif isinstance(location, Location):
        location_name, _ = location.get_location_name()
        return location_name
    raise TypeError(u'Expected location to be of type Location or FoldScopeLocation. Instead got '
                    u'type {} for location {}'.format(type(location), location))


def get_collected_vertex_list_name(full_path_name):
    """Return the name of the list generated by folding vertices with name full_path_name."""
    return u'collected_' + full_path_name
