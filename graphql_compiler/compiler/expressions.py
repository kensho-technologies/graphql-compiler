# Copyright 2017-present Kensho Technologies, LLC.
from graphql import GraphQLList, GraphQLNonNull
import six

from ..exceptions import GraphQLCompilationError
from ..schema import GraphQLDate, GraphQLDateTime
from .compiler_entities import Expression
from .helpers import (STANDARD_DATE_FORMAT, STANDARD_DATETIME_FORMAT, FoldScopeLocation, Location,
                      ensure_unicode_string, is_graphql_type, is_vertex_field_name,
                      safe_quoted_string, strip_non_null_from_type, validate_safe_string)


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
    u'$currentMatch'
})


class Literal(Expression):
    """A literal, such as a boolean value, null, or a fixed string value.

    We have to be extra careful with string literals -- for ease of escaping, we use
    json.dumps() to represent strings. However, we must then manually escape '$' characters
    as they trigger string interpolation in Groovy/Gremlin.
        http://docs.groovy-lang.org/latest/html/documentation/index.html#_string_interpolation

    Think long and hard about the above before allowing literals in user-supplied GraphQL!
    """

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
            validate_safe_string(self.value)
            return

        # Literal ints are correctly representable and supported.
        if isinstance(self.value, int):
            return

        # Literal empty lists, and non-empty lists of safe strings, are
        # correctly representable and supported.
        if isinstance(self.value, list):
            if len(self.value) > 0:
                for x in self.value:
                    validate_safe_string(x)
            return

        raise GraphQLCompilationError(u'Cannot represent literal: {}'.format(self.value))

    def _to_output_code(self):
        """Return a unicode object with the Gremlin/MATCH representation of this Literal."""
        # All supported Literal objects serialize to identical strings both in Gremlin and MATCH.
        self.validate()
        if self.value is None:
            return u'null'
        elif self.value is True:
            return u'true'
        elif self.value is False:
            return u'false'
        elif isinstance(self.value, six.string_types):
            return safe_quoted_string(self.value)
        elif isinstance(self.value, int):
            return six.text_type(self.value)
        elif isinstance(self.value, list):
            if len(self.value) == 0:
                return '[]'
            elif all(isinstance(x, six.string_types) for x in self.value):
                list_contents = ', '.join(safe_quoted_string(x) for x in sorted(self.value))
                return '[' + list_contents + ']'
        else:
            pass  # Fall through to assertion error below.
        raise AssertionError(u'Unreachable state reached: {}'.format(self))

    to_gremlin = _to_output_code
    to_match = _to_output_code


NullLiteral = Literal(None)
TrueLiteral = Literal(True)
FalseLiteral = Literal(False)
EmptyListLiteral = Literal([])
ZeroLiteral = Literal(0)


class Variable(Expression):
    """A variable for a parameterized query, to be filled in at runtime."""

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
        # We can't directly pass a Date or a DateTime object, so we have to pass it as a string
        # and then parse it inline. For date format parameter meanings, see:
        # http://docs.oracle.com/javase/7/docs/api/java/text/SimpleDateFormat.html
        if GraphQLDate.is_same_type(self.inferred_type):
            return u'Date.parse("{}", {})'.format(STANDARD_DATE_FORMAT, self.variable_name)
        elif GraphQLDateTime.is_same_type(self.inferred_type):
            return u'Date.parse("{}", {})'.format(STANDARD_DATETIME_FORMAT, self.variable_name)
        else:
            return six.text_type(self.variable_name)

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

    def __init__(self, field_name):
        """Construct a new LocalField object that references a field at the current position."""
        super(LocalField, self).__init__(field_name)
        self.field_name = field_name
        self.validate()

    def get_local_object_gremlin_name(self):
        """Return the Gremlin name of the local object whose field is being produced."""
        return u'it'

    def validate(self):
        """Validate that the LocalField is correctly representable."""
        validate_safe_string(self.field_name)

    def to_match(self):
        """Return a unicode object with the MATCH representation of this LocalField."""
        self.validate()
        return six.text_type(self.field_name)

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        local_object_name = self.get_local_object_gremlin_name()

        if self.field_name == '@this':
            return local_object_name

        if '@' in self.field_name:
            return u'{}[\'{}\']'.format(local_object_name, self.field_name)
        else:
            return u'{}.{}'.format(local_object_name, self.field_name)


class SelectEdgeContextField(Expression):
    """An edge field drawn from the global context, for use in a SELECT WHERE statement."""

    def __init__(self, location):
        """Construct a new SelectEdgeContextField object that references an edge field.

        Args:
            location: Location, specifying where the field was declared.
                      The Location object must contain an edge field.

        Returns:
            new SelectEdgeContextField object
        """
        super(SelectEdgeContextField, self).__init__(location)
        self.location = location
        self.validate()

    def validate(self):
        """Validate that the SelectEdgeContextField is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(u'Expected Location location, got: {} {}'
                            .format(type(self.location).__name__, self.location))

        if self.location.field is None:
            raise AssertionError(u'Received Location without a field: {}'
                                 .format(self.location))

        if not is_vertex_field_name(self.location.field):
            raise AssertionError(u'Received Location with a non-edge field: {}'
                                 .format(self.location))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this SelectEdgeContextField."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        validate_safe_string(mark_name)
        validate_safe_string(field_name)

        return u'%s.%s' % (mark_name, field_name)

    def to_gremlin(self):
        """Not implemented, should not be used."""
        raise AssertionError(u'SelectEdgeContextField is only used for the WHERE statement in '
                             u'MATCH. This function should not be called.')


class ContextField(Expression):
    """A field drawn from the global context, e.g. if selected earlier in the query."""

    def __init__(self, location):
        """Construct a new ContextField object that references a field from the global context.

        Args:
            location: Location, specifying where the field was declared. If the Location points
                      to a vertex, the field refers to the data captured at the location vertex.
                      Otherwise, if the Location points to a property, the field refers to
                      the particular value of that property.

        Returns:
            new ContextField object
        """
        super(ContextField, self).__init__(location)
        self.location = location
        self.validate()

    def validate(self):
        """Validate that the ContextField is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(u'Expected Location location, got: {} {}'.format(
                type(self.location).__name__, self.location))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this ContextField."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        validate_safe_string(mark_name)

        if field_name is None:
            return u'$matched.%s' % (mark_name,)
        else:
            validate_safe_string(field_name)
            return u'$matched.%s.%s' % (mark_name, field_name)

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()

        if field_name is not None:
            validate_safe_string(field_name)
            if '@' in field_name:
                template = u'm.{mark_name}[\'{field_name}\']'
            else:
                template = u'm.{mark_name}.{field_name}'
        else:
            template = u'm.{mark_name}'

        validate_safe_string(mark_name)

        return template.format(mark_name=mark_name, field_name=field_name)


class OutputContextField(Expression):
    """A field used in ConstructResult blocks to output data from the global context."""

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
        validate_safe_string(mark_name)
        validate_safe_string(field_name)

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
        validate_safe_string(field_name)

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


class FoldedOutputContextField(Expression):
    """An expression used to output data captured in a @fold scope."""

    def __init__(self, fold_scope_location, field_name, field_type):
        """Construct a new FoldedOutputContextField object for this folded field.

        Args:
            fold_scope_location: FoldScopeLocation specifying the start of the @fold scope
                                 where this output context field was captured.
            field_name: string, the name of the field being output.
            field_type: GraphQL type object, specifying the type of the field being output.
                        Since the field is folded, this must be a GraphQLList of some kind.

        Returns:
            new FoldedOutputContextField object
        """
        super(FoldedOutputContextField, self).__init__(fold_scope_location, field_name, field_type)
        self.fold_scope_location = fold_scope_location
        self.field_name = field_name
        self.field_type = field_type
        self.validate()

    def validate(self):
        """Validate that the FoldedOutputContextField is correctly representable."""
        if not isinstance(self.fold_scope_location, FoldScopeLocation):
            raise TypeError(u'Expected FoldScopeLocation fold_scope_location, got: {} {}'.format(
                type(self.fold_scope_location), self.fold_scope_location))

        validate_safe_string(self.field_name)

        if not isinstance(self.field_type, GraphQLList):
            raise ValueError(u'Invalid value of "field_type", expected a list type but got: '
                             u'{}'.format(self.field_type))

        inner_type = strip_non_null_from_type(self.field_type.of_type)
        if isinstance(inner_type, GraphQLList):
            raise GraphQLCompilationError(u'Outputting list-valued fields in a @fold context is '
                                          u'currently not supported: {} '
                                          u'{}'.format(self.field_name, self.field_type.of_type))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this expression."""
        self.validate()
        edge_direction, edge_name = self.fold_scope_location.relative_position

        mark_name = self.fold_scope_location.get_location_name()
        validate_safe_string(mark_name)

        template = u'$%(mark_name)s.%(field_name)s'

        inner_type = strip_non_null_from_type(self.field_type.of_type)
        if GraphQLDate.is_same_type(inner_type):
            # Known OrientDB bug may cause trouble here, and incorrect data may be returned:
            # https://github.com/orientechnologies/orientdb/issues/7289
            template += '.format("' + STANDARD_DATE_FORMAT + '")'
        elif GraphQLDateTime.is_same_type(inner_type):
            # Known OrientDB bug may cause trouble here, and incorrect data may be returned:
            # https://github.com/orientechnologies/orientdb/issues/7289
            template += '.format("' + STANDARD_DATETIME_FORMAT + '")'

        template_data = {
            'mark_name': mark_name,
            'direction': edge_direction,
            'edge_name': edge_name,
            'field_name': self.field_name,
        }
        return template % template_data

    def to_gremlin(self):
        """Must never be called."""
        raise NotImplementedError()

    def __eq__(self, other):
        """Return True if the given object is equal to this one, and False otherwise."""
        # Since this object has a GraphQL type as a variable, which doesn't implement
        # the equality operator, we have to override equality and call is_same_type() here.
        return (type(self) == type(other) and
                self.fold_scope_location == other.fold_scope_location and
                self.field_name == other.field_name and
                self.field_type.is_same_type(other.field_type))

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)


class ContextFieldExistence(Expression):
    """An expression that evaluates to True if the given context field exists, and False otherwise.

    Useful to determine whether e.g. a field at the end of an optional edge is defined or not.
    """

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


def _validate_operator_name(operator, supported_operators):
    """Ensure the named operator is valid and supported."""
    if not isinstance(operator, six.text_type):
        raise TypeError(u'Expected operator as unicode string, got: {} {}'.format(
            type(operator).__name__, operator))

    if operator not in supported_operators:
        raise GraphQLCompilationError(u'Unrecognized operator: {}'.format(operator))


class UnaryTransformation(Expression):
    """An expression that modifies an underlying expression with a unary operator."""

    SUPPORTED_OPERATORS = frozenset(
        {u'size'})

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


class BinaryComposition(Expression):
    """An expression created by composing two expressions together."""

    SUPPORTED_OPERATORS = frozenset(
        {u'=', u'!=', u'>=', u'<=', u'>', u'<', u'+', u'||', u'&&', u'contains', u'intersects',
         u'has_substring', u'LIKE', u'INSTANCEOF'})

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
            raise TypeError(u'Expected Expression left, got: {} {}'.format(
                type(self.left).__name__, self.left))

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
        # pylint: enable=unused-variable

        # Null literals use 'is/is not' as (in)equality operators, while other values use '=/<>'.
        if any((isinstance(self.left, Literal) and self.left.value is None,
                isinstance(self.right, Literal) and self.right.value is None)):
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
                u'intersects': (u'intersect', intersects_operator_format),
                u'has_substring': (None, None),  # must be lowered into compatible form using LIKE

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
            u'intersects': (u'intersect', intersects_operator_format),
            u'has_substring': (u'contains', dotted_operator_format),
        }

        gremlin_operator, format_spec = translation_table.get(self.operator, (None, None))
        if not gremlin_operator:
            raise AssertionError(u'Unrecognized operator used: '
                                 u'{} {}'.format(self.operator, self))

        return format_spec.format(operator=gremlin_operator,
                                  left=self.left.to_gremlin(),
                                  right=self.right.to_gremlin())


class TernaryConditional(Expression):
    """A ternary conditional expression, returning one of two expressions depending on a third."""

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
