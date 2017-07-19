# Copyright 2017 Kensho Technologies, Inc.
from abc import ABCMeta
import string

from graphql import GraphQLEnumType, GraphQLNonNull, GraphQLScalarType, GraphQLString, is_type

from ..exceptions import GraphQLCompilationError


VARIABLE_ALLOWED_CHARS = frozenset(unicode(string.ascii_letters + string.digits + '_'))


def get_ast_field_name(ast):
    """Return the normalized field name for the given AST node."""
    replacements = {
        # We always rewrite the following field names into their proper underlying counterparts.
        '__typename': '@class'
    }
    base_field_name = ast.name.value
    normalized_name = replacements.get(base_field_name, base_field_name)
    return normalized_name


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


def strip_non_null_from_type(graphql_type):
    """Return the GraphQL type stripped of its GraphQLNonNull annotations."""
    while isinstance(graphql_type, GraphQLNonNull):
        graphql_type = graphql_type.of_type
    return graphql_type


def is_real_leaf_type(graphql_type):
    """Return True if the argument is a leaf type, and False otherwise."""
    # HACK(predrag): Workaround for graphql-core issue:
    #                https://github.com/graphql-python/graphql-core/issues/105
    return isinstance(strip_non_null_from_type(graphql_type),
                      (GraphQLScalarType, GraphQLEnumType))


def is_graphql_type(graphql_type):
    """Return True if the argument is a GraphQL type object, and False otherwise."""
    # Helper function to work around the fact that "is_type" is a poorly-named function.
    return is_type(graphql_type)


def ensure_unicode_string(value):
    """Ensure the value is a basestring, and return it as unicode."""
    if not isinstance(value, basestring):
        raise TypeError(u'Expected basestring value, got: {}'.format(value))
    return unicode(value)


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

    if not isinstance(value, basestring):
        raise TypeError(u'Expected basestring value, got: {} {}'.format(
            type(value).__name__, value))

    if not value:
        raise GraphQLCompilationError(u'Empty strings are not allowed!')

    if value[0] in string.digits:
        raise GraphQLCompilationError(u'String values cannot start with a digit: {}'.format(value))

    if not set(value).issubset(VARIABLE_ALLOWED_CHARS) and \
            value not in legal_strings_with_special_chars:
        raise GraphQLCompilationError(u'Encountered illegal characters in string: {}'.format(value))


def validate_marked_location(location):
    """Validate that a Location object is safe for marking, and not at a field."""
    if not isinstance(location, Location):
        raise TypeError(u'Expected Location location, got: {} {}'.format(
            type(location).__name__, location))

    if location.field is not None:
        raise GraphQLCompilationError(u'Cannot mark location at a field: {}'.format(location))


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
            query_path: tuple of basestrings, in-order, one for each vertex in the
                        current nested position in the graph
            field: basestring if at a field in a vertex, or None if at a vertex
            visit_counter: int, number that allows semantic disambiguation of otherwise equivalent
                           Location objects -- see the explanation above.

        Returns:
            new Location object with the provided properties
        """
        if not isinstance(query_path, tuple):
            raise TypeError(u'Expected query_path to be a tuple, was: '
                            u'{} {}'.format(type(query_path).__name__, query_path))
        if field and not isinstance(field, basestring):
            raise TypeError(u'Expected field to be None or basestring, was: '
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
        if not isinstance(child, basestring):
            raise TypeError(u'Expected child to be a basestring, was: {}'.format(child))
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
        mark_name = u'__'.join(self.query_path) + u'___' + unicode(self.visit_counter)
        return (mark_name, self.field)

    def __unicode__(self):
        """Return a human-readable unicode representation of the Location object."""
        return u'Location({}, {}, {})'.format(self.query_path, self.field, self.visit_counter)

    def __str__(self):
        """Return a human-readable str representation of the Location object."""
        return self.__unicode__().encode('utf-8')

    def __repr__(self):
        """Return a human-readable str representation of the Location object."""
        return self.__str__()

    def __eq__(self, other):
        """Return True if the Locations are equal, and False otherwise."""
        return (self.query_path == other.query_path and
                self.field == other.field and
                self.visit_counter == other.visit_counter)

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)

    def __hash__(self):
        """Return the object's hash value."""
        return hash(self.query_path) ^ hash(self.field) ^ hash(self.visit_counter)


class CompilerEntity(object):
    """An abstract compiler entity. Can represent things like basic blocks and expressions."""

    __metaclass__ = ABCMeta

    def __init__(self, *args, **kwargs):
        """Construct a new CompilerEntity."""
        self._print_args = args
        self._print_kwargs = kwargs

    def validate(self):
        """Ensure that the CompilerEntity is valid."""
        pass

    def __unicode__(self):
        """Return a human-readable unicode representation of this CompilerEntity."""
        printed_args = []
        if self._print_args:
            printed_args.append('{args}')
        if self._print_kwargs:
            printed_args.append('{kwargs}')

        template = u'{cls_name}(' + u', '.join(printed_args) + u')'
        return template.format(cls_name=type(self).__name__,
                               args=self._print_args,
                               kwargs=self._print_kwargs)

    def __str__(self):
        """Return a human-readable str representation of this CompilerEntity."""
        return self.__unicode__().encode('utf-8')

    def __repr__(self):
        """Return a human-readable str representation of the CompilerEntity object."""
        return self.__str__()

    # pylint: disable=protected-access
    def __eq__(self, other):
        """Return True if the CompilerEntity objects are equal, and False otherwise."""
        return (type(self) == type(other) and
                self._print_args == other._print_args and
                self._print_kwargs == other._print_kwargs)
    # pylint: enable=protected-access

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)

    def to_gremlin(self):
        """Return the Gremlin unicode string representation of this object."""
        raise NotImplementedError()

    def to_match(self):
        """Return the MATCH unicode string representation of this object."""
        raise NotImplementedError()
