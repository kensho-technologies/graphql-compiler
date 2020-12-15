# Copyright 2017-present Kensho Technologies, LLC.
import operator as python_operator
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from graphql import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLString,
)
from graphql.type.definition import GraphQLOutputType
import six
import sqlalchemy
from sqlalchemy import bindparam, sql
from sqlalchemy.dialects.mssql.base import MSDialect
from sqlalchemy.dialects.postgresql.base import PGDialect

from . import cypher_helpers, sqlalchemy_extensions
from ..exceptions import GraphQLCompilationError
from ..global_utils import is_same_type
from ..schema import (
    ALL_SUPPORTED_META_FIELDS,
    COUNT_META_FIELD_NAME,
    TYPENAME_META_FIELD_NAME,
    GraphQLDate,
    GraphQLDateTime,
    GraphQLDecimal,
)
from .compiler_entities import AliasesDictType, AliasType, Expression
from .helpers import (
    STANDARD_DATE_FORMAT,
    STANDARD_DATETIME_FORMAT,
    FoldScopeLocation,
    Location,
    ensure_unicode_string,
    is_graphql_type,
    safe_or_special_quoted_string,
    strip_non_null_from_type,
    validate_safe_or_special_string,
    validate_safe_string,
)


# Since MATCH uses $-prefixed keywords to indicate special values,
# we must restrict those keywords from being used as variables.
# For consistency, we reserve these keywords in both Gremlin and MATCH.
RESERVED_MATCH_KEYWORDS = frozenset(
    {
        "$matches",
        "$matched",
        "$paths",
        "$elements",
        "$pathElements",
        "$depth",
        "$currentMatch",
    }
)


ExpressionT = TypeVar("ExpressionT", bound=Expression)
ReplacementExpressionT = TypeVar("ReplacementExpressionT", bound=Expression)
ReplacementT = Union[ExpressionT, ReplacementExpressionT]


def make_replacement_visitor(
    find_expression: Expression, replace_expression: ReplacementExpressionT
) -> Callable[[ExpressionT], ReplacementT]:
    """Return a visitor function that replaces every instance of one expression with another one."""

    def visitor_fn(expression: ExpressionT) -> ReplacementT:
        """Return the replacement if this expression matches the expression we're looking for."""
        if expression == find_expression:
            return replace_expression
        else:
            return expression

    return visitor_fn


def make_type_replacement_visitor(
    find_types: Union[Type[Expression], Tuple[Type[Expression], ...]],
    replacement_func: Callable[[ExpressionT], ReplacementT],
) -> Callable[[ExpressionT], ReplacementT]:
    """Return a visitor function that replaces expressions of a given type with new expressions."""

    def visitor_fn(expression: ExpressionT) -> ReplacementT:
        """Return a replacement expression if the original expression is of the correct type."""
        if isinstance(expression, find_types):
            return replacement_func(expression)
        else:
            return expression

    return visitor_fn


ValueT = TypeVar("ValueT")


class Literal(Generic[ValueT], Expression):
    """A literal, such as a boolean value, null, or a fixed string value.

    We have to be extra careful with string literals -- for ease of escaping, we use
    json.dumps() to represent strings. However, we must then manually escape '$' characters
    as they trigger string interpolation in Groovy/Gremlin.
        http://docs.groovy-lang.org/latest/html/documentation/index.html#_string_interpolation

    Think long and hard about the above before allowing literals in user-supplied GraphQL!
    """

    __slots__ = ("value",)

    def __init__(self, value: ValueT) -> None:
        """Construct a new Literal object with the given value."""
        super(Literal, self).__init__(value)
        self.value = value
        self.validate()

    def validate(self) -> None:
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

        raise GraphQLCompilationError("Cannot represent literal: {}".format(self.value))

    def _to_output_code(self) -> str:
        """Return a unicode object with the Gremlin/MATCH/Cypher representation of this Literal."""
        # All supported Literal objects serialize to identical strings
        # in all of Gremlin, Cypher, and MATCH.
        self.validate()
        if self.value is None:
            return "null"
        elif self.value is True:
            return "true"
        elif self.value is False:
            return "false"
        elif isinstance(self.value, six.string_types):
            return safe_or_special_quoted_string(self.value)
        elif isinstance(self.value, int):
            return six.text_type(self.value)
        elif isinstance(self.value, list):
            if len(self.value) == 0:
                return "[]"
            elif all(isinstance(x, six.string_types) for x in self.value):
                list_contents = ", ".join(
                    safe_or_special_quoted_string(x) for x in sorted(self.value)
                )
                return "[" + list_contents + "]"
        else:
            pass  # Fall through to assertion error below.
        raise AssertionError("Unreachable state reached: {}".format(self))

    to_gremlin = _to_output_code
    to_match = _to_output_code
    to_cypher = _to_output_code

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return the value."""
        self.validate()
        return self.value


NullLiteral = Literal(None)
TrueLiteral = Literal(True)
FalseLiteral = Literal(False)
EmptyListLiteral: Literal[List[Any]] = Literal([])
ZeroLiteral = Literal(0)


class Variable(Expression):
    """A variable for a parameterized query, to be filled in at runtime."""

    __slots__ = ("variable_name", "inferred_type")

    def __init__(self, variable_name: str, inferred_type: GraphQLOutputType) -> None:
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

    def validate(self) -> None:
        """Validate that the Variable is correctly representable."""
        # Get the first letter, or empty string if it doesn't exist.
        if not self.variable_name.startswith("$"):
            raise GraphQLCompilationError(
                "Expected variable name to start with $, but was: {}".format(self.variable_name)
            )

        if self.variable_name in RESERVED_MATCH_KEYWORDS:
            raise GraphQLCompilationError(
                "Cannot use reserved MATCH keyword {} as variable "
                "name!".format(self.variable_name)
            )

        validate_safe_string(self.variable_name[1:])

        if not is_graphql_type(self.inferred_type):
            raise ValueError('Invalid value of "inferred_type": {}'.format(self.inferred_type))

        if isinstance(self.inferred_type, GraphQLNonNull):
            raise ValueError(
                'GraphQL non-null types are not supported as "inferred_type": '
                "{}".format(self.inferred_type)
            )

        if isinstance(self.inferred_type, GraphQLList):
            inner_type = strip_non_null_from_type(self.inferred_type.of_type)
            if is_same_type(GraphQLDate, inner_type) or is_same_type(GraphQLDateTime, inner_type):
                # This is a compilation error rather than a ValueError as
                # it can be caused by an invalid GraphQL query on an otherwise valid schema.
                # In other words, it's an error in writing the GraphQL query, rather than
                # a programming error within the library.
                raise GraphQLCompilationError(
                    "Lists of Date or DateTime cannot currently be represented as "
                    "Variable objects: {}".format(self.inferred_type)
                )

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this Variable."""
        self.validate()

        # We don't want the dollar sign as part of the variable name.
        variable_with_no_dollar_sign = self.variable_name[1:]

        match_variable_name = "{%s}" % (six.text_type(variable_with_no_dollar_sign),)

        # We can't directly pass a Date or DateTime object, so we have to pass it as a string
        # and then parse it inline. For date format parameter meanings, see:
        # http://docs.oracle.com/javase/7/docs/api/java/text/SimpleDateFormat.html
        # For the semantics of the date() OrientDB SQL function, see:
        # http://orientdb.com/docs/last/SQL-Functions.html#date
        if is_same_type(GraphQLDate, self.inferred_type):
            return 'date(%s, "%s")' % (match_variable_name, STANDARD_DATE_FORMAT)
        elif is_same_type(GraphQLDateTime, self.inferred_type):
            return 'date(%s, "%s")' % (match_variable_name, STANDARD_DATETIME_FORMAT)
        else:
            return match_variable_name

    def to_gremlin(self) -> str:
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        # We can't directly pass a Date or a DateTime object, so we have to pass it as a string
        # and then parse it inline. For date format parameter meanings, see:
        # http://docs.oracle.com/javase/7/docs/api/java/text/SimpleDateFormat.html
        if is_same_type(GraphQLDate, self.inferred_type):
            return 'Date.parse("{}", {})'.format(STANDARD_DATE_FORMAT, self.variable_name)
        elif is_same_type(GraphQLDateTime, self.inferred_type):
            return 'Date.parse("{}", {})'.format(STANDARD_DATETIME_FORMAT, self.variable_name)
        else:
            return six.text_type(self.variable_name)

    def to_cypher(self) -> str:
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
        return "{}".format(self.variable_name)

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a sqlalchemy BindParameter."""
        self.validate()

        is_list = isinstance(self.inferred_type, GraphQLList)
        return bindparam(self.variable_name[1:], expanding=is_list)

    def __eq__(self, other: Any) -> bool:
        """Return True if the given object is equal to this one, and False otherwise."""
        # Since this object has a GraphQL type as a variable, which doesn't implement
        # the equality operator, we have to override equality and call is_same_type() here.
        return (
            type(self) == type(other)
            and self.variable_name == other.variable_name
            and is_same_type(self.inferred_type, other.inferred_type)
        )

    def __ne__(self, other: Any) -> bool:
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)


class LocalField(Expression):
    """A field at the current position in the query."""

    __slots__ = ("field_name", "field_type")

    def __init__(self, field_name: str, field_type: Optional[GraphQLOutputType]) -> None:
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

    def get_local_object_gremlin_name(self) -> str:
        """Return the Gremlin name of the local object whose field is being produced."""
        return "it"

    def validate(self) -> None:
        """Validate that the LocalField is correctly representable."""
        validate_safe_or_special_string(self.field_name)
        if self.field_type is not None and not is_graphql_type(self.field_type):
            raise ValueError('Invalid value {} of "field_type": {}'.format(self.field_type, self))

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this LocalField."""
        self.validate()

        if self.field_name == TYPENAME_META_FIELD_NAME:
            return six.text_type("@class")
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif self.field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The match backend does not support meta field {}.".format(self.field_name)
            )

        return six.text_type(self.field_name)

    def to_gremlin(self) -> str:
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        local_object_name = self.get_local_object_gremlin_name()

        if self.field_name == "@this":
            return local_object_name

        if self.field_name == TYPENAME_META_FIELD_NAME:
            return "{}['{}']".format(local_object_name, "@class")
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif self.field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The gremlin backend does not support meta field {}.".format(self.field_name)
            )

        if "@" in self.field_name:
            return "{}['{}']".format(local_object_name, self.field_name)
        else:
            return "{}.{}".format(local_object_name, self.field_name)

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a sqlalchemy Column picked from the current_alias."""
        self.validate()

        if isinstance(self.field_type, GraphQLList):
            raise NotImplementedError(
                "The SQL backend does not support lists. Cannot "
                "process field {}.".format(self.field_name)
            )

        # Meta fields are special cases; assume all meta fields are not implemented.
        if self.field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The SQL backend does not support meta field {}.".format(self.field_name)
            )

        return current_alias.c[self.field_name]

    def to_cypher(self) -> str:
        """Not implemented, should not be used."""
        raise AssertionError(
            "LocalField is not used as part of the query emission process in "
            "Cypher, so this is a bug. This function should not be called."
        )


class GlobalContextField(Expression):
    """A field drawn from the global context, for use in a global operations WHERE statement."""

    __slots__ = ("location", "field_type")

    def __init__(self, location: Location, field_type: GraphQLOutputType) -> None:
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

    def validate(self) -> None:
        """Validate that the GlobalContextField is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(
                "Expected Location location, got: {} {}".format(
                    type(self.location).__name__, self.location
                )
            )

        if self.location.field is None:
            raise AssertionError("Received Location without a field: {}".format(self.location))

        if not is_graphql_type(self.field_type):
            raise ValueError('Invalid value of "field_type": {}'.format(self.field_type))

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this GlobalContextField."""
        self.validate()

        mark_name, field_name = self.location.get_location_at_field_name()
        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = "@class"
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The match backend does not support meta field {}.".format(field_name)
            )
        validate_safe_string(mark_name)
        validate_safe_or_special_string(field_name)

        return "%s.%s" % (mark_name, field_name)

    def to_gremlin(self) -> str:
        """Not implemented, should not be used."""
        raise AssertionError(
            "GlobalContextField is only used for the WHERE statement in "
            "MATCH, so this is a bug. This function should not be called."
        )

    def to_cypher(self) -> str:
        """Not implemented, should not be used."""
        raise AssertionError(
            "GlobalContextField is not used as part of the query emission "
            "process in Cypher, so this is a bug. This function "
            "should not be called."
        )

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a sqlalchemy Column picked from the appropriate alias."""
        self.validate()
        if isinstance(self.field_type, GraphQLList):
            raise NotImplementedError(
                "The SQL backend does not support lists. Cannot "
                "process field {}.".format(self.location.field)
            )

        if self.location.field is not None:
            # Meta fields are special cases; assume all meta fields are not implemented.
            if self.location.field in ALL_SUPPORTED_META_FIELDS:
                raise NotImplementedError(
                    "The SQL backend does not support meta field {}.".format(self.location.field)
                )
            return aliases[(self.location.at_vertex().query_path, None)].c[self.location.field]
        else:
            raise AssertionError(
                "This is a bug. The SQL backend does not use "
                "global context fields to point to vertices. GlobalContextField "
                "at query_path {} and visit_counter {} did note have a valid "
                "field.".format(self.location.query_path, self.location.visit_counter)
            )


class ContextField(Expression):
    """A field drawn from the global context, e.g. if selected earlier in the query."""

    __slots__ = ("location", "field_type")

    def __init__(self, location: Location, field_type: GraphQLOutputType) -> None:
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

    def validate(self) -> None:
        """Validate that the ContextField is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(
                "Expected Location location, got: {} {}".format(
                    type(self.location).__name__, self.location
                )
            )

        if not is_graphql_type(self.field_type):
            raise ValueError('Invalid value of "field_type": {}'.format(self.field_type))

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this ContextField."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()
        validate_safe_string(mark_name)

        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = "@class"
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The match backend does not support meta field {}.".format(field_name)
            )

        if field_name is None:
            return "$matched.%s" % (mark_name,)
        else:
            validate_safe_or_special_string(field_name)
            return "$matched.%s.%s" % (mark_name, field_name)

    def to_gremlin(self) -> str:
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()

        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = "@class"
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The gremlin backend does not support meta field {}.".format(field_name)
            )

        if field_name is not None:
            validate_safe_or_special_string(field_name)
            if "@" in field_name:
                template = "m.{mark_name}['{field_name}']"
            else:
                template = "m.{mark_name}.{field_name}"
        else:
            template = "m.{mark_name}"

        validate_safe_string(mark_name)

        return template.format(mark_name=mark_name, field_name=field_name)

    def to_cypher(self) -> str:
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_name()

        if field_name is not None:
            validate_safe_string(field_name)
            template = "{mark_name}.{field_name}"
        else:
            template = "{mark_name}"

        validate_safe_string(mark_name)

        return template.format(mark_name=mark_name, field_name=field_name)

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a sqlalchemy Column picked from the appropriate alias."""
        self.validate()

        if isinstance(self.field_type, GraphQLList):
            raise NotImplementedError(
                "The SQL backend does not support lists. Cannot "
                "process field {}.".format(self.location.field)
            )

        if self.location.field is not None:
            # Meta fields are special cases; assume all meta fields are not implemented.
            if self.location.field in ALL_SUPPORTED_META_FIELDS:
                raise NotImplementedError(
                    "The SQL backend does not support meta field {}.".format(self.location.field)
                )
            return aliases[(self.location.at_vertex().query_path, None)].c[self.location.field]
        else:
            raise AssertionError(
                "This is a bug. The SQL backend does not use "
                "context fields to point to vertices."
            )


class OutputContextField(Expression):
    """A field used in ConstructResult blocks to output data from the global context."""

    __slots__ = ("location", "field_type")

    def __init__(self, location: Location, field_type: GraphQLOutputType) -> None:
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

    def validate(self) -> None:
        """Validate that the OutputContextField is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(
                "Expected Location location, got: {} {}".format(
                    type(self.location).__name__, self.location
                )
            )

        if not self.location.field:
            raise ValueError(
                "Expected Location object that points to a field, got: {}".format(self.location)
            )

        if not is_graphql_type(self.field_type):
            raise ValueError('Invalid value of "field_type": {}'.format(self.field_type))

        stripped_field_type = strip_non_null_from_type(self.field_type)
        if isinstance(stripped_field_type, GraphQLList):
            inner_type = strip_non_null_from_type(stripped_field_type.of_type)
            if is_same_type(GraphQLDate, inner_type) or is_same_type(GraphQLDateTime, inner_type):
                # This is a compilation error rather than a ValueError as
                # it can be caused by an invalid GraphQL query on an otherwise valid schema.
                # In other words, it's an error in writing the GraphQL query, rather than
                # a programming error within the library.
                raise GraphQLCompilationError(
                    "Lists of Date or DateTime cannot currently be represented as "
                    "OutputContextField objects: {}".format(self.field_type)
                )

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_at_field_name()
        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = "@class"
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The match backend does not support meta field {}.".format(field_name)
            )
        validate_safe_string(mark_name)
        validate_safe_or_special_string(field_name)

        stripped_field_type = strip_non_null_from_type(self.field_type)
        if is_same_type(GraphQLDate, stripped_field_type):
            return '%s.%s.format("%s")' % (mark_name, field_name, STANDARD_DATE_FORMAT)
        elif is_same_type(GraphQLDateTime, stripped_field_type):
            return '%s.%s.format("%s")' % (mark_name, field_name, STANDARD_DATETIME_FORMAT)
        else:
            return "%s.%s" % (mark_name, field_name)

    def to_gremlin(self) -> str:
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_at_field_name()
        validate_safe_string(mark_name)
        validate_safe_or_special_string(field_name)

        if field_name == TYPENAME_META_FIELD_NAME:
            field_name = "@class"
        # Meta fields are special cases; assume all meta fields are not implemented unless
        # otherwise specified.
        elif field_name in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The gremlin backend does not support meta field {}.".format(field_name)
            )

        if "@" in field_name:
            template = "m.{mark_name}['{field_name}']"
        else:
            template = "m.{mark_name}.{field_name}"

        format_value = None
        stripped_field_type = strip_non_null_from_type(self.field_type)
        if is_same_type(GraphQLDate, stripped_field_type):
            template += '.format("{format}")'
            format_value = STANDARD_DATE_FORMAT
        elif is_same_type(GraphQLDateTime, stripped_field_type):
            template += '.format("{format}")'
            format_value = STANDARD_DATETIME_FORMAT

        return template.format(mark_name=mark_name, field_name=field_name, format=format_value)

    def to_cypher(self) -> str:
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        mark_name, field_name = self.location.get_location_at_field_name()
        validate_safe_string(mark_name)
        validate_safe_string(field_name)

        template = "{mark_name}.{field_name}"

        return template.format(mark_name=mark_name, field_name=field_name)

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a SQLAlchemy Column picked from the appropriate alias."""
        if isinstance(self.field_type, GraphQLList):
            raise NotImplementedError(
                "The SQL backend does not support lists. Cannot "
                "output field {}.".format(self.location.field)
            )

        # Meta fields are special cases; assume all meta fields are not implemented.
        if self.location.field in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The SQL backend does not support meta field {}.".format(self.location.field)
            )

        return aliases[(self.location.at_vertex().query_path, None)].c[self.location.field]

    def __eq__(self, other: Any) -> bool:
        """Return True if the given object is equal to this one, and False otherwise."""
        # Since this object has a GraphQL type as a variable, which doesn't implement
        # the equality operator, we have to override equality and call is_same_type() here.
        return (
            type(self) == type(other)
            and self.location == other.location
            and is_same_type(self.field_type, other.field_type)
        )

    def __ne__(self, other: Any) -> bool:
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)


class FoldedContextField(Expression):
    """An expression used to output data captured in a @fold scope."""

    __slots__ = ("fold_scope_location", "field_type")

    def __init__(
        self, fold_scope_location: FoldScopeLocation, field_type: GraphQLList[GraphQLOutputType]
    ) -> None:
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

    @staticmethod
    def _get_sql_array_type(graphql_type: GraphQLOutputType) -> Optional[str]:
        """Convert folded field type to a corresponding SQL type."""
        # Extract inner type of the GraphQLList.
        inner_type = strip_non_null_from_type(graphql_type)
        graphql_type_to_sql_array_type_dict = {
            GraphQLInt: "BIGINT",
            GraphQLString: "VARCHAR",
            GraphQLID: "VARCHAR",
            GraphQLBoolean: "BOOL",
            GraphQLFloat: "DOUBLE PRECISION",
            GraphQLDate: "DATE",
            GraphQLDateTime: "TIMESTAMP",
            GraphQLDecimal: "DECIMAL",
        }
        for graphql_type, type_name in graphql_type_to_sql_array_type_dict.items():
            if is_same_type(graphql_type, inner_type):
                return type_name
        # If the graphql_type was not found, return None.
        return None

    def validate(self) -> None:
        """Validate that the FoldedContextField is correctly representable."""
        if not isinstance(self.fold_scope_location, FoldScopeLocation):
            raise TypeError(
                "Expected FoldScopeLocation fold_scope_location, got: {} {}".format(
                    type(self.fold_scope_location), self.fold_scope_location
                )
            )

        if self.fold_scope_location.field is None:
            raise ValueError(
                "Expected FoldScopeLocation at a field, but got: {}".format(
                    self.fold_scope_location
                )
            )

        if self.fold_scope_location.field == COUNT_META_FIELD_NAME:
            if not is_same_type(GraphQLInt, self.field_type):
                raise TypeError(
                    "Expected the _x_count meta-field to be of GraphQLInt type, but "
                    "encountered type {} instead: {}".format(
                        self.field_type, self.fold_scope_location
                    )
                )
        else:
            if not isinstance(self.field_type, GraphQLList):
                raise ValueError(
                    'Invalid value of "field_type" for a field that is not '
                    "a meta-field, expected a list type but got: {} {}".format(
                        self.field_type, self.fold_scope_location
                    )
                )

            inner_type = strip_non_null_from_type(self.field_type.of_type)
            if isinstance(inner_type, GraphQLList):
                raise GraphQLCompilationError(
                    "Outputting list-valued fields in a @fold context is currently not supported: "
                    "{} {}".format(self.fold_scope_location, self.field_type.of_type)
                )

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this expression."""
        self.validate()

        mark_name, field_name = self.fold_scope_location.get_location_at_field_name()
        validate_safe_string(mark_name)

        template = "$%(mark_name)s.%(field_name)s"
        template_data = {
            "mark_name": mark_name,
        }

        if field_name == COUNT_META_FIELD_NAME:
            template_data["field_name"] = "size()"
        else:
            inner_type = strip_non_null_from_type(self.field_type.of_type)
            if is_same_type(GraphQLDate, inner_type):
                # Known OrientDB bug may cause trouble here, and incorrect data may be returned:
                # https://github.com/orientechnologies/orientdb/issues/7289
                template += '.format("' + STANDARD_DATE_FORMAT + '")'
            elif is_same_type(GraphQLDateTime, inner_type):
                # Known OrientDB bug may cause trouble here, and incorrect data may be returned:
                # https://github.com/orientechnologies/orientdb/issues/7289
                template += '.format("' + STANDARD_DATETIME_FORMAT + '")'

            template_data["field_name"] = field_name

        return template % template_data

    def to_gremlin(self) -> str:
        """Not implemented, should not be used."""
        raise AssertionError(
            "FoldedContextField are not used during the query emission process "
            "in Gremlin, so this is a bug. This function should not be called."
        )

    def to_cypher(self) -> str:
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        _, field_name = self.fold_scope_location.get_location_name()
        mark_name = cypher_helpers.get_collected_vertex_list_name(
            cypher_helpers.get_fold_scope_location_full_path_name(self.fold_scope_location)
        )
        validate_safe_string(mark_name)

        template = "[x IN {mark_name} | x.{field_name}]"

        if field_name == COUNT_META_FIELD_NAME:
            raise NotImplementedError("_x_count is not implemented in the Cypher backend.")

        return template.format(mark_name=mark_name, field_name=field_name)

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a sqlalchemy Column picked from the appropriate alias."""
        if self.fold_scope_location.field is None:
            raise AssertionError(
                "Unreachable code reached, expected a location at a field "
                "but got {}: {}".format(self.fold_scope_location, self)
            )

        # _x_count is a special case that has already been coalesced to 0.
        # _x_count's intermediate output name is always fold_output__x_count
        if self.fold_scope_location.field == COUNT_META_FIELD_NAME:
            return aliases[
                self.fold_scope_location.base_location.query_path,
                self.fold_scope_location.fold_path,
            ].c["fold_output__x_count"]
        elif self.fold_scope_location.field in ALL_SUPPORTED_META_FIELDS:
            raise NotImplementedError(
                "The SQL backend does not support meta field {}.".format(
                    self.fold_scope_location.field
                )
            )

        fold_output_column = aliases[
            self.fold_scope_location.base_location.query_path, self.fold_scope_location.fold_path
        ].c["fold_output_" + self.fold_scope_location.field]

        if isinstance(dialect, MSDialect):
            # MSSQL
            return fold_output_column
        elif isinstance(dialect, PGDialect):
            # PostgreSQL
            # Coalesce to an empty array of the corresponding type.
            graphql_type = self.field_type.of_type
            sql_array_type = FoldedContextField._get_sql_array_type(graphql_type)
            if sql_array_type is None:
                raise NotImplementedError(
                    f"Type {graphql_type} not implemented for outputs inside a fold."
                )
            empty_array = "ARRAY[]::{}[]".format(sql_array_type)
            return sqlalchemy.func.coalesce(
                fold_output_column, sqlalchemy.literal_column(empty_array)
            )
        else:
            raise NotImplementedError(
                "Fold only supported for MSSQL and "
                "PostgreSQL, dialect was set to {}".format(dialect.name)
            )

    def __eq__(self, other: Any) -> bool:
        """Return True if the given object is equal to this one, and False otherwise."""
        # Since this object has a GraphQL type as a variable, which doesn't implement
        # the equality operator, we have to override equality and call is_same_type() here.
        return (
            type(self) == type(other)
            and self.fold_scope_location == other.fold_scope_location
            and is_same_type(self.field_type, other.field_type)
        )

    def __ne__(self, other: Any) -> bool:
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)


class FoldCountContextField(Expression):
    """An expression used to output the number of elements captured in a @fold scope."""

    __slots__ = ("fold_scope_location",)

    def __init__(self, fold_scope_location: FoldScopeLocation) -> None:
        """Construct a new FoldCountContextField object for this fold.

        Args:
            fold_scope_location: FoldScopeLocation specifying the fold whose size is being output.

        Returns:
            new FoldCountContextField object
        """
        super(FoldCountContextField, self).__init__(fold_scope_location)
        self.fold_scope_location = fold_scope_location
        self.validate()

    def validate(self) -> None:
        """Validate that the FoldCountContextField is correctly representable."""
        if not isinstance(self.fold_scope_location, FoldScopeLocation):
            raise TypeError(
                "Expected FoldScopeLocation fold_scope_location, got: {} {}".format(
                    type(self.fold_scope_location), self.fold_scope_location
                )
            )

        if self.fold_scope_location.field != COUNT_META_FIELD_NAME:
            raise AssertionError(
                "Unexpected field in the FoldScopeLocation of this "
                "FoldCountContextField object: {} {}".format(self.fold_scope_location, self)
            )

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this expression."""
        self.validate()

        mark_name, _ = self.fold_scope_location.get_location_name()
        validate_safe_string(mark_name)

        template = "$%(mark_name)s.size()"
        template_data = {
            "mark_name": mark_name,
        }
        return template % template_data

    def to_gremlin(self) -> str:
        """Not supported yet."""
        raise NotImplementedError("_x_count is not implemented in the Gremlin backend")

    def to_cypher(self) -> str:
        """Not supported yet."""
        raise NotImplementedError("_x_count is not implemented in the Cypher backend.")

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a SQLAlchemy column of a coalesced COUNT(*) from a folded subquery."""
        # _x_count's intermediate output name is always fold_output__x_count
        return aliases[
            self.fold_scope_location.base_location.query_path, self.fold_scope_location.fold_path
        ].c["fold_output__x_count"]


class ContextFieldExistence(Expression):
    """An expression that evaluates to True if the given context field exists, and False otherwise.

    Useful to determine whether e.g. a field at the end of an optional edge is defined or not.
    """

    __slots__ = ("location",)

    def __init__(self, location: Location) -> None:
        """Construct a new ContextFieldExistence object for a vertex field from the global context.

        Args:
            location: Location, specifying where the field was declared. Must point to a vertex.

        Returns:
            new ContextFieldExistence expression which evaluates to True iff the vertex exists
        """
        super(ContextFieldExistence, self).__init__(location)
        self.location = location
        self.validate()

    def validate(self) -> None:
        """Validate that the ContextFieldExistence is correctly representable."""
        if not isinstance(self.location, Location):
            raise TypeError(
                "Expected Location location, got: {} {}".format(
                    type(self.location).__name__, self.location
                )
            )

        if self.location.field:
            raise ValueError(
                "Expected location to point to a vertex, "
                "but found a field: {}".format(self.location)
            )

    def to_match(self) -> str:
        """Must not be used -- ContextFieldExistence must be lowered during the IR lowering step."""
        raise AssertionError("ContextFieldExistence.to_match() was called: {}".format(self))

    def to_gremlin(self) -> str:
        """Must not be used -- ContextFieldExistence must be lowered during the IR lowering step."""
        raise AssertionError("ContextFieldExistence.to_gremlin() was called: {}".format(self))

    def to_cypher(self) -> str:
        """Must not be used -- ContextFieldExistence must be lowered during the IR lowering step."""
        raise AssertionError("ContextFieldExistence.to_cypher() was called: {}".format(self))

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Must not be used -- ContextFieldExistence must be lowered during the IR lowering step."""
        raise AssertionError("ContextFieldExistence.to_sql() was called: {}".format(self))


def _validate_operator_name(operator: str, supported_operators: FrozenSet[str]) -> None:
    """Ensure the named operator is valid and supported."""
    if not isinstance(operator, six.text_type):
        raise TypeError(
            "Expected operator as unicode string, got: {} {}".format(
                type(operator).__name__, operator
            )
        )

    if operator not in supported_operators:
        raise GraphQLCompilationError("Unrecognized operator: {}".format(operator))


class UnaryTransformation(Expression):
    """An expression that modifies an underlying expression with a unary operator."""

    SUPPORTED_OPERATORS = frozenset({"size"})

    __slots__ = ("operator", "inner_expression")

    def __init__(self, operator: str, inner_expression: Expression) -> None:
        """Construct a UnaryExpression that modifies the given inner expression."""
        super(UnaryTransformation, self).__init__(operator, inner_expression)
        self.operator = operator
        self.inner_expression = inner_expression

    def validate(self) -> None:
        """Validate that the UnaryTransformation is correctly representable."""
        _validate_operator_name(self.operator, UnaryTransformation.SUPPORTED_OPERATORS)

        if not isinstance(self.inner_expression, Expression):
            raise TypeError(
                "Expected Expression inner_expression, got {} {}".format(
                    type(self.inner_expression).__name__, self.inner_expression
                )
            )

    def visit_and_update(self, visitor_fn: Callable[[Expression], ExpressionT]) -> ExpressionT:
        """Create an updated version (if needed) of UnaryTransformation via the visitor pattern."""
        new_inner = self.inner_expression.visit_and_update(visitor_fn)

        if new_inner is not self.inner_expression:
            return visitor_fn(UnaryTransformation(self.operator, new_inner))
        else:
            return visitor_fn(self)

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this UnaryTransformation."""
        self.validate()

        translation_table = {
            "size": "size()",
        }
        match_operator = translation_table.get(self.operator)
        if not match_operator:
            raise AssertionError("Unrecognized operator used: {} {}".format(self.operator, self))

        template = "%(inner)s.%(operator)s"
        args = {
            "inner": self.inner_expression.to_match(),
            "operator": match_operator,
        }
        return template % args

    def to_gremlin(self) -> str:
        """Return a unicode object with the Gremlin representation of this expression."""
        translation_table = {
            "size": "count()",
        }
        gremlin_operator = translation_table.get(self.operator)
        if not gremlin_operator:
            raise AssertionError("Unrecognized operator used: {} {}".format(self.operator, self))

        template = "{inner}.{operator}"
        args = {
            "inner": self.inner_expression.to_gremlin(),
            "operator": gremlin_operator,
        }
        return template.format(**args)

    def to_cypher(self) -> str:
        """Not implemented yet."""
        raise NotImplementedError("Unary operators are not implemented in the Cypher backend.")

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Not implemented yet."""
        raise NotImplementedError("Unary operators are not implemented in the SQL backend.")


class BinaryComposition(Expression):
    """An expression created by composing two expressions together."""

    SUPPORTED_OPERATORS = frozenset(
        {
            "=",
            "!=",
            ">=",
            "<=",
            ">",
            "<",
            "+",
            "||",
            "&&",
            "contains",
            "not_contains",
            "intersects",
            "has_substring",
            "starts_with",
            "ends_with",
            "LIKE",
            "INSTANCEOF",
        }
    )

    __slots__ = ("operator", "left", "right")

    def __init__(self, operator: str, left: Expression, right: Expression) -> None:
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

    def validate(self) -> None:
        """Validate that the BinaryComposition is correctly representable."""
        _validate_operator_name(self.operator, BinaryComposition.SUPPORTED_OPERATORS)

        if not isinstance(self.left, Expression):
            raise TypeError(
                "Expected Expression left, got: {} {} {}".format(
                    type(self.left).__name__, self.left, self
                )
            )

        if not isinstance(self.right, Expression):
            raise TypeError(
                "Expected Expression right, got: {} {}".format(
                    type(self.right).__name__, self.right
                )
            )

    def visit_and_update(self, visitor_fn: Callable[[Expression], ExpressionT]) -> ExpressionT:
        """Create an updated version (if needed) of BinaryComposition via the visitor pattern."""
        new_left = self.left.visit_and_update(visitor_fn)
        new_right = self.right.visit_and_update(visitor_fn)

        if new_left is not self.left or new_right is not self.right:
            return visitor_fn(BinaryComposition(self.operator, new_left, new_right))
        else:
            return visitor_fn(self)

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this BinaryComposition."""
        self.validate()

        # The MATCH versions of some operators require an inverted order of arguments.
        # pylint: disable=unused-variable
        regular_operator_format = "(%(left)s %(operator)s %(right)s)"
        inverted_operator_format = "(%(right)s %(operator)s %(left)s)"  # noqa
        intersects_operator_format = "(%(operator)s(%(left)s, %(right)s).asList().size() > 0)"
        negated_regular_operator_format = "(NOT (%(left)s %(operator)s %(right)s))"
        # pylint: enable=unused-variable

        translation_table: Dict[str, Union[Tuple[str, str], Tuple[None, None]]]

        # Comparing null to a value does not make sense.
        if self.left == NullLiteral:
            raise AssertionError(
                "The left expression cannot be a NullLiteral! Received operator "
                "{} and right expression {}.".format(self.operator, self.right)
            )
        # Null literals use the OrientDB 'IS/IS NOT' (in)equality operators,
        # while other values use the OrientDB '=/<>' operators.
        elif self.right == NullLiteral:
            translation_table = {
                "=": ("IS", regular_operator_format),
                "!=": ("IS NOT", regular_operator_format),
            }
        else:
            translation_table = {
                "=": ("=", regular_operator_format),
                "!=": ("<>", regular_operator_format),
                ">=": (">=", regular_operator_format),
                "<=": ("<=", regular_operator_format),
                ">": (">", regular_operator_format),
                "<": ("<", regular_operator_format),
                "+": ("+", regular_operator_format),
                "||": ("OR", regular_operator_format),
                "&&": ("AND", regular_operator_format),
                "contains": ("CONTAINS", regular_operator_format),
                "not_contains": ("CONTAINS", negated_regular_operator_format),
                "intersects": ("intersect", intersects_operator_format),
                "has_substring": (None, None),  # must be lowered into compatible form using LIKE
                "starts_with": (None, None),  # must be lowered into compatible form using LIKE
                "ends_with": (None, None),  # must be lowered into compatibe form using LIKE
                # MATCH-specific operators
                "LIKE": ("LIKE", regular_operator_format),
                "INSTANCEOF": ("INSTANCEOF", regular_operator_format),
            }

        match_operator, format_spec = translation_table.get(self.operator, (None, None))
        if not match_operator or not format_spec:
            raise AssertionError("Unrecognized operator used: {} {}".format(self.operator, self))

        return format_spec % dict(
            operator=match_operator, left=self.left.to_match(), right=self.right.to_match()
        )

    def to_gremlin(self) -> str:
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        immediate_operator_format = "({left} {operator} {right})"
        dotted_operator_format = "{left}.{operator}({right})"
        intersects_operator_format = "(!{left}.{operator}({right}).empty)"
        negated_dotted_operator_format = "!{left}.{operator}({right})"

        # Comparing null to a value does not make sense.
        if self.left == NullLiteral:
            raise AssertionError(
                "The left expression cannot be a NullLiteral! Received operator "
                "{} and right expression {}.".format(self.operator, self.right)
            )
        translation_table = {
            "=": ("==", immediate_operator_format),
            "!=": ("!=", immediate_operator_format),
            ">=": (">=", immediate_operator_format),
            "<=": ("<=", immediate_operator_format),
            ">": (">", immediate_operator_format),
            "<": ("<", immediate_operator_format),
            "+": ("+", immediate_operator_format),
            "||": ("||", immediate_operator_format),
            "&&": ("&&", immediate_operator_format),
            "contains": ("contains", dotted_operator_format),
            "not_contains": ("contains", negated_dotted_operator_format),
            "intersects": ("intersect", intersects_operator_format),
            "has_substring": ("contains", dotted_operator_format),
            "starts_with": ("startsWith", dotted_operator_format),
            "ends_with": ("endsWith", dotted_operator_format),
        }

        gremlin_operator, format_spec = translation_table.get(self.operator, (None, None))
        if not gremlin_operator or not format_spec:
            raise AssertionError("Unrecognized operator used: {} {}".format(self.operator, self))

        return format_spec.format(
            operator=gremlin_operator, left=self.left.to_gremlin(), right=self.right.to_gremlin()
        )

    def to_cypher(self) -> str:
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        # The Cypher versions of some operators require an inverted order of arguments.
        regular_operator_format = "({left} {operator} {right})"
        inverted_operator_format = "({right} {operator} {left})"
        negated_inverted_operator_format = "(NOT ({right} {operator} {left}))"
        intersects_operator_format = "any(_ {operator} {left} WHERE _ {operator} {right})"

        # Comparing null to a value does not make sense.
        if self.left == NullLiteral:
            raise AssertionError(
                "The left expression cannot be a NullLiteral! Received operator "
                "{} and right expression {}.".format(self.operator, self.right)
            )
        # Null literals use 'is/is not' as (in)equality operators, while other values use '=/<>'.
        elif self.right == NullLiteral:
            translation_table = {
                "=": ("IS", regular_operator_format),
                "!=": ("IS NOT", regular_operator_format),
            }
        else:
            translation_table = {
                "=": ("=", regular_operator_format),
                "!=": ("<>", regular_operator_format),
                ">=": (">=", regular_operator_format),
                "<=": ("<=", regular_operator_format),
                ">": (">", regular_operator_format),
                "<": ("<", regular_operator_format),
                "||": ("OR", regular_operator_format),
                "&&": ("AND", regular_operator_format),
                "contains": ("IN", inverted_operator_format),
                "not_contains": ("IN", negated_inverted_operator_format),
                "intersects": ("IN", intersects_operator_format),
                "has_substring": ("CONTAINS", regular_operator_format),
                "starts_with": ("STARTS WITH", regular_operator_format),
                "ends_with": ("ENDS WITH", regular_operator_format),
            }

        cypher_operator, format_spec = translation_table.get(self.operator, (None, None))
        if not cypher_operator or not format_spec:
            raise AssertionError("Unrecognized operator used: {} {}".format(self.operator, self))

        return format_spec.format(
            operator=cypher_operator, left=self.left.to_cypher(), right=self.right.to_cypher()
        )

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a sqlalchemy BinaryExpression representing this BinaryComposition."""
        self.validate()

        translation_table = {
            "=": python_operator.__eq__,
            "!=": python_operator.__ne__,
            "<": python_operator.__lt__,
            ">": python_operator.__gt__,
            "<=": python_operator.__le__,
            ">=": python_operator.__ge__,
            "&&": sql.expression.and_,
            "||": sql.expression.or_,
            "has_substring": sql.operators.ColumnOperators.contains,
            "starts_with": sql.operators.ColumnOperators.startswith,
            "ends_with": sql.operators.ColumnOperators.endswith,
            # IR generation converts an in_collection filter in the query to a contains filter
            # in the IR. Because of this an implementation for in_collection and not_in_collection
            # is not needed.
            "contains": sqlalchemy_extensions.contains_operator,
            "not_contains": sqlalchemy_extensions.not_contains_operator,
        }
        if self.operator not in translation_table:
            raise NotImplementedError(
                "The SQL backend does not support operator {}.".format(self.operator)
            )
        return translation_table[self.operator](
            self.left.to_sql(dialect, aliases, current_alias),
            self.right.to_sql(dialect, aliases, current_alias),
        )


class TernaryConditional(Expression):
    """A ternary conditional expression, returning one of two expressions depending on a third."""

    __slots__ = ("predicate", "if_true", "if_false")

    def __init__(self, predicate: Expression, if_true: Expression, if_false: Expression) -> None:
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

    def validate(self) -> None:
        """Validate that the TernaryConditional is correctly representable."""
        if not isinstance(self.predicate, Expression):
            raise TypeError(
                "Expected Expression predicate, got: {} {}".format(
                    type(self.predicate).__name__, self.predicate
                )
            )
        if not isinstance(self.if_true, Expression):
            raise TypeError(
                "Expected Expression if_true, got: {} {}".format(
                    type(self.if_true).__name__, self.if_true
                )
            )
        if not isinstance(self.if_false, Expression):
            raise TypeError(
                "Expected Expression if_false, got: {} {}".format(
                    type(self.if_false).__name__, self.if_false
                )
            )

    def visit_and_update(self, visitor_fn: Callable[[Expression], ExpressionT]) -> ExpressionT:
        """Create an updated version (if needed) of TernaryConditional via the visitor pattern."""
        new_predicate = self.predicate.visit_and_update(visitor_fn)
        new_if_true = self.if_true.visit_and_update(visitor_fn)
        new_if_false = self.if_false.visit_and_update(visitor_fn)

        if any(
            (
                new_predicate is not self.predicate,
                new_if_true is not self.if_true,
                new_if_false is not self.if_false,
            )
        ):
            return visitor_fn(TernaryConditional(new_predicate, new_if_true, new_if_false))
        else:
            return visitor_fn(self)

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this TernaryConditional."""
        self.validate()

        # For MATCH, an additional validation step is needed -- we currently do not support
        # emitting MATCH code for TernaryConditional that contains another TernaryConditional
        # anywhere within the predicate expression. This is because the predicate expression
        # must be surrounded in quotes, and it is unclear whether nested/escaped quotes would work.
        def visitor_fn(expression: ExpressionT) -> ExpressionT:
            """Visitor function that ensures the predicate does not contain TernaryConditionals."""
            if isinstance(expression, TernaryConditional):
                raise ValueError(
                    "Cannot emit MATCH code for TernaryConditional that contains "
                    "in its predicate another TernaryConditional: "
                    "{} {}".format(expression, self)
                )
            return expression

        self.predicate.visit_and_update(visitor_fn)

        format_spec = 'if(eval("%(predicate)s"), %(if_true)s, %(if_false)s)'
        predicate_string = self.predicate.to_match()
        if '"' in predicate_string:
            raise AssertionError(
                "Found a double-quote within the predicate string, this would "
                "have terminated the if(eval()) early and should be fixed: "
                "{} {}".format(predicate_string, self)
            )

        return format_spec % dict(
            predicate=predicate_string,
            if_true=self.if_true.to_match(),
            if_false=self.if_false.to_match(),
        )

    def to_gremlin(self) -> str:
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()

        return "({predicate} ? {if_true} : {if_false})".format(
            predicate=self.predicate.to_gremlin(),
            if_true=self.if_true.to_gremlin(),
            if_false=self.if_false.to_gremlin(),
        )

    def to_cypher(self) -> str:
        """Return a unicode object with the Cypher representation of this expression."""
        self.validate()

        return "(CASE WHEN {predicate} THEN {if_true} ELSE {if_false} END)".format(
            predicate=self.predicate.to_cypher(),
            if_true=self.if_true.to_cypher(),
            if_false=self.if_false.to_cypher(),
        )

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a sqlalchemy Case representing this TernaryConditional."""
        self.validate()
        sql_predicate = self.predicate.to_sql(dialect, aliases, current_alias)
        sql_if_true = self.if_true.to_sql(dialect, aliases, current_alias)
        sql_else = self.if_false.to_sql(dialect, aliases, current_alias)
        return sql.expression.case([(sql_predicate, sql_if_true)], else_=sql_else)
