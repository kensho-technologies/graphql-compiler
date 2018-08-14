# Copyright 2018-present Kensho Technologies, LLC.
"""Utilities for recording, inspecting, and manipulating metadata collected during compilation."""
from collections import namedtuple

import six


LocationInfo = namedtuple(
    'LocationInfo',
    (
        'parent_location',         # Location/FoldScopeLocation, the parent of the current location
        'type',                    # str, the actual type name at that location
        'coerced_from_type',       # str, the type before coercion, or None if no coercion applied
        'optional_scopes_depth',   # int, how many nested optional scopes this location is in
        'recursive_scopes_depth',  # int, how many nested recursion scopes this location is in
        'is_within_fold',          # bool, True if this location is within an optional scope
    )
)


@six.python_2_unicode_compatible
class QueryMetadataTable(object):
    """Query metadata container with info on locations, inputs, outputs, and tags in the query."""

    def __init__(self, root_location, root_location_info):
        """Create a new empty QueryMetadataTable object."""
        self._root_location = root_location  # Location, the root location of the entire query
        self._locations = dict()             # dict, Location/FoldScopeLocation -> LocationInfo
        self._inputs = dict()                # dict, input name -> input info namedtuple
        self._outputs = dict()               # dict, output name -> output info namedtuple
        self._tags = dict()                  # dict, tag name -> tag info namedtuple
        self.register_location(root_location, root_location_info)

    @property
    def root_location(self):
        """Return the root location of the query."""
        return self._root_location

    def register_location(self, location, location_info):
        """Record a new location's metadata in the metadata table."""
        old_info = self._locations.get(location, None)
        if old_info is not None:
            raise AssertionError(u'Attempting to register an already-registered location {}: '
                                 u'old info {}, new info {}'
                                 .format(location, old_info, location_info))
        self._locations[location] = location_info

    def revisit_location(self, location):
        """Revisit a location, returning the revisited location after setting its metadata."""
        # This helper exists to avoid accidentally recording outdated metadata for the revisited
        # location. The metadata could be outdated, for example, if the original location_info
        # is preserved and not updated if a coercion is recorded at the given location.
        # In that case, the QueryMetadataTable will update its local info object, but the caller
        # might still be holding on to the original info object, therefore registering stale data.
        # This function ensures that the latest metadata on the location is always used instead.
        revisited_location = location.revisit()
        self.register_location(revisited_location, self.get_location_info(location))
        return revisited_location

    def record_coercion_at_location(self, location, coerced_to_type):
        """Record that a particular location is getting coerced to a different type."""
        current_info = self._locations.get(location, None)
        if current_info is None:
            raise AssertionError(u'Attempting to record a coercion at an unregistered location {}: '
                                 u'coerced_to_type {}'.format(location, coerced_to_type))

        if current_info.coerced_from_type is not None:
            raise AssertionError(u'Attempting to record a second coercion at the same location {}: '
                                 u'{} {}'.format(location, current_info, coerced_to_type))

        new_info = current_info._replace(
            type=coerced_to_type,
            coerced_from_type=current_info.type)
        self._locations[location] = new_info

    def get_location_info(self, location):
        """Return the LocationInfo object for a given location."""
        return self._locations[location]

    def __str__(self):
        """Return a human-readable str representation of the QueryMetadataTable object."""
        return (
            u'QueryMetadataTable(root_location={}, locations={}, inputs={}, outputs={}, tags={})'
            .format(self._root_location, self._locations, self._inputs, self._outputs, self._tags)
        )

    def __repr__(self):
        """Return a human-readable str representation of the QueryMetadataTable object."""
        return self.__str__()
