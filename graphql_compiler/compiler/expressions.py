# Copyright 2017-present Kensho Technologies, LLC.
import operator as python_operator

from graphql import GraphQLInt, GraphQLList, GraphQLNonNull, GraphQLString
import six
import sqlalchemy
from sqlalchemy import bindparam, sql

from . import cypher_helpers, sqlalchemy_extensions
from ..exceptions import GraphQLCompilationError
from ..schema import (
    ALL_SUPPORTED_META_FIELDS, COUNT_META_FIELD_NAME, TYPENAME_META_FIELD_NAME, GraphQLDate,
    GraphQLDateTime
)
from .compiler_entities import Expression
from .helpers import (
    STANDARD_DATE_FORMAT, STANDARD_DATETIME_FORMAT, FoldScopeLocation, Location,
    ensure_unicode_string, is_graphql_type, safe_or_special_quoted_string, strip_non_null_from_type,
    validate_safe_or_special_string, validate_safe_string
)


# Since MATCH uses $-prefixed keywords to indicate special values,
# we must restrict those keywords from being used as variables.
# For consistency, we blacklist these keywords in both Gremlin and MATCH.
RESERVED_MATCH_KEYWORDS = frozenset({
    u'$matches',
    u'$matched',
    u'$paths',
    u'$elements',
    u'$pathElements',
    u'$depth',
    u'$currentMatch',
})


def make_replacement_visitor(find_expression, replace_expression):
    """Return a visitor function that replaces every instance of one expression with another one."""
    def visitor_fn(expression):
        """Return the replacement if this expression matches the expression we're looking for."""
        if expression == find_expression:
            return replace_expression
        else:
            return expression

    return visitor_fn


def make_type_replacement_visitor(find_types, replacement_func):
    """Return a visitor function that replaces expressions of a given type with new expressions."""
    def visitor_fn(expression):
        """Return a replacement expression if the original expression is of the correct type."""
        if isinstance(expression, find_types):
            return replacement_func(expression)
        else:
            return expression

    return visitor_fn


class Literal(Expression):
    """A literal, such as a boolean value, null, or a fixed string value.

    We have to be extra careful with string literals -- for ease of escaping, we use
    json.dumps() to represent strings. However, we must then manually escape '$' characters
    as they trigger string interpolation in Groovy/Gremlin.
        http://docs.groovy-lang.org/latest/html/documentation/index.html#_string_interpolation

    Think long and hard about the above before allowing literals in user-supplied GraphQL!
    """

    __slots__ = ('value',)

    def __init__(self, value):
        """Construct a new Literal object with the given value."""
        super(Literal, self).__init__(value)
        self.value = value
        self.validate()

    def validate(self):
        """Validate that the Literal is correctly representable."""
        # Literals representing boolean values or None are correctly representable and supported.
        if self.value is None or self.value is True or self.value is False:
            return

        # Literal safe strings are correctly representable and supported.
        if isinstance(self.value, six.string_types):
            validate_safe_or_special_string(self.value)
            return

        # Literal ints are correctly representable and supported.
        if isinstance(self.value, int):
            return

        # Literal empty lists, and non-empty lists of safe strings, are
        # correctly representable and supported.
        if isinstance(self.value, list):
            if len(self.value) > 0:
                for x in self.value:
                    validate_safe_or_special_string(x)
            return

        raise GraphQLCompilationError(u'Cannot represent literal: {}'.format(self.value))

    def _to_output_code(self):
        """Return a unicode object with the Gremlin/MATCH/Cypher representation of this Literal."""
        # All supported Literal objects serialize to identical strings
        # in all of Gremlin, Cypher, and MATCH.
        self.validate()
        if self.value is None:
            return u'null'
        elif self.value is True:
            return u'true'
        elif self.value is False:
            return u'false'
        elif isinstance(self.value, six.string_types):
            return safe_or_special_quoted_string(self.value)
        elif isinstance(self.value, int):
            return six.text_type(self.value)
        elif isinstance(self.value, list):
            if len(self.value) == 0:
                return '[]'
            elif all(isinstance(x, six.string_types) for x in self.value):
                list_contents = ', '.join(
                    safe_or_special_quoted_string(x)
                    for x in sorted(self.value)
                )
                return '[' + list_contents + ']'
        else:
            pass  # Fall through to assertion error below.
        raise AssertionError(u'Unreachable state reached: {}'.format(self))

    to_gremlin = _to_output_code
    to_match = _to_output_code
    to_cypher = _to_output_code

    def to_sql(self, aliases, current_alias):
        """Return the value."""
        self.validate()
        return self.value


NullLiteral = Literal(None)
TrueLiteral = Literal(True)
FalseLiteral = Literal(False)
EmptyListLiteral = Literal([])
ZeroLiteral = Literal(0)


class Variable(Expression):
    """A variable for a parameterized query, to be filled in at runtime."""

    __slots__ = ('variable_name', 'inferred_type')

    def __init__(self, variable_name, inferred_type):
        """Construct a new Variable object for the given variable name.

        Args:
            variable_name: string, should start with '$' and then obey variable naming rules
                           (see validate_safe_string())
            inferred_type: GraphQL type object, specifying the inferred type of the variable

        Returns:
            new Variable object
        """
        variable_name = ensure_unicode_string(variable_name)
        super(Variable, self).__init__(variable_name, inferred_type)
        self.variable_name = variable_name
        self.inferred_type = inferred_type
        self.validate()

    def validate(self):
        """Validate that the Variable is correctly representable."""
        # Get the first letter, or empty string if it doesn't exist.
        if not self.variable_name.startswith(u'$'):
            raise GraphQLCompilationError(u'Expected variable name to start with $, but was: '
                                          u'{}'.format(self.variable_name))

        if self.variable_name in RESERVED_MATCH_KEYWORDS:
            raise GraphQLCompilationError(u'Cannot use reserved MATCH keyword {} as variable '
                                          u'name!'.format(self.variable_name))

        validate_safe_string(self.variable_name[1:])

        if not is_graphql_type(self.inferred_type):
            raise ValueError(u'Invalid value of "inferred_type": {}'.format(self.inferred_type))

        if isinstance(self.inferred_type, GraphQLNonNull):
            raise ValueError(u'GraphQL non-null types are not supported as "inferred_type": '
                             u'{}'.format(self.inferred_type))

        if isinstance(self.inferred_type, GraphQLList):
            inner_type = strip_non_null_from_type(self.inferred_type.of_type)
            if GraphQLDate.is_same_type(inner_type) or GraphQLDateTime.is_same_type(inner_type):
                # This is a compilation error rather than a ValueError as
                # it can be caused by an invalid GraphQL query on an otherwise valid schema.
                # In other words, it's an error in writing the GraphQL query, rather than
                # a programming error within the library.
                raise GraphQLCompilationError(
                    u'Lists of Date or DateTime cannot currently be represented as '
                    u'Variable objects: {}'.format(self.inferred_type))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this Variable."""
        self.validate()

        # We don't want the dollar sign as part of the variable name.
        variable_with_no_dollar_sign = self.variable_name[1:]

        match_variable_name = '{%s}' % (six.text_type(variable_with_no_dollar_sign),)

        # We can't directly pass a Date or DateTime object, so we have to pass it as a string
        # and then parse it inline. For date format parameter meanings, see:
        # http://docs.oracle.com/javase/7/docs/api/java/text/SimpleDateFormat.html
        # For the semantics of the date() OrientDB SQL function, see:
        # http://orientdb.com/docs/last/SQL-Functions.html#date
        if GraphQLDate.is_same_type(self.inferred_type):
            return u'date(%s, "%s")' % (match_variable_name, STANDARD_DATE_FORMAT)
        elif GraphQLDateTime.is_same_type(self.inferred_type):
            return u'date(%s, "%s")' % (match_variable_name, STANDARD_DATETIME_FORMAT)
        else:
            return match_variable_name

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        # We can't directly pass a Date or a DateTime object, so we have to pass it as a string
        # and then parse it inline. For date format parameter meanings, see:
        # http://docs.oracle.com/javase/7/docs/api/java/text/SimpleDateFormat.html
        if GraphQLDate.is_same_type(self.inferred_type):
            return u'Date.parse("{}", {})'.format(STANDARD_DATE_FORMAT, self.variable_name)
        elif GraphQLDateTime.is_same_type(self.inferred_type):
            return u'Date.parse("{}", {})'.format(STANDARD_DATETIME_FORMAT, self.variable_name)
        else:
            return six.text_type(self.variable_name)

    def to_cypher(self):
        """Return a unicode object with the Cypher representation of this expression."""
        # Cypher has built-in support for variable expansion, so we'll just emit a variable
        # definition and rely on Cypher to insert the value.
        self.validate()

        # The Neo4j client allows us to pass date and datetime objects directly as arguments. See
        # the compile_and_run_neo4j_query function in integration_test_helpers.py for an example of
        # how this is done.
        #
        # Meanwhile, RedisGraph (for which we're manually interpolating parameters since RedisGraph
        # doesn't support query parameters [0]) doesn't support date objects [1] anyways.
        #
        # Either way, we don't need to do any special handling for temporal values here-- either
        # we don't need to do it ourselves, or they're not supported at all.
        #
        # [0] https://github.com/RedisGraph/RedisGraph/issues/544
        # [1] https://oss.redislabs.com/redisgraph/cypher_support/#types
        return u'{}'.format(self.variable_name)

    def to_sql(self, aliases, current_alias):
        """Return a sqlalchemy BindParameter."""
        self.validate()

        is_list = isinstance(self.inferred_type, GraphQLList)
        return bindparam(self.variable_name[1:], expanding=is_list)

    def __eq__(self, other):
        """Return True if the given object is equal to this one, and False otherwise."""
        # Since this object has a GraphQL type as a variable, which doesn't implement
        # the equality operator, we have to override equality and call is_same_type() here.
        return (type(self) == type(other) and
                self.variable_name == other.variable_name and
                self.inferred_type.is_same_type(other.inferred_type))

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)


class LocalField(Expression):
    """A field at the current position in the query."""

    __slots__ = ('field_name', 'field_type')

    def __init__(self, field_name, field_type):
        """Construct a new LocalField object that references a field at the current position.

        Args:
            field_name: string, the name of the local field being referenced
            field_type: GraphQLType object describing the type of the referenced field. For some
                        special fields (such as OrientDB "@this" or "@rid"), we may be unable to
                        represent the field type in the GraphQL type system. In these situations,
                        this value is set to None.
        """
        super(LocalField, self).__init__(field_name, field_type)
        self.field_name = field_name
        self.field_type = field_type
        self.validate()

    def get_local_object_gremlin_name(self):
        """Return the Gremlin name of the local object whose field is being produced."""
        return u'it'

    def validate(self):
        """Validate that the LocalField is correctly representable."""
        validate_safe_or_special_string(self.field_name)
        if self.field_type is not None and not is_graphql_type(self.field_type):
            raise ValueError(u'Invalid value {} of "field_type": {}'.format(self.field_type, self))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this LocalField."""
        self.validate()

        if self.field_name == TYPENAME_META_FIELD_NAME:
            return six.text_type('@class')
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif self.field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(u'The SQL backend does not support meta field {}.'.format(
                self.field_name))

        return six.text_type(self.field_name)

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        local_object_name = self.get_local_object_gremlin_name()

        if self.field_name == '@this':
            return local_object_name

        if self.field_name == TYPENAME_META_FIELD_NAME:
            return u'{}[\'{}\']'.format(local_object_name, '@class')
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif self.field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(u'The SQL backend does not support meta field {}.'.format(
                self.field_name))

        if '@' in self.field_name:
            return u'{}[\'{}\']'.format(local_object_name, self.field_name)
        else:
            return u'{}.{}'.format(local_object_name, self.field_name)

    def to_sql(self, aliases, current_alias):
        """Return a sqlalchemy Column picked from the current_alias."""
        self.validate()

        if isinstance(self.field_type, GraphQLList):
            raise NotImplementedError(u'The SQL backend does not support lists. Cannot '
                                      u'process field {}.'.format(self.field_name))

        # Meta fields are special cases; assume all meta fields are not implemented.
        if self.field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(u'The SQL backend does not support meta field {}.'.format(
                self.field_name))

        return current_alias.c[self.field_name]

    def to_cypher(self):
        """Not implemented, should not be used."""
        raise AssertionError(u'LocalField is not used as part of the query emission process in '
                             u'Cypher, so this is a bug. This function should not be called.')


class GlobalContextField(Expression):
    """A field drawn from the global context, for use in a global operations WHERE statement."""

    __slots__ = ('location', 'field_type')

    def __init__(self, location, field_type):
        """Construct a new GlobalContextField object that references a field at a given location.

        Args:
            location: Location, specifying where the field was declared.

        Returns:
            new GlobalContextField object
        """
        super(GlobalContextField, self).__init__(location, field_type)
        self.location = location
        self.field_type = field_type
        self.validate()

    def validate(self):
        """Validate that the GlobalContextField is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(u'Expected Location location, got: {} {}'
                            .format(type(self.location).__name__, self.location))

        if self.location.field is None:
            raise AssertionError(u'Received Location without a field: {}'
                                 .format(self.location))

        if not is_graphql_type(self.field_type):
            raise ValueError(u'Invalid value of "field_type": {}'.format(self.field_type))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this GlobalContextField."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = '@class'
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(u'The SQL backend does not support meta field {}.'.format(
                field_name))
        validate_safe_string(mark_name)
        validate_safe_or_special_string(field_name)

        return u'%s.%s' % (mark_name, field_name)

    def to_gremlin(self):
        """Not implemented, should not be used."""
        raise AssertionError(u'GlobalContextField is only used for the WHERE statement in '
                             u'MATCH, so this is a bug. This function should not be called.')

    def to_cypher(self):
        """Not implemented, should not be used."""
        raise AssertionError(u'GlobalContextField is not used as part of the query emission '
                             u'process in Cypher, so this is a bug. This function '
                             u'should not be called.')

    def to_sql(self, aliases, current_alias):
        """Not implemented, should not be used."""
        raise AssertionError(u'GlobalContextField is not used as part of the query emission '
                             u'process in SQL, so this is a bug. This function '
                             u'should not be called.')


class ContextField(Expression):
    """A field drawn from the global context, e.g. if selected earlier in the query."""

    __slots__ = ('location', 'field_type')

    def __init__(self, location, field_type):
        """Construct a new ContextField object that references a field from the global context.

        Args:
            location: Location, specifying where the field was declared. If the Location points
                      to a vertex, the field refers to the data captured at the location vertex.
                      Otherwise, if the Location points to a property, the field refers to
                      the particular value of that property.
            field_type: GraphQLType object, specifying the type of the field being output

        Returns:
            new ContextField object
        """
        super(ContextField, self).__init__(location, field_type)
        self.location = location
        self.field_type = field_type
        self.validate()

    def validate(self):
        """Validate that the ContextField is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(u'Expected Location location, got: {} {}'.format(
                type(self.location).__name__, self.location))

        if not is_graphql_type(self.field_type):
            raise ValueError(u'Invalid value of "field_type": {}'.format(self.field_type))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this ContextField."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        validate_safe_string(mark_name)

        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = '@class'
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(u'The SQL backend does not support meta field {}.'.format(
                field_name))

        if field_name is None:
            return u'$matched.%s' % (mark_name,)
        else:
            validate_safe_or_special_string(field_name)
            return u'$matched.%s.%s' % (mark_name, field_name)

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()

        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = '@class'
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(u'The SQL backend does not support meta field {}.'.format(
                field_name))

        if field_name is not None:
            validate_safe_or_special_string(field_name)
            if '@' in field_name:
                template = u'm.{mark_name}[\'{field_name}\']'
            else:
                template = u'm.{mark_name}.{field_name}'
        else:
            template = u'm.{mark_name}'

        validate_safe_string(mark_name)

        return template.format(mark_name=mark_name, field_name=field_name)

    def to_cypher(self):
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()

        if field_name is not None:
            validate_safe_string(field_name)
            template = u'{mark_name}.{field_name}'
        else:
            template = u'{mark_name}'

        validate_safe_string(mark_name)

        return template.format(mark_name=mark_name, field_name=field_name)

    def to_sql(self, aliases, current_alias):
        """Return a sqlalchemy Column picked from the appropriate alias."""
        self.validate()

        if isinstance(self.field_type, GraphQLList):
            raise NotImplementedError(u'The SQL backend does not support lists. Cannot '
                                      u'process field {}.'.format(self.location.field))

        if self.location.field is not None:
            # Meta fields are special cases; assume all meta fields are not implemented.
            if self.location.field in ALL_SUPPORTED_META_FIELDS:
                raise NotImplementedError(u'The SQL backend does not support meta field {}.'.format(
                    self.location.field))
            return aliases[(self.location.at_vertex().query_path, None)].c[self.location.field]
        else:
            raise AssertionError(u'This is a bug. The SQL backend does not use '
                                 u'context fields to point to vertices.')


class OutputContextField(Expression):
    """A field used in ConstructResult blocks to output data from the global context."""

    __slots__ = ('location', 'field_type')

    def __init__(self, location, field_type):
        """Construct a new OutputContextField object for the field at the given location.

        Args:
            location: Location, specifying where the field was declared. The Location
                      must point to a property, and that property's value is output as the result.
            field_type: GraphQL type object, specifying the type of the field being output

        Returns:
            new OutputContextField object
        """
        super(OutputContextField, self).__init__(location, field_type)
        self.location = location
        self.field_type = field_type
        self.validate()

    def validate(self):
        """Validate that the OutputContextField is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(u'Expected Location location, got: {} {}'.format(
                type(self.location).__name__, self.location))

        if not self.location.field:
            raise ValueError(u'Expected Location object that points to a field, got: '
                             u'{}'.format(self.location))

        if not is_graphql_type(self.field_type):
            raise ValueError(u'Invalid value of "field_type": {}'.format(self.field_type))

        stripped_field_type = strip_non_null_from_type(self.field_type)
        if isinstance(stripped_field_type, GraphQLList):
            inner_type = strip_non_null_from_type(stripped_field_type.of_type)
            if GraphQLDate.is_same_type(inner_type) or GraphQLDateTime.is_same_type(inner_type):
                # This is a compilation error rather than a ValueError as
                # it can be caused by an invalid GraphQL query on an otherwise valid schema.
                # In other words, it's an error in writing the GraphQL query, rather than
                # a programming error within the library.
                raise GraphQLCompilationError(
                    u'Lists of Date or DateTime cannot currently be represented as '
                    u'OutputContextField objects: {}'.format(self.field_type))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = '@class'
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(u'The SQL backend does not support meta field {}.'.format(
                field_name))
        validate_safe_string(mark_name)
        validate_safe_or_special_string(field_name)

        stripped_field_type = strip_non_null_from_type(self.field_type)
        if GraphQLDate.is_same_type(stripped_field_type):
            return u'%s.%s.format("%s")' % (mark_name, field_name, STANDARD_DATE_FORMAT)
        elif GraphQLDateTime.is_same_type(stripped_field_type):
            return u'%s.%s.format("%s")' % (mark_name, field_name, STANDARD_DATETIME_FORMAT)
        else:
            return u'%s.%s' % (mark_name, field_name)

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        validate_safe_string(mark_name)
        validate_safe_or_special_string(field_name)

        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = '@class'
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(u'The SQL backend does not support meta field {}.'.format(
                field_name))

        if '@' in field_name:
            template = u'm.{mark_name}[\'{field_name}\']'
        else:
            template = u'm.{mark_name}.{field_name}'

        format_value = None
        stripped_field_type = strip_non_null_from_type(self.field_type)
        if GraphQLDate.is_same_type(stripped_field_type):
            template += '.format("{format}")'
            format_value = STANDARD_DATE_FORMAT
        elif GraphQLDateTime.is_same_type(stripped_field_type):
            template += '.format("{format}")'
            format_value = STANDARD_DATETIME_FORMAT

        return template.format(mark_name=mark_name, field_name=field_name,
                               format=format_value)

    def to_cypher(self):
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        validate_safe_string(mark_name)
        validate_safe_string(field_name)

        template = u'{mark_name}.{field_name}'

        return template.format(mark_name=mark_name, field_name=field_name)

    def to_sql(self, aliases, current_alias):
        """Return a sqlalchemy Column picked from the appropriate alias."""
        if isinstance(self.field_type, GraphQLList):
            raise NotImplementedError(u'The SQL backend does not support lists. Cannot '
                                      u'output field {}.'.format(self.location.field))

        # Meta fields are special cases; assume all meta fields are not implemented.
        if self.location.field in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(u'The sql backend does not support meta field {}.'.format(
                self.location.field))

        return aliases[(self.location.at_vertex().query_path, None)].c[self.location.field]

    def __eq__(self, other):
        """Return True if the given object is equal to this one, and False otherwise."""
        # Since this object has a GraphQL type as a variable, which doesn't implement
        # the equality operator, we have to override equality and call is_same_type() here.
        return (type(self) == type(other) and
                self.location == other.location and
                self.field_type.is_same_type(other.field_type))

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)


class FoldedContextField(Expression):
    """An expression used to output data captured in a @fold scope."""

    __slots__ = ('fold_scope_location', 'field_type')

    def __init__(self, fold_scope_location, field_type):
        """Construct a new FoldedContextField object for this folded field.

        Args:
            fold_scope_location: FoldScopeLocation specifying the location of
                                 the context field being output.
            field_type: GraphQL type object, specifying the type of the field being output.
                        Since the field is folded, this must be a GraphQLList of some kind.

        Returns:
            new FoldedContextField object
        """
        super(FoldedContextField, self).__init__(fold_scope_location, field_type)
        self.fold_scope_location = fold_scope_location
        self.field_type = field_type
        self.validate()

    def validate(self):
        """Validate that the FoldedContextField is correctly representable."""
        if not isinstance(self.fold_scope_location, FoldScopeLocation):
            raise TypeError(u'Expected FoldScopeLocation fold_scope_location, got: {} {}'.format(
                type(self.fold_scope_location), self.fold_scope_location))

        if self.fold_scope_location.field is None:
            raise ValueError(u'Expected FoldScopeLocation at a field, but got: {}'
                             .format(self.fold_scope_location))

        if self.fold_scope_location.field == COUNT_META_FIELD_NAME:
            if not GraphQLInt.is_same_type(self.field_type):
                raise TypeError(u'Expected the _x_count meta-field to be of GraphQLInt type, but '
                                u'encountered type {} instead: {}'
                                .format(self.field_type, self.fold_scope_location))
        else:
            if not isinstance(self.field_type, GraphQLList):
                raise ValueError(u'Invalid value of "field_type" for a field that is not '
                                 u'a meta-field, expected a list type but got: {} {}'
                                 .format(self.field_type, self.fold_scope_location))

            inner_type = strip_non_null_from_type(self.field_type.of_type)
            if isinstance(inner_type, GraphQLList):
                raise GraphQLCompilationError(
                    u'Outputting list-valued fields in a @fold context is currently not supported: '
                    u'{} {}'.format(self.fold_scope_location, self.field_type.of_type))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this expression."""
        self.validate()

        mark_name, field_name = self.fold_scope_location.get_location_name()
        validate_safe_string(mark_name)

        template = u'$%(mark_name)s.%(field_name)s'
        template_data = {
            'mark_name': mark_name,
        }

        if field_name == COUNT_META_FIELD_NAME:
            template_data['field_name'] = 'size()'
        else:
            inner_type = strip_non_null_from_type(self.field_type.of_type)
            if GraphQLDate.is_same_type(inner_type):
                # Known OrientDB bug may cause trouble here, and incorrect data may be returned:
                # https://github.com/orientechnologies/orientdb/issues/7289
                template += '.format("' + STANDARD_DATE_FORMAT + '")'
            elif GraphQLDateTime.is_same_type(inner_type):
                # Known OrientDB bug may cause trouble here, and incorrect data may be returned:
                # https://github.com/orientechnologies/orientdb/issues/7289
                template += '.format("' + STANDARD_DATETIME_FORMAT + '")'

            template_data['field_name'] = field_name

        return template % template_data

    def to_gremlin(self):
        """Not implemented, should not be used."""
        raise AssertionError(u'FoldedContextField are not used during the query emission process '
                             u'in Gremlin, so this is a bug. This function should not be called.')

    def to_cypher(self):
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        _, field_name = self.fold_scope_location.get_location_name()
        mark_name = cypher_helpers.get_collected_vertex_list_name(
            cypher_helpers.get_fold_scope_location_full_path_name(self.fold_scope_location))
        validate_safe_string(mark_name)

        template = u'[x IN {mark_name} | x.{field_name}]'

        if field_name == COUNT_META_FIELD_NAME:
            raise NotImplementedError()

        return template.format(mark_name=mark_name, field_name=field_name)

    def to_sql(self, aliases, current_alias):
        """Return a sqlalchemy Column picked from the appropriate alias."""
        # get the type of the folded field
        inner_type = strip_non_null_from_type(self.field_type.of_type)
        if GraphQLInt.is_same_type(inner_type):
            sql_array_type = 'INT'
        elif GraphQLString.is_same_type(inner_type):
            sql_array_type = 'VARCHAR'
        else:
            raise NotImplementedError('Type {} not implemented for outputs inside a fold.'.format(
                inner_type
            ))

        # coalesce to an empty array of the corresponding type
        empty_array = 'ARRAY[]::{}[]'.format(sql_array_type)
        return sqlalchemy.func.coalesce(
            aliases[
                self.fold_scope_location.base_location.query_path,
                self.fold_scope_location.fold_path
            ].c['fold_output_' + self.fold_scope_location.field],
            sqlalchemy.literal_column(empty_array)
        )

    def __eq__(self, other):
        """Return True if the given object is equal to this one, and False otherwise."""
        # Since this object has a GraphQL type as a variable, which doesn't implement
        # the equality operator, we have to override equality and call is_same_type() here.
        return (type(self) == type(other) and
                self.fold_scope_location == other.fold_scope_location and
                self.field_type.is_same_type(other.field_type))

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)


class FoldCountContextField(Expression):
    """An expression used to output the number of elements captured in a @fold scope."""

    __slots__ = ('fold_scope_location',)

    def __init__(self, fold_scope_location):
        """Construct a new FoldCountContextField object for this fold.

        Args:
            fold_scope_location: FoldScopeLocation specifying the fold whose size is being output.

        Returns:
            new FoldCountContextField object
        """
        super(FoldCountContextField, self).__init__(fold_scope_location)
        self.fold_scope_location = fold_scope_location
        self.validate()

    def validate(self):
        """Validate that the FoldCountContextField is correctly representable."""
        if not isinstance(self.fold_scope_location, FoldScopeLocation):
            raise TypeError(u'Expected FoldScopeLocation fold_scope_location, got: {} {}'.format(
                type(self.fold_scope_location), self.fold_scope_location))

        if self.fold_scope_location.field != COUNT_META_FIELD_NAME:
            raise AssertionError(u'Unexpected field in the FoldScopeLocation of this '
                                 u'FoldCountContextField object: {} {}'
                                 .format(self.fold_scope_location, self))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this expression."""
        self.validate()

        mark_name, _ = self.fold_scope_location.get_location_name()
        validate_safe_string(mark_name)

        template = u'$%(mark_name)s.size()'
        template_data = {
            'mark_name': mark_name,
        }
        return template % template_data

    def to_gremlin(self):
        """Not supported yet."""
        raise NotImplementedError()

    def to_cypher(self):
        """Not supported yet."""
        raise NotImplementedError()

    def to_sql(self, aliases, current_alias):
        """Not supported yet."""
        raise NotImplementedError(u'The SQL backend does not support _x_count.')


class ContextFieldExistence(Expression):
    """An expression that evaluates to True if the given context field exists, and False otherwise.

    Useful to determine whether e.g. a field at the end of an optional edge is defined or not.
    """

    __slots__ = ('location',)

    def __init__(self, location):
        """Construct a new ContextFieldExistence object for a vertex field from the global context.

        Args:
            location: Location, specifying where the field was declared. Must point to a vertex.

        Returns:
            new ContextFieldExistence expression which evaluates to True iff the vertex exists
        """
        super(ContextFieldExistence, self).__init__(location)
        self.location = location
        self.validate()

    def validate(self):
        """Validate that the ContextFieldExistence is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(u'Expected Location location, got: {} {}'.format(
                type(self.location).__name__, self.location))

        if self.location.field:
            raise ValueError(u'Expected location to point to a vertex, '
                             u'but found a field: {}'.format(self.location))

    def to_match(self):
        """Must not be used -- ContextFieldExistence must be lowered during the IR lowering step."""
        raise AssertionError(u'ContextFieldExistence.to_match() was called: {}'.format(self))

    def to_gremlin(self):
        """Must not be used -- ContextFieldExistence must be lowered during the IR lowering step."""
        raise AssertionError(u'ContextFieldExistence.to_gremlin() was called: {}'.format(self))

    def to_cypher(self):
        """Must not be used -- ContextFieldExistence must be lowered during the IR lowering step."""
        raise AssertionError(u'ContextFieldExistence.to_cypher() was called: {}'.format(self))

    def to_sql(self, aliases, current_alias):
        """Must not be used -- ContextFieldExistence must be lowered during the IR lowering step."""
        raise AssertionError(u'ContextFieldExistence.to_sql() was called: {}'.format(self))


def _validate_operator_name(operator, supported_operators):
    """Ensure the named operator is valid and supported."""
    if not isinstance(operator, six.text_type):
        raise TypeError(u'Expected operator as unicode string, got: {} {}'.format(
            type(operator).__name__, operator))

    if operator not in supported_operators:
        raise GraphQLCompilationError(u'Unrecognized operator: {}'.format(operator))


class UnaryTransformation(Expression):
    """An expression that modifies an underlying expression with a unary operator."""

    SUPPORTED_OPERATORS = frozenset({u'size'})

    __slots__ = ('operator', 'inner_expression')

    def __init__(self, operator, inner_expression):
        """Construct a UnaryExpression that modifies the given inner expression."""
        super(UnaryTransformation, self).__init__(operator, inner_expression)
        self.operator = operator
        self.inner_expression = inner_expression

    def validate(self):
        """Validate that the UnaryTransformation is correctly representable."""
        _validate_operator_name(self.operator, UnaryTransformation.SUPPORTED_OPERATORS)

        if not isinstance(self.inner_expression, Expression):
            raise TypeError(u'Expected Expression inner_expression, got {} {}'.format(
                type(self.inner_expression).__name__, self.inner_expression))

    def visit_and_update(self, visitor_fn):
        """Create an updated version (if needed) of UnaryTransformation via the visitor pattern."""
        new_inner = self.inner_expression.visit_and_update(visitor_fn)

        if new_inner is not self.inner_expression:
            return visitor_fn(UnaryTransformation(self.operator, new_inner))
        else:
            return visitor_fn(self)

    def to_match(self):
        """Return a unicode object with the MATCH representation of this UnaryTransformation."""
        self.validate()

        translation_table = {
            u'size': u'size()',
        }
        match_operator = translation_table.get(self.operator)
        if not match_operator:
            raise AssertionError(u'Unrecognized operator used: '
                                 u'{} {}'.format(self.operator, self))

        template = u'%(inner)s.%(operator)s'
        args = {
            'inner': self.inner_expression.to_match(),
            'operator': match_operator,
        }
        return template % args

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        translation_table = {
            u'size': u'count()',
        }
        gremlin_operator = translation_table.get(self.operator)
        if not gremlin_operator:
            raise AssertionError(u'Unrecognized operator used: '
                                 u'{} {}'.format(self.operator, self))

        template = u'{inner}.{operator}'
        args = {
            'inner': self.inner_expression.to_gremlin(),
            'operator': gremlin_operator,
        }
        return template.format(**args)

    def to_cypher(self):
        """Not implemented yet."""
        raise NotImplementedError()

    def to_sql(self, aliases, current_alias):
        """Not implemented yet."""
        raise NotImplementedError(u'Unary operators are not implemented in the SQL backend.')


class BinaryComposition(Expression):
    """An expression created by composing two expressions together."""

    SUPPORTED_OPERATORS = frozenset({
        u'=', u'!=', u'>=', u'<=', u'>', u'<', u'+', u'||', u'&&',
        u'contains', u'not_contains', u'intersects', u'has_substring', u'starts_with',
        u'ends_with', u'LIKE', u'INSTANCEOF',
    })

    __slots__ = ('operator', 'left', 'right')

    def __init__(self, operator, left, right):
        """Construct an expression that connects two expressions with an operator.

        Args:
            operator: unicode, specifying where the field was declared
            left: Expression on the left side of the binary operator
            right: Expression on the right side of the binary operator

        Returns:
            new BinaryComposition object
        """
        super(BinaryComposition, self).__init__(operator, left, right)
        self.operator = operator
        self.left = left
        self.right = right
        self.validate()

    def validate(self):
        """Validate that the BinaryComposition is correctly representable."""
        _validate_operator_name(self.operator, BinaryComposition.SUPPORTED_OPERATORS)

        if not isinstance(self.left, Expression):
            raise TypeError(u'Expected Expression left, got: {} {} {}'.format(
                type(self.left).__name__, self.left, self))

        if not isinstance(self.right, Expression):
            raise TypeError(u'Expected Expression right, got: {} {}'.format(
                type(self.right).__name__, self.right))

    def visit_and_update(self, visitor_fn):
        """Create an updated version (if needed) of BinaryComposition via the visitor pattern."""
        new_left = self.left.visit_and_update(visitor_fn)
        new_right = self.right.visit_and_update(visitor_fn)

        if new_left is not self.left or new_right is not self.right:
            return visitor_fn(BinaryComposition(self.operator, new_left, new_right))
        else:
            return visitor_fn(self)

    def to_match(self):
        """Return a unicode object with the MATCH representation of this BinaryComposition."""
        self.validate()

        # The MATCH versions of some operators require an inverted order of arguments.
        # pylint: disable=unused-variable
        regular_operator_format = '(%(left)s %(operator)s %(right)s)'
        inverted_operator_format = '(%(right)s %(operator)s %(left)s)'  # noqa
        intersects_operator_format = '(%(operator)s(%(left)s, %(right)s).asList().size() > 0)'
        negated_regular_operator_format = '(NOT (%(left)s %(operator)s %(right)s))'
        # pylint: enable=unused-variable

        # Comparing null to a value does not make sense.
        if self.left == NullLiteral:
            raise AssertionError(u'The left expression cannot be a NullLiteral! Received operator '
                                 u'{} and right expression {}.'.format(self.operator, self.right))
        # Null literals use the OrientDB 'IS/IS NOT' (in)equality operators,
        # while other values use the OrientDB '=/<>' operators.
        elif self.right == NullLiteral:
            translation_table = {
                u'=': (u'IS', regular_operator_format),
                u'!=': (u'IS NOT', regular_operator_format),
            }
        else:
            translation_table = {
                u'=': (u'=', regular_operator_format),
                u'!=': (u'<>', regular_operator_format),
                u'>=': (u'>=', regular_operator_format),
                u'<=': (u'<=', regular_operator_format),
                u'>': (u'>', regular_operator_format),
                u'<': (u'<', regular_operator_format),
                u'+': (u'+', regular_operator_format),
                u'||': (u'OR', regular_operator_format),
                u'&&': (u'AND', regular_operator_format),
                u'contains': (u'CONTAINS', regular_operator_format),
                u'not_contains': (u'CONTAINS', negated_regular_operator_format),
                u'intersects': (u'intersect', intersects_operator_format),
                u'has_substring': (None, None),  # must be lowered into compatible form using LIKE
                u'starts_with': (None, None),  # must be lowered into compatible form using LIKE
                u'ends_with': (None, None),  # must be lowered into compatibe form using LIKE
                # MATCH-specific operators
                u'LIKE': (u'LIKE', regular_operator_format),
                u'INSTANCEOF': (u'INSTANCEOF', regular_operator_format),
            }

        match_operator, format_spec = translation_table.get(self.operator, (None, None))
        if not match_operator:
            raise AssertionError(u'Unrecognized operator used: '
                                 u'{} {}'.format(self.operator, self))

        return format_spec % dict(operator=match_operator,
                                  left=self.left.to_match(),
                                  right=self.right.to_match())

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        immediate_operator_format = u'({left} {operator} {right})'
        dotted_operator_format = u'{left}.{operator}({right})'
        intersects_operator_format = u'(!{left}.{operator}({right}).empty)'
        negated_dotted_operator_format = u'!{left}.{operator}({right})'

        # Comparing null to a value does not make sense.
        if self.left == NullLiteral:
            raise AssertionError(
                u'The left expression cannot be a NullLiteral! Received operator '
                u'{} and right expression {}.'.format(self.operator, self.right))
        translation_table = {
            u'=': (u'==', immediate_operator_format),
            u'!=': (u'!=', immediate_operator_format),
            u'>=': (u'>=', immediate_operator_format),
            u'<=': (u'<=', immediate_operator_format),
            u'>': (u'>', immediate_operator_format),
            u'<': (u'<', immediate_operator_format),
            u'+': (u'+', immediate_operator_format),
            u'||': (u'||', immediate_operator_format),
            u'&&': (u'&&', immediate_operator_format),
            u'contains': (u'contains', dotted_operator_format),
            u'not_contains': (u'contains', negated_dotted_operator_format),
            u'intersects': (u'intersect', intersects_operator_format),
            u'has_substring': (u'contains', dotted_operator_format),
            u'starts_with': (u'startsWith', dotted_operator_format),
            u'ends_with': (u'endsWith', dotted_operator_format),
        }

        gremlin_operator, format_spec = translation_table.get(self.operator, (None, None))
        if not gremlin_operator:
            raise AssertionError(u'Unrecognized operator used: '
                                 u'{} {}'.format(self.operator, self))

        return format_spec.format(operator=gremlin_operator,
                                  left=self.left.to_gremlin(),
                                  right=self.right.to_gremlin())

    def to_cypher(self):
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        # The Cypher versions of some operators require an inverted order of arguments.
        regular_operator_format = u'({left} {operator} {right})'
        inverted_operator_format = u'({right} {operator} {left})'
        negated_inverted_operator_format = u'(NOT ({right} {operator} {left}))'
        intersects_operator_format = u'any(_ {operator} {left} WHERE _ {operator} {right})'

        # Comparing null to a value does not make sense.
        if self.left == NullLiteral:
            raise AssertionError(
                u'The left expression cannot be a NullLiteral! Received operator '
                u'{} and right expression {}.'.format(self.operator, self.right))
        # Null literals use 'is/is not' as (in)equality operators, while other values use '=/<>'.
        elif self.right == NullLiteral:
            translation_table = {
                u'=': (u'IS', regular_operator_format),
                u'!=': (u'IS NOT', regular_operator_format),
            }
        else:
            translation_table = {
                u'=': (u'=', regular_operator_format),
                u'!=': (u'<>', regular_operator_format),
                u'>=': (u'>=', regular_operator_format),
                u'<=': (u'<=', regular_operator_format),
                u'>': (u'>', regular_operator_format),
                u'<': (u'<', regular_operator_format),
                u'||': (u'OR', regular_operator_format),
                u'&&': (u'AND', regular_operator_format),
                u'contains': (u'IN', inverted_operator_format),
                u'not_contains': (u'IN', negated_inverted_operator_format),
                u'intersects': (u'IN', intersects_operator_format),
                u'has_substring': (u'CONTAINS', regular_operator_format),
                u'starts_with': (u'STARTS WITH', regular_operator_format),
                u'ends_with': (u'ENDS WITH', regular_operator_format),
            }

        cypher_operator, format_spec = translation_table.get(self.operator, (None, None))
        if not cypher_operator:
            raise AssertionError(u'Unrecognized operator used: '
                                 u'{} {}'.format(self.operator, self))

        return format_spec.format(operator=cypher_operator,
                                  left=self.left.to_cypher(),
                                  right=self.right.to_cypher())

    def to_sql(self, aliases, current_alias):
        """Return a sqlalchemy BinaryExpression representing this BinaryComposition."""
        self.validate()

        translation_table = {
            u'=': python_operator.__eq__,
            u'!=': python_operator.__ne__,
            u'<': python_operator.__lt__,
            u'>': python_operator.__gt__,
            u'<=': python_operator.__le__,
            u'>=': python_operator.__ge__,
            u'&&': sql.expression.and_,
            u'||': sql.expression.or_,
            u'has_substring': sql.operators.ColumnOperators.contains,
            u'starts_with': sql.operators.ColumnOperators.startswith,
            u'ends_with': sql.operators.ColumnOperators.endswith,
            # IR generation converts an in_collection filter in the query to a contains filter
            # in the IR. Because of this an implementation for in_collection and not_in_collection
            # is not needed.
            u'contains': sqlalchemy_extensions.contains_operator,
            u'not_contains': sqlalchemy_extensions.not_contains_operator,
        }
        if self.operator not in translation_table:
            raise NotImplementedError(u'The SQL backend does not support operator {}.'
                                      .format(self.operator))
        return translation_table[self.operator](
            self.left.to_sql(aliases, current_alias),
            self.right.to_sql(aliases, current_alias),
        )


class TernaryConditional(Expression):
    """A ternary conditional expression, returning one of two expressions depending on a third."""

    __slots__ = ('predicate', 'if_true', 'if_false')

    def __init__(self, predicate, if_true, if_false):
        """Construct an expression that evaluates a predicate and returns one of two results.

        Args:
            predicate: Expression to evaluate, and based on which to choose the returned value
            if_true: Expression to return if the predicate was true
            if_false: Expression to return if the predicate was false

        Returns:
            new TernaryConditional object
        """
        super(TernaryConditional, self).__init__(predicate, if_true, if_false)
        self.predicate = predicate
        self.if_true = if_true
        self.if_false = if_false
        self.validate()

    def validate(self):
        """Validate that the TernaryConditional is correctly representable."""
        if not isinstance(self.predicate, Expression):
            raise TypeError(u'Expected Expression predicate, got: {} {}'.format(
                type(self.predicate).__name__, self.predicate))
        if not isinstance(self.if_true, Expression):
            raise TypeError(u'Expected Expression if_true, got: {} {}'.format(
                type(self.if_true).__name__, self.if_true))
        if not isinstance(self.if_false, Expression):
            raise TypeError(u'Expected Expression if_false, got: {} {}'.format(
                type(self.if_false).__name__, self.if_false))

    def visit_and_update(self, visitor_fn):
        """Create an updated version (if needed) of TernaryConditional via the visitor pattern."""
        new_predicate = self.predicate.visit_and_update(visitor_fn)
        new_if_true = self.if_true.visit_and_update(visitor_fn)
        new_if_false = self.if_false.visit_and_update(visitor_fn)

        if any((new_predicate is not self.predicate,
                new_if_true is not self.if_true,
                new_if_false is not self.if_false)):
            return visitor_fn(TernaryConditional(new_predicate, new_if_true, new_if_false))
        else:
            return visitor_fn(self)

    def to_match(self):
        """Return a unicode object with the MATCH representation of this TernaryConditional."""
        self.validate()

        # For MATCH, an additional validation step is needed -- we currently do not support
        # emitting MATCH code for TernaryConditional that contains another TernaryConditional
        # anywhere within the predicate expression. This is because the predicate expression
        # must be surrounded in quotes, and it is unclear whether nested/escaped quotes would work.
        def visitor_fn(expression):
            """Visitor function that ensures the predicate does not contain TernaryConditionals."""
            if isinstance(expression, TernaryConditional):
                raise ValueError(u'Cannot emit MATCH code for TernaryConditional that contains '
                                 u'in its predicate another TernaryConditional: '
                                 u'{} {}'.format(expression, self))
            return expression

        self.predicate.visit_and_update(visitor_fn)

        format_spec = u'if(eval("%(predicate)s"), %(if_true)s, %(if_false)s)'
        predicate_string = self.predicate.to_match()
        if u'"' in predicate_string:
            raise AssertionError(u'Found a double-quote within the predicate string, this would '
                                 u'have terminated the if(eval()) early and should be fixed: '
                                 u'{} {}'.format(predicate_string, self))

        return format_spec % dict(predicate=predicate_string,
                                  if_true=self.if_true.to_match(),
                                  if_false=self.if_false.to_match())

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        return u'({predicate} ? {if_true} : {if_false})'.format(
            predicate=self.predicate.to_gremlin(),
            if_true=self.if_true.to_gremlin(),
            if_false=self.if_false.to_gremlin())

    def to_cypher(self):
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        return u'(CASE WHEN {predicate} THEN {if_true} ELSE {if_false} END)'.format(
            predicate=self.predicate.to_cypher(),
            if_true=self.if_true.to_cypher(),
            if_false=self.if_false.to_cypher())

    def to_sql(self, aliases, current_alias):
        """Return a sqlalchemy Case representing this TernaryConditional."""
        self.validate()
        sql_predicate = self.predicate.to_sql(aliases, current_alias)
        sql_if_true = self.if_true.to_sql(aliases, current_alias)
        sql_else = self.if_false.to_sql(aliases, current_alias)
        return sql.expression.case([(sql_predicate, sql_if_true)], else_=sql_else)
