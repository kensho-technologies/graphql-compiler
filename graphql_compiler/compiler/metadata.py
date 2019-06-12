# Copyright 2018-present Kensho Technologies, LLC.
"""Utilities for recording, inspecting, and manipulating metadata collected during compilation."""
from collections import namedtuple

import six

from .helpers import Location


LocationInfo = namedtuple(
    'LocationInfo',
    (
        'parent_location',         # Location/FoldScopeLocation, the parent of the current location
        'type',                    # GraphQL type object for the type at that location

        'coerced_from_type',       # GraphQL type object for the type before coercion,
                                   # or None if no coercion was applied

        'optional_scopes_depth',   # int, how many nested optional scopes this location is in
        'recursive_scopes_depth',  # int, how many nested recursion scopes this location is in
        'is_within_fold',          # bool, True if this location is within a fold scope;
                                   #       fold scopes are not allowed to nest within each other.
    )
)


OutputInfo = namedtuple(
    'OutputInfo',
    (
        'location',     # Location/FoldScopeLocation, where to output from
        'type',         # GraphQLType of the output
        'optional',     # boolean, whether the output was defined within an @optional scope
    )
)

TagInfo = namedtuple(
    'TagInfo',
    (
        'location',     # Location/FoldScopeLocation, where to output from
        'type',         # GraphQLType of the tag
        'optional',     # boolean, whether the output was defined within an @optional scope
    )
)

FilterInfo = namedtuple(
    'FilterInfo',
    (
        'fields',
        'op_name',
        'args',
    )
)

RecurseInfo = namedtuple(
    'RecurseInfo',
    (
        'edge_direction',
        'edge_name',
        'depth',
    )
)


@six.python_2_unicode_compatible
class QueryMetadataTable(object):
    """Query metadata container with info on locations, inputs, outputs, and tags in the query."""

    def __init__(self, root_location, root_location_info):
        """Create a new empty QueryMetadataTable object."""
        if not isinstance(root_location, Location):
            raise AssertionError(u'Expected Location object as the root of the QueryMetadataTable. '
                                 u'Note that FoldScopeLocation objects cannot be root locations. '
                                 u'Got: {} {}'.format(type(root_location).__name__, root_location))

        if len(root_location.query_path) != 1 or root_location.visit_counter != 1:
            raise AssertionError(u'Expected a root location with a query path of length 1, and a '
                                 u'visit counter of 1, but received: {}'.format(root_location))

        self._root_location = root_location  # Location, the root location of the entire query
        self._locations = dict()             # dict, Location/FoldScopeLocation -> LocationInfo
        self._inputs = dict()                # dict, input name -> input info namedtuple
        self._outputs = dict()               # dict, output name -> output info namedtuple
        self._tags = dict()                  # dict, tag name -> tag info namedtuple

        self._filter_infos = dict()          # Location -> FilterInfo array
        self._recurse_infos = dict()         # Location -> RecurseInfo array

        # dict, revisiting Location -> revisit origin, i.e. the first Location with that query path
        self._revisit_origins = dict()

        # dict, revisit origin Location -> set of Locations for which
        #       that Location is the revisit origin
        self._revisits = dict()

        # dict, Location/FoldScopeLocation -> set of Location and FoldScopeLocation objects
        #       that are directly descended from it
        self._child_locations = dict()

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

        if location.field is not None:
            raise AssertionError(u'Attempting to register a location at a field, this is '
                                 u'not allowed: {} {}'.format(location, location_info))

        if location_info.parent_location is None:
            # Only the root location and revisits of the root location are allowed
            # to not have a parent location.
            is_root_location = location == self._root_location
            is_revisit_of_root_location = self._root_location.is_revisited_at(location)
            if not (is_root_location or is_revisit_of_root_location):
                raise AssertionError(u'All locations other than the root location and its revisits '
                                     u'must have a parent location, but received a location with '
                                     u'no parent: {} {}'.format(location, location_info))
        else:
            self._child_locations.setdefault(location_info.parent_location, set()).add(location)

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

        # If "location" is itself a revisit, then we point "revisited_location" to "location"'s
        # revisit origin. If "location" is not a revisit, then it itself is the revisit origin.
        revisit_origin = self._revisit_origins.get(location, location)
        self._revisit_origins[revisited_location] = revisit_origin
        self._revisits.setdefault(revisit_origin, set()).add(revisited_location)

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
        location_info = self._locations.get(location, None)
        if location_info is None:
            raise AssertionError(u'Attempted to get the location info of an unregistered location: '
                                 u'{}'.format(location))
        return location_info

    @property
    def outputs(self):
        """Return an iterable of (output_name, output_info) tuples for all outputs in the query."""
        for output_name, output_info in six.iteritems(self._outputs):
            yield output_name, output_info

    def record_output_info(self, output_name, output_info):
        """Record information about the output."""
        old_info = self._outputs.get(output_name, None)
        if old_info is not None:
            raise AssertionError(u'Attempting to reuse an already-defined output name {}. '
                                 u'old info {}, new info {}.'
                                 .format(output_name, old_info, output_info))
        self._outputs[output_name] = output_info

    def get_output_info(self, output_name):
        """Get information about an output."""
        return self._outputs.get(output_name, None)

    @property
    def tags(self):
        """Return an iterable of (tag_name, tag_info) tuples for all tags in the query."""
        for tag_name, tag_info in six.iteritems(self._tags):
            yield tag_name, tag_info

    def record_tag_info(self, tag_name, tag_info):
        """Record information about the tag."""
        old_info = self._tags.get(tag_name, None)
        if old_info is not None:
            raise AssertionError(u'Attempting to define an already-defined tag {}. '
                                 u'old info {}, new info {}'
                                 .format(tag_name, old_info, tag_info))
        self._tags[tag_name] = tag_info

    def get_tag_info(self, tag_name):
        """Get information about a tag."""
        return self._tags.get(tag_name, None)

    def record_filter_info(self, location, filter_info):
        """Record filter information about the location."""
        record_location = location.at_vertex()
        self._filter_infos.setdefault(record_location, []).append(filter_info)

    def get_filter_infos(self, location):
        """Get information about filters at the location."""
        return self._filter_infos.get(location, [])

    def record_recurse_info(self, location, recurse_info):
        """Record recursion information about the location."""
        record_location = location.at_vertex()
        self._recurse_infos.setdefault(record_location, []).append(recurse_info)

    def get_recurse_infos(self, location):
        """Get information about recursions at the location."""
        return self._recurse_infos.get(location, [])

    def get_child_locations(self, location):
        """Yield an iterable of child locations for a given Location/FoldScopeLocation object."""
        self.get_location_info(location)  # purely to check for location validity

        for child_location in self._child_locations.get(location, []):
            yield child_location

    def get_all_revisits(self, location):
        """Yield an iterable of locations that revisit that location or another of its revisits."""
        self.get_location_info(location)  # purely to check for location validity

        for revisit_location in self._revisits.get(location, []):
            yield revisit_location

    def get_revisit_origin(self, location):
        """Return the location that this location revisits, or the input if it isn't a revisit.

        Args:
            location: Location/FoldScopeLocation object whose revisit origin to get

        Returns:
            Location object representing the first location with the same query path as the given
            location. Returns the given location itself if that location is the first one with
            that query path. Guaranteed to return the input location if it is a FoldScopeLocation.
        """
        self.get_location_info(location)  # purely to check for location validity
        return self._revisit_origins.get(location, location)

    @property
    def registered_locations(self):
        """Return an iterable of (location, location_info) tuples for all registered locations."""
        for location, location_info in six.iteritems(self._locations):
            yield location, location_info

    def __str__(self):
        """Return a human-readable str representation of the QueryMetadataTable object."""
        return (
            u'QueryMetadataTable(root_location={}, locations={}, inputs={}, outputs={}, tags={})'
            .format(self._root_location, self._locations, self._inputs, self._outputs, self._tags)
        )

    def __repr__(self):
        """Return a human-readable str representation of the QueryMetadataTable object."""
        return self.__str__()
