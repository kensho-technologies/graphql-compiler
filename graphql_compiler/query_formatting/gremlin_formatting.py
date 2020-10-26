# Copyright 2017-present Kensho Technologies, LLC.
"""Safely represent arguments for Gremlin-language GraphQL queries."""
import json
from string import Template

from graphql import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import six

from ..compiler import GREMLIN_LANGUAGE
from ..compiler.helpers import strip_non_null_from_type
from ..exceptions import GraphQLInvalidArgumentError
from ..global_utils import is_same_type
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from .representations import coerce_to_decimal, represent_float_as_str, type_check_and_str


def _safe_gremlin_string(value):
    """Sanitize and represent a string argument in Gremlin."""
    if not isinstance(value, six.string_types):
        if isinstance(value, bytes):  # likely to only happen in py2
            value = value.decode("utf-8")
        else:
            raise GraphQLInvalidArgumentError(
                "Attempting to convert a non-string into a string: {}".format(value)
            )

    # Using JSON encoding means that all unicode literals and special chars
    # (e.g. newlines and backslashes) are replaced by appropriate escape sequences.
    # However, the quoted result is wrapped in double quotes, and $ signs are not escaped,
    # so that would allow arbitrary code execution in Gremlin.
    # We will therefore turn the double-quoted string into a single-quoted one to avoid this risk.
    escaped_and_quoted = json.dumps(value)

    # Double-quoted string literals in Gremlin/Groovy allow
    # arbitrary code execution via string interpolation and closures.
    # To avoid this, we perform the following steps:
    #   - we strip the wrapping double quotes;
    #   - we un-escape any double-quotes in the string, by replacing \" with ";
    #   - we escape any single-quotes in the string, by replacing ' with \';
    #   - finally, we wrap the string in single quotes.
    # http://www.groovy-lang.org/syntax.html#_double_quoted_string
    if not escaped_and_quoted[0] == escaped_and_quoted[-1] == '"':
        raise AssertionError("Unreachable state reached: {} {}".format(value, escaped_and_quoted))
    no_quotes = escaped_and_quoted[1:-1]
    re_escaped = no_quotes.replace('\\"', '"').replace("'", "\\'")

    final_escaped_value = "'" + re_escaped + "'"
    return final_escaped_value


def _safe_gremlin_decimal(value):
    """Represent decimal objects as Gremlin strings."""
    decimal_value = coerce_to_decimal(value)

    # The "G" suffix on a decimal number forces it to be a BigInteger/BigDecimal literal:
    # http://docs.groovy-lang.org/next/html/documentation/core-syntax.html#_number_type_suffixes
    return str(decimal_value) + "G"


def _safe_gremlin_date(value):
    """Represent date objects as Gremlin strings."""
    try:
        serialized_value = GraphQLDate.serialize(value)
    except ValueError as e:
        raise GraphQLInvalidArgumentError(e)

    return _safe_gremlin_string(serialized_value)


def _safe_gremlin_datetime(value):
    """Represent datetime objects as Gremlin strings."""
    try:
        serialized_value = GraphQLDateTime.serialize(value)
    except ValueError as e:
        raise GraphQLInvalidArgumentError(e)

    return _safe_gremlin_string(serialized_value)


def _safe_gremlin_list(inner_type, argument_value):
    """Represent the list of "inner_type" objects in Gremlin form."""
    if not isinstance(argument_value, list):
        raise GraphQLInvalidArgumentError(
            "Attempting to represent a non-list as a list: {}".format(argument_value)
        )

    stripped_type = strip_non_null_from_type(inner_type)
    components = (_safe_gremlin_argument(stripped_type, x) for x in argument_value)
    return "[" + ",".join(components) + "]"


def _safe_gremlin_argument(expected_type, argument_value):
    """Return a Gremlin string representing the given argument value."""
    if is_same_type(GraphQLString, expected_type):
        return _safe_gremlin_string(argument_value)
    elif is_same_type(GraphQLID, expected_type):
        # IDs can be strings or numbers, but the GraphQL library coerces them to strings.
        # We will follow suit and treat them as strings.
        if not isinstance(argument_value, six.string_types):
            if isinstance(argument_value, bytes):  # likely to only happen in py2
                argument_value = argument_value.decode("utf-8")
            else:
                argument_value = six.text_type(argument_value)
        return _safe_gremlin_string(argument_value)
    elif is_same_type(GraphQLFloat, expected_type):
        return represent_float_as_str(argument_value)
    elif is_same_type(GraphQLInt, expected_type):
        # Special case: in Python, isinstance(True, int) returns True.
        # Safeguard against this with an explicit check against bool type.
        if isinstance(argument_value, bool):
            raise GraphQLInvalidArgumentError(
                "Attempting to represent a non-int as an int: {}".format(argument_value)
            )

        return type_check_and_str(int, argument_value)
    elif is_same_type(GraphQLBoolean, expected_type):
        return type_check_and_str(bool, argument_value)
    elif is_same_type(GraphQLDecimal, expected_type):
        return _safe_gremlin_decimal(argument_value)
    elif is_same_type(GraphQLDate, expected_type):
        return _safe_gremlin_date(argument_value)
    elif is_same_type(GraphQLDateTime, expected_type):
        return _safe_gremlin_datetime(argument_value)
    elif isinstance(expected_type, GraphQLList):
        return _safe_gremlin_list(expected_type.of_type, argument_value)
    else:
        raise AssertionError(
            "Could not safely represent the requested GraphQL type: "
            "{} {}".format(expected_type, argument_value)
        )


######
# Public API
######


def insert_arguments_into_gremlin_query(compilation_result, arguments):
    """Insert the arguments into the compiled Gremlin query to form a complete query.

    The GraphQL compiler attempts to use single-quoted string literals ('abc') in Gremlin output.
    Double-quoted strings allow inline interpolation with the $ symbol, see here for details:
    http://www.groovy-lang.org/syntax.html#all-strings

    If the compiler needs to emit a literal '$' character as part of the Gremlin query,
    it must be doubled ('$$') to avoid being interpreted as a query parameter.

    Args:
        compilation_result: a CompilationResult object derived from the GraphQL compiler
        arguments: dict, str -> any, mapping argument name to its value, for every parameter the
                   query expects.

    Returns:
        string, a Gremlin query with inserted argument data
    """
    if compilation_result.language != GREMLIN_LANGUAGE:
        raise AssertionError("Unexpected query output language: {}".format(compilation_result))

    base_query = compilation_result.query
    argument_types = compilation_result.input_metadata

    # The arguments are assumed to have already been validated against the query.
    sanitized_arguments = {
        key: _safe_gremlin_argument(argument_types[key], value)
        for key, value in six.iteritems(arguments)
    }

    return Template(base_query).substitute(sanitized_arguments)


######
