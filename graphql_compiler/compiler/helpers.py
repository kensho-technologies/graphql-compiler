# Copyright 2017-present Kensho Technologies, LLC.
"""Common helper objects, base classes and methods."""
from collections import namedtuple
import string

import funcy
from graphql import GraphQLList, GraphQLNonNull, GraphQLString, is_type
from graphql.language.ast import InlineFragment
from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType, GraphQLUnionType
import six

from ..exceptions import GraphQLCompilationError


# These are the Java (OrientDB) representations of the ISO-8601 standard date and datetime formats.
STANDARD_DATE_FORMAT = 'yyyy-MM-dd'
STANDARD_DATETIME_FORMAT = 'yyyy-MM-dd\'T\'HH:mm:ssX'

VARIABLE_ALLOWED_CHARS = frozenset(six.text_type(string.ascii_letters + string.digits + '_'))


FilterOperationInfo = namedtuple(
    'FilterOperationInfo',
    ('directive', 'field_ast', 'field_name', 'field_type'))


def get_only_element_from_collection(one_element_collection):
    """Assert that the collection has exactly one element, then return that element."""
    if len(one_element_collection) != 1:
        raise AssertionError(u'Expected a collection with exactly one element, but got: {}'
                             .format(one_element_collection))
    return funcy.first(one_element_collection)


def get_ast_field_name(ast):
    """Return the normalized field name for the given AST node."""
    replacements = {
        # We always rewrite the following field names into their proper underlying counterparts.
        '__typename': '@class'
    }
    base_field_name = ast.name.value
    normalized_name = replacements.get(base_field_name, base_field_name)
    return normalized_name


def get_ast_field_name_or_none(ast):
    """Return the field name for the AST node, or None if the AST is an InlineFragment."""
    if isinstance(ast, InlineFragment):
        return None
    return get_ast_field_name(ast)


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


def is_vertex_field_name(field_name):
    """Return True if the field's name indicates it is a non-root vertex field."""
    return field_name.startswith('out_') or field_name.startswith('in_')


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
    """Return the provided string, surrounded by single quotes. Unsafe strings cause exceptions."""
    validate_safe_string(value)
    return u'\'{}\''.format(value)


def validate_safe_string(value):
    """Ensure the provided string does not have illegal characters."""
    # The following strings are explicitly allowed, despite having otherwise-illegal chars.
    legal_strings_with_special_chars = frozenset({'@rid', '@class', '@this', '%'})

    if not isinstance(value, six.string_types):
        raise TypeError(u'Expected string value, got: {} {}'.format(
            type(value).__name__, value))

    if not value:
        raise GraphQLCompilationError(u'Empty strings are not allowed!')

    if value[0] in string.digits:
        raise GraphQLCompilationError(u'String values cannot start with a digit: {}'.format(value))

    if not set(value).issubset(VARIABLE_ALLOWED_CHARS) and \
            value not in legal_strings_with_special_chars:
        raise GraphQLCompilationError(u'Encountered illegal characters in string: {}'.format(value))


def validate_edge_direction(edge_direction):
    """Ensure the provided edge direction is either "in" or "out"."""
    if not isinstance(edge_direction, six.string_types):
        raise TypeError(u'Expected string edge_direction, got: {} {}'.format(
                        type(edge_direction), edge_direction))

    if edge_direction not in {u'in', u'out'}:
        raise ValueError(u'Unrecognized edge direction: {}'.format(edge_direction))


def validate_marked_location(location):
    """Validate that a Location object is safe for marking, and not at a field."""
    if not isinstance(location, Location):
        raise TypeError(u'Expected Location location, got: {} {}'.format(
            type(location).__name__, location))

    if location.field is not None:
        raise GraphQLCompilationError(u'Cannot mark location at a field: {}'.format(location))


@six.python_2_unicode_compatible
class Location(object):
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

    def revisit(self):
        """Return a new Location object with an incremented 'visit_counter'."""
        if self.field:
            raise AssertionError(u'Attempted to revisit a location at a field: {}'.format(self))
        return Location(self.query_path, field=None, visit_counter=(self.visit_counter + 1))

    def get_location_name(self):
        """Return a tuple of a unique name of the Location, and the current field name (or None)."""
        mark_name = u'__'.join(self.query_path) + u'___' + six.text_type(self.visit_counter)
        return (mark_name, self.field)

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

    def __hash__(self):
        """Return the object's hash value."""
        return hash(self.query_path) ^ hash(self.field) ^ hash(self.visit_counter)


@six.python_2_unicode_compatible
class FoldScopeLocation(object):
    def __init__(self, base_location, relative_position):
        """Create a new FoldScopeLocation object. Used to represent the locations of @fold scopes.

        Args:
            base_location: Location object defining where the @fold scope is rooted. In other words,
                           the location of the tightest scope that fully contains the @fold scope.
            relative_position: (edge_direction, edge_name) tuple, representing where the @fold scope
                               lies within its base_location scope.

        Returns:
            a new FoldScopeLocation object
        """
        if not isinstance(base_location, Location):
            raise TypeError(u'Expected a Location for base_location, got: '
                            u'{} {}'.format(type(base_location), base_location))

        if base_location.field:
            raise ValueError(u'Expected Location object that points to a vertex, got: '
                             u'{}'.format(base_location))

        if not isinstance(relative_position, tuple) or not len(relative_position) == 2:
            raise TypeError(u'Expected relative_position to be a tuple of two elements, got: '
                            u'{} {}'.format(type(relative_position), relative_position))

        # If we ever allow folds deeper than a single level,
        # relative_position might need rethinking.
        edge_direction, edge_name = relative_position
        validate_edge_direction(edge_direction)
        validate_safe_string(edge_name)

        self.base_location = base_location
        self.relative_position = relative_position

    def get_location_name(self):
        """Return a unique name for the FoldScopeLocation."""
        edge_direction, edge_name = self.relative_position
        return (self.base_location.get_location_name()[0] + u'___' +
                edge_direction + u'_' + edge_name)

    def __str__(self):
        """Return a human-readable str representation of the FoldScopeLocation object."""
        return u'FoldScopeLocation({}, {})'.format(self.base_location, self.relative_position)

    def __repr__(self):
        """Return a human-readable str representation of the FoldScopeLocation object."""
        return self.__str__()

    def __eq__(self, other):
        """Return True if the FoldScopeLocations are equal, and False otherwise."""
        return (type(self) == type(other) and
                self.base_location == other.base_location and
                self.relative_position == other.relative_position)

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)

    def __hash__(self):
        """Return the object's hash value."""
        return hash(self.base_location) ^ hash(self.relative_position)
