# Copyright 2017-present Kensho Technologies, LLC.
"""Common helper objects, base classes and methods."""
from abc import ABCMeta, abstractmethod
from collections import Hashable, namedtuple
from functools import total_ordering
import string

import funcy
from graphql import GraphQLList, GraphQLNonNull, GraphQLString, is_type
from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType, GraphQLUnionType
import six

from ..exceptions import GraphQLCompilationError
from ..schema import INBOUND_EDGE_FIELD_PREFIX, OUTBOUND_EDGE_FIELD_PREFIX, is_vertex_field_name


# These are the Java (OrientDB) representations of the ISO-8601 standard date and datetime formats.
STANDARD_DATE_FORMAT = 'yyyy-MM-dd'
STANDARD_DATETIME_FORMAT = 'yyyy-MM-dd\'T\'HH:mm:ssX'

VARIABLE_ALLOWED_CHARS = frozenset(six.text_type(string.ascii_letters + string.digits + '_'))

OUTBOUND_EDGE_DIRECTION = 'out'
INBOUND_EDGE_DIRECTION = 'in'
ALLOWED_EDGE_DIRECTIONS = frozenset({OUTBOUND_EDGE_DIRECTION, INBOUND_EDGE_DIRECTION})


FilterOperationInfo = namedtuple(
    'FilterOperationInfo',
    ('directive', 'field_ast', 'field_name', 'field_type'))


def get_only_element_from_collection(one_element_collection):
    """Assert that the collection has exactly one element, then return that element."""
    if len(one_element_collection) != 1:
        raise AssertionError(u'Expected a collection with exactly one element, but got: {}'
                             .format(one_element_collection))
    return funcy.first(one_element_collection)


def get_field_type_from_schema(schema_type, field_name):
    """Return the type of the field in the given type, accounting for field name normalization."""
    if field_name == '@class':
        return GraphQLString
    else:
        if field_name not in schema_type.fields:
            raise AssertionError(u'Field {} passed validation but was not present on type '
                                 u'{}'.format(field_name, schema_type))

        # Validation guarantees that the field must exist in the schema.
        return schema_type.fields[field_name].type


def get_vertex_field_type(current_schema_type, vertex_field_name):
    """Return the type of the vertex within the specified vertex field name of the given type."""
    # According to the schema, the vertex field itself is of type GraphQLList, and this is
    # what get_field_type_from_schema returns. We care about what the type *inside* the list is,
    # i.e., the type on the other side of the edge (hence .of_type).
    # Validation guarantees that the field must exist in the schema.
    if not is_vertex_field_name(vertex_field_name):
        raise AssertionError(u'Trying to load the vertex field type of a non-vertex field: '
                             u'{} {}'.format(current_schema_type, vertex_field_name))

    raw_field_type = get_field_type_from_schema(current_schema_type, vertex_field_name)
    if not isinstance(strip_non_null_from_type(raw_field_type), GraphQLList):
        raise AssertionError(u'Found an edge whose schema type was not GraphQLList: '
                             u'{} {} {}'.format(current_schema_type, vertex_field_name,
                                                raw_field_type))
    return raw_field_type.of_type


def strip_non_null_from_type(graphql_type):
    """Return the GraphQL type stripped of its GraphQLNonNull annotations."""
    while isinstance(graphql_type, GraphQLNonNull):
        graphql_type = graphql_type.of_type
    return graphql_type


def strip_non_null_and_list_from_type(graphql_type):
    """Return the GraphQL type stripped of its GraphQLNonNull and GraphQLList annotations."""
    while isinstance(graphql_type, (GraphQLNonNull, GraphQLList)):
        graphql_type = graphql_type.of_type
    return graphql_type


def get_edge_direction_and_name(vertex_field_name):
    """Get the edge direction and name from a non-root vertex field name."""
    edge_direction = None
    edge_name = None
    if vertex_field_name.startswith(OUTBOUND_EDGE_FIELD_PREFIX):
        edge_direction = OUTBOUND_EDGE_DIRECTION
        edge_name = vertex_field_name[len(OUTBOUND_EDGE_FIELD_PREFIX):]
    elif vertex_field_name.startswith(INBOUND_EDGE_FIELD_PREFIX):
        edge_direction = INBOUND_EDGE_DIRECTION
        edge_name = vertex_field_name[len(INBOUND_EDGE_FIELD_PREFIX):]
    else:
        raise AssertionError(u'Unreachable condition reached:', vertex_field_name)

    validate_safe_string(edge_name)

    return edge_direction, edge_name


def is_vertex_field_type(graphql_type):
    """Return True if the argument is a vertex field type, and False otherwise."""
    # This will need to change if we ever support complex embedded types or edge field types.
    underlying_type = strip_non_null_from_type(graphql_type)
    return isinstance(underlying_type, (GraphQLInterfaceType, GraphQLObjectType, GraphQLUnionType))


def is_graphql_type(graphql_type):
    """Return True if the argument is a GraphQL type object, and False otherwise."""
    # Helper function to work around the fact that "is_type" is a poorly-named function.
    return is_type(graphql_type)


def ensure_unicode_string(value):
    """Ensure the value is a string, and return it as unicode."""
    if not isinstance(value, six.string_types):
        raise TypeError(u'Expected string value, got: {}'.format(value))
    return six.text_type(value)


def get_uniquely_named_objects_by_name(object_list):
    """Return dict of name -> object pairs from a list of objects with unique names.

    Args:
        object_list: list of objects, each X of which has a unique name accessible as X.name.value

    Returns:
        dict, { X.name.value: X for x in object_list }
        If the list is empty or None, returns an empty dict.
    """
    if not object_list:
        return dict()

    result = dict()
    for obj in object_list:
        name = obj.name.value
        if name in result:
            raise GraphQLCompilationError(u'Found duplicate object key: '
                                          u'{} {}'.format(name, object_list))
        result[name] = obj

    return result


def safe_quoted_string(value):
    """Return the provided string, surrounded by single quotes. Ensure string is safe."""
    validate_safe_string(value)
    return u'\'{}\''.format(value)


def safe_or_special_quoted_string(value):
    """Return the provided string, surrounded by single quotes. Ensure string is safe or special."""
    validate_safe_or_special_string(value)
    return u'\'{}\''.format(value)


def validate_safe_or_special_string(value, value_description='string'):
    """Ensure the string does not have illegal characters or is in a set of allowed strings."""
    # The following strings are explicitly allowed, despite having otherwise-illegal chars.
    legal_strings_with_special_chars = frozenset({'@rid', '@class', '@this', '%'})
    if value not in legal_strings_with_special_chars:
        validate_safe_string(value, value_description=value_description)


def validate_safe_string(value, value_description='string'):
    """Ensure that the provided string not have illegal characters."""
    if not value:
        raise GraphQLCompilationError(u'Empty {}s are not allowed!'.format(value_description))

    if value[0] in string.digits:
        raise GraphQLCompilationError(u'Encountered invalid {}: {}. It cannot start with a '
                                      u'digit.'.format(value_description, value))

    # set(value) is used instead of frozenset(value) to avoid printing 'frozenset' in error message.
    disallowed_chars = set(value) - VARIABLE_ALLOWED_CHARS
    if disallowed_chars:
        raise GraphQLCompilationError(u'Encountered illegal characters {} in {}: {}. It is only '
                                      u'allowed to have upper and lower case letters, '
                                      u'digits and underscores.'
                                      .format(disallowed_chars, value_description, value))


def validate_runtime_argument_name(name):
    """Ensure that the provided string is valid for use as a runtime argument name."""
    validate_safe_string(name, value_description='runtime argument name')


def validate_tagged_argument_name(name):
    """Ensure that provided string is valid for use as a tagged argument name."""
    validate_safe_string(name, value_description='tagged argument name')


def validate_output_name(name):
    """Ensure that the provided string is valid for use as an output name."""
    internal_name_prefix = u'___'
    if name.startswith(internal_name_prefix):
        raise GraphQLCompilationError(
            u'The prefix "___" (three underscores) for output names is reserved by the compiler.')
    validate_safe_string(name, value_description='output name')


def validate_edge_direction(edge_direction):
    """Ensure the provided edge direction is either "in" or "out"."""
    if not isinstance(edge_direction, six.string_types):
        raise TypeError(u'Expected string edge_direction, got: {} {}'.format(
                        type(edge_direction), edge_direction))

    if edge_direction not in ALLOWED_EDGE_DIRECTIONS:
        raise ValueError(u'Unrecognized edge direction: {}'.format(edge_direction))


def validate_marked_location(location):
    """Validate that a Location object is safe for marking, and not at a field."""
    if not isinstance(location, (Location, FoldScopeLocation)):
        raise TypeError(u'Expected Location or FoldScopeLocation location, got: {} {}'.format(
            type(location).__name__, location))

    if location.field is not None:
        raise GraphQLCompilationError(u'Cannot mark location at a field: {}'.format(location))


def _create_fold_path_component(edge_direction, edge_name):
    """Return a tuple representing a fold_path component of a FoldScopeLocation."""
    return ((edge_direction, edge_name),)  # tuple containing a tuple of two elements


def invert_dict(invertible_dict):
    """Invert a dict. A dict is invertible if values are unique and hashable."""
    inverted = {}
    for k, v in six.iteritems(invertible_dict):
        if not isinstance(v, Hashable):
            raise TypeError(u'Expected an invertible dict, but value at key {} has type {}'.format(
                k, type(v).__name__))
        if v in inverted:
            raise TypeError(u'Expected an invertible dict, but keys '
                            u'{} and {} map to the same value'.format(
                                inverted[v], k))
        inverted[v] = k
    return inverted


def is_runtime_parameter(argument):
    """Return True if the directive argument defines a runtime parameter, and False otherwise."""
    return argument.startswith('$')


def is_tagged_parameter(argument):
    """Return True if the directive argument defines a tagged parameter, and False otherwise."""
    return argument.startswith('%')


def get_parameter_name(argument):
    """Return the name of the parameter without the leading prefix."""
    if argument[0] not in {'$', '%'}:
        raise AssertionError(u'Unexpectedly received an unprefixed parameter name, unable to '
                             u'determine whether it is a runtime or tagged parameter: {}'
                             .format(argument))
    return argument[1:]


@total_ordering
@six.add_metaclass(ABCMeta)
class BaseLocation(object):
    """An abstract location object, describing a location in the GraphQL query."""

    @abstractmethod
    def navigate_to_field(self, field):
        """Return a new BaseLocation object at the specified field of the current BaseLocation."""
        raise NotImplementedError()

    @abstractmethod
    def navigate_to_subpath(self, child):
        """Return a new BaseLocation after a traversal to the specified child location."""
        raise NotImplementedError()

    @abstractmethod
    def get_location_name(self):
        """Return a tuple of a unique name of the location, and the current field name (or None)."""
        raise NotImplementedError()

    @abstractmethod
    def _check_if_object_of_same_type_is_smaller(self, other):
        """Return True if the other object is smaller than self in the total ordering."""
        raise NotImplementedError()

    @abstractmethod
    def __eq__(self, other):
        """Return True if the BaseLocations are equal, and False otherwise."""
        raise NotImplementedError()

    def __lt__(self, other):
        """Return True if the other object is smaller than self in the total ordering."""
        if isinstance(self, Location) and isinstance(other, Location):
            return self._check_if_object_of_same_type_is_smaller(other)
        elif isinstance(self, FoldScopeLocation) and isinstance(other, FoldScopeLocation):
            return self._check_if_object_of_same_type_is_smaller(other)
        elif isinstance(self, Location) and isinstance(other, FoldScopeLocation):
            if self != other.base_location:
                return self < other.base_location
            return False
        elif isinstance(self, FoldScopeLocation) and isinstance(other, Location):
            return not other <= self
        else:
            raise AssertionError(u'Received objects of types {}, {} in BaseLocation comparison. '
                                 u'Only Location and FoldScopeLocation are allowed: {} {}'
                                 .format(type(self).__name__, type(other).__name__, self, other))


@six.python_2_unicode_compatible
class Location(BaseLocation):
    def __init__(self, query_path, field=None, visit_counter=1):
        """Create a new Location object.

        Used to uniquely identify locations in the graph traversal, with three components.
            - The 'query_path' is a tuple containing the in-order nested set of vertex fields where
              the Location is.
            - The 'field' is a string set to the name of a property field, if the
              Location is at a property field, or None otherwise.
            - The 'visit_counter' is a counter that disambiguates between consecutive,
              but semantically different, visits to the same 'query_path' and 'field'.
              In the following example, note that the Location objects for 'X' and 'Y'
              have identical values for both 'query_path' (empty tuple) and 'field' (None),
              but are not semantically equivalent:
                  g.as('X').out('foo').back('X').as('Y').out('bar').optional('Y')
              The difference between 'X' and 'Y' is in the .optional() statement --
              .optional('Y') says that the 'bar' edge is optional, and .optional('X') says that
              both 'foo' and 'bar' are optional. Hence, the Location objects for 'X' and 'Y'
              should have different 'visit_counter' values.

        Args:
            query_path: tuple of strings, in-order, one for each vertex in the
                        current nested position in the graph
            field: string if at a field in a vertex, or None if at a vertex
            visit_counter: int, number that allows semantic disambiguation of otherwise equivalent
                           Location objects -- see the explanation above.

        Returns:
            new Location object with the provided properties
        """
        if not isinstance(query_path, tuple):
            raise TypeError(u'Expected query_path to be a tuple, was: '
                            u'{} {}'.format(type(query_path).__name__, query_path))
        if field and not isinstance(field, six.string_types):
            raise TypeError(u'Expected field to be None or string, was: '
                            u'{} {}'.format(type(field).__name__, field))

        self.query_path = query_path
        self.field = field

        # A single visit counter is enough, rather than a visit counter per path level,
        # because field names are unique -- one can't be at path 'X' and
        # visit 'Y' in two different ways to generate colliding 'X__Y___1' identifiers.
        self.visit_counter = visit_counter

    def navigate_to_field(self, field):
        """Return a new Location object at the specified field of the current Location's vertex."""
        if self.field:
            raise AssertionError(u'Already at a field, cannot nest fields: {}'.format(self))
        return Location(self.query_path, field=field, visit_counter=self.visit_counter)

    def at_vertex(self):
        """Get the Location ignoring its field component."""
        if not self.field:
            return self

        return Location(self.query_path, field=None, visit_counter=self.visit_counter)

    def navigate_to_subpath(self, child):
        """Return a new Location object at a child vertex of the current Location's vertex."""
        if not isinstance(child, six.string_types):
            raise TypeError(u'Expected child to be a string, was: {}'.format(child))
        if self.field:
            raise AssertionError(u'Currently at a field, cannot go to child: {}'.format(self))
        return Location(self.query_path + (child,))

    def navigate_to_fold(self, folded_child):
        """Return a new FoldScopeLocation for the folded child vertex of the current Location."""
        if not isinstance(folded_child, six.string_types):
            raise TypeError(u'Expected folded_child to be a string, was: {}'.format(folded_child))
        if self.field:
            raise AssertionError(u'Currently at a field, cannot go to folded child: '
                                 u'{}'.format(self))

        edge_direction, edge_name = get_edge_direction_and_name(folded_child)

        fold_path = _create_fold_path_component(edge_direction, edge_name)
        return FoldScopeLocation(self, fold_path)

    def revisit(self):
        """Return a new Location object with an incremented 'visit_counter'."""
        if self.field:
            raise AssertionError(u'Attempted to revisit a location at a field: {}'.format(self))
        return Location(self.query_path, field=None, visit_counter=(self.visit_counter + 1))

    def get_location_name(self):
        """Return a tuple of a unique name of the Location, and the current field name (or None)."""
        mark_name = u'__'.join(self.query_path) + u'___' + six.text_type(self.visit_counter)
        return (mark_name, self.field)

    def is_revisited_at(self, other_location):
        """Return True if other_location is a revisit of this location, and False otherwise."""
        # Note that FoldScopeLocation objects cannot revisit Location objects, or each other.
        return (isinstance(other_location, Location) and
                self.query_path == other_location.query_path and
                self.visit_counter < other_location.visit_counter)

    def __str__(self):
        """Return a human-readable str representation of the Location object."""
        return u'Location({}, {}, {})'.format(self.query_path, self.field, self.visit_counter)

    def __repr__(self):
        """Return a human-readable str representation of the Location object."""
        return self.__str__()

    def __eq__(self, other):
        """Return True if the Locations are equal, and False otherwise."""
        return (type(self) == type(other) and
                self.query_path == other.query_path and
                self.field == other.field and
                self.visit_counter == other.visit_counter)

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)

    def _check_if_object_of_same_type_is_smaller(self, other):
        """Return True if the other object is smaller than self in the total ordering."""
        if not isinstance(other, Location):
            raise AssertionError(u'Expected Location type for other. Received {}: {}'
                                 .format(type(other).__name__, other))

        if len(self.query_path) != len(other.query_path):
            return len(self.query_path) < len(other.query_path)

        if self.query_path != other.query_path:
            return self.query_path < other.query_path

        if self.visit_counter != other.visit_counter:
            return self.visit_counter < other.visit_counter

        if self.field is None:
            return other.field is not None

        if other.field is None:
            return False

        return self.field < other.field

    def __hash__(self):
        """Return the object's hash value."""
        return hash(self.query_path) ^ hash(self.field) ^ hash(self.visit_counter)


@six.python_2_unicode_compatible
class FoldScopeLocation(BaseLocation):
    def __init__(self, base_location, fold_path, field=None):
        """Create a new FoldScopeLocation object. Used to represent the locations of @fold scopes.

        Args:
            base_location: Location object defining where the @fold scope is rooted. In other words,
                           the location of the tightest scope that fully contains the @fold scope.
            fold_path: tuple of (edge_direction, edge_name) tuples, containing the traversal path
                       of the fold, starting from the base_location of the @fold scope.
            field: string if at a field in a vertex, or None if at a vertex

        Returns:
            new FoldScopeLocation object
        """
        if not isinstance(base_location, Location):
            raise TypeError(u'Expected a Location for base_location, got: '
                            u'{} {}'.format(type(base_location), base_location))

        if base_location.field:
            raise ValueError(u'Expected Location object that points to a vertex, got: '
                             u'{}'.format(base_location))

        if not isinstance(fold_path, tuple) or len(fold_path) == 0:
            raise TypeError(u'Expected fold_path to be a non-empty tuple, but got: {} {}'
                            .format(type(fold_path), fold_path))
        fold_path_is_valid = all(
            len(element) == 2 and element[0] in ALLOWED_EDGE_DIRECTIONS
            for element in fold_path
        )
        if not fold_path_is_valid:
            raise ValueError(u'Encountered an invalid fold_path: {}'.format(fold_path))

        self.base_location = base_location
        self.fold_path = fold_path
        self.field = field

    def get_location_name(self):
        """Return a tuple of a unique name of the location, and the current field name (or None)."""
        # We currently require that all outputs from a given fold are from the same location:
        # any given fold has one set of traversals away from the root, and all outputs are
        # at the tip of the set of traversals.
        #
        # Therefore, for the purposes of creating a unique edge name, it's sufficient to take
        # only one traversal from the root of the fold. This allows fold names to be shorter.
        first_folded_edge_direction, first_folded_edge_name = self.get_first_folded_edge()

        unique_name = u''.join((
            self.base_location.get_location_name()[0],
            u'___',
            first_folded_edge_direction,
            u'_',
            first_folded_edge_name
        ))
        return (unique_name, self.field)

    def get_first_folded_edge(self):
        """Return a tuple representing the first folded edge within the fold scope."""
        # The constructor of this object guarantees that the fold has at least one traversal,
        # so the [0]-indexing is guaranteed to not raise an exception.
        first_folded_edge_direction, first_folded_edge_name = self.fold_path[0]
        return first_folded_edge_direction, first_folded_edge_name

    def at_vertex(self):
        """Get the FoldScopeLocation ignoring its field component."""
        if not self.field:
            return self

        return FoldScopeLocation(self.base_location, self.fold_path, field=None)

    def navigate_to_field(self, field):
        """Return a new location object at the specified field of the current location."""
        if self.field:
            raise AssertionError(u'Already at a field, cannot nest fields: {}'.format(self))
        return FoldScopeLocation(self.base_location, self.fold_path, field=field)

    def navigate_to_subpath(self, child):
        """Return a new location after a traversal to the specified child location."""
        if not isinstance(child, six.string_types):
            raise TypeError(u'Expected child to be a string, was: {}'.format(child))
        if self.field:
            raise AssertionError(u'Currently at a field, cannot go to child: {}'.format(self))

        edge_direction, edge_name = get_edge_direction_and_name(child)
        new_fold_path = self.fold_path + _create_fold_path_component(edge_direction, edge_name)
        return FoldScopeLocation(self.base_location, new_fold_path)

    def __str__(self):
        """Return a human-readable str representation of the FoldScopeLocation object."""
        return u'FoldScopeLocation({}, {}, field={})'.format(
            self.base_location, self.fold_path, self.field)

    def __repr__(self):
        """Return a human-readable str representation of the FoldScopeLocation object."""
        return self.__str__()

    def __eq__(self, other):
        """Return True if the FoldScopeLocations are equal, and False otherwise."""
        return (type(self) == type(other) and
                self.base_location == other.base_location and
                self.fold_path == other.fold_path and
                self.field == other.field)

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)

    def __hash__(self):
        """Return the object's hash value."""
        return hash(self.base_location) ^ hash(self.fold_path) ^ hash(self.field)

    def _check_if_object_of_same_type_is_smaller(self, other):
        """Return True if the other object is smaller than self in the total ordering."""
        if not isinstance(other, FoldScopeLocation):
            raise AssertionError(u'Expected FoldScopeLocation type for other. Received {}: {}'
                                 .format(type(other).__name__, other))

        if self.base_location != other.base_location:
            return self.base_location < other.base_location

        if len(self.fold_path) != len(other.fold_path):
            return len(self.fold_path) < len(other.fold_path)

        if self.fold_path != other.fold_path:
            return self.fold_path < other.fold_path

        if self.field is None:
            return other.field is not None

        if other.field is None:
            return False

        return self.field < other.field
