# Copyright 2017-present Kensho Technologies, LLC.
"""Safely represent arguments for Gremlin-language GraphQL queries."""
import datetime
import json
from string import Template

import arrow
from graphql import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import six

from ..compiler import GREMLIN_LANGUAGE
from ..compiler.helpers import strip_non_null_from_type
from ..exceptions import GraphQLInvalidArgumentError
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from .representations import coerce_to_decimal, represent_float_as_str, type_check_and_str


def _safe_gremlin_string(value):
    """Sanitize and represent a string argument in Gremlin."""
    if not isinstance(value, six.string_types):
        if isinstance(value, bytes):  # should only happen in py3
            value = value.decode('utf-8')
        else:
            raise GraphQLInvalidArgumentError(u'Attempting to convert a non-string into a string: '
                                              u'{}'.format(value))

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
        raise AssertionError(u'Unreachable state reached: {} {}'.format(value, escaped_and_quoted))
    no_quotes = escaped_and_quoted[1:-1]
    re_escaped = no_quotes.replace('\\"', '"').replace('\'', '\\\'')

    final_escaped_value = '\'' + re_escaped + '\''
    return final_escaped_value


def _safe_gremlin_decimal(value):
    """Represent decimal objects as Gremlin strings."""
    decimal_value = coerce_to_decimal(value)

    # The "G" suffix on a decimal number forces it to be a BigInteger/BigDecimal literal:
    # http://docs.groovy-lang.org/next/html/documentation/core-syntax.html#_number_type_suffixes
    return str(decimal_value) + 'G'


def _safe_gremlin_date_and_datetime(graphql_type, expected_python_types, value):
    """Represent date and datetime objects as Gremlin strings."""
    # Python datetime.datetime is a subclass of datetime.date,
    # but in this case, the two are not interchangeable.
    # Rather than using isinstance, we will therefore check for exact type equality.
    value_type = type(value)
    if not any(value_type == x for x in expected_python_types):
        raise GraphQLInvalidArgumentError(u'Expected value to be exactly one of '
                                          u'python types {}, but was {}: '
                                          u'{}'.format(expected_python_types, value_type, value))

    # The serialize() method of GraphQLDate and GraphQLDateTime produces the correct
    # ISO-8601 format that Gremlin expects. We then simply represent it as a regular string.
    try:
        serialized_value = graphql_type.serialize(value)
    except ValueError as e:
        raise GraphQLInvalidArgumentError(e)

    return _safe_gremlin_string(serialized_value)


def _safe_gremlin_list(inner_type, argument_value):
    """Represent the list of "inner_type" objects in Gremlin form."""
    if not isinstance(argument_value, list):
        raise GraphQLInvalidArgumentError(u'Attempting to represent a non-list as a list: '
                                          u'{}'.format(argument_value))

    stripped_type = strip_non_null_from_type(inner_type)
    components = (
        _safe_gremlin_argument(stripped_type, x)
        for x in argument_value
    )
    return u'[' + u','.join(components) + u']'


def _safe_gremlin_argument(expected_type, argument_value):
    """Return a Gremlin string representing the given argument value."""
    if GraphQLString.is_same_type(expected_type):
        return _safe_gremlin_string(argument_value)
    elif GraphQLID.is_same_type(expected_type):
        # IDs can be strings or numbers, but the GraphQL library coerces them to strings.
        # We will follow suit and treat them as strings.
        if not isinstance(argument_value, six.string_types):
            if isinstance(argument_value, bytes):  # should only happen in py3
                argument_value = argument_value.decode('utf-8')
            else:
                argument_value = six.text_type(argument_value)
        return _safe_gremlin_string(argument_value)
    elif GraphQLFloat.is_same_type(expected_type):
        return represent_float_as_str(argument_value)
    elif GraphQLInt.is_same_type(expected_type):
        # Special case: in Python, isinstance(True, int) returns True.
        # Safeguard against this with an explicit check against bool type.
        if isinstance(argument_value, bool):
            raise GraphQLInvalidArgumentError(u'Attempting to represent a non-int as an int: '
                                              u'{}'.format(argument_value))

        return type_check_and_str(int, argument_value)
    elif GraphQLBoolean.is_same_type(expected_type):
        return type_check_and_str(bool, argument_value)
    elif GraphQLDecimal.is_same_type(expected_type):
        return _safe_gremlin_decimal(argument_value)
    elif GraphQLDate.is_same_type(expected_type):
        return _safe_gremlin_date_and_datetime(expected_type, (datetime.date,), argument_value)
    elif GraphQLDateTime.is_same_type(expected_type):
        return _safe_gremlin_date_and_datetime(expected_type,
                                               (datetime.datetime, arrow.Arrow), argument_value)
    elif isinstance(expected_type, GraphQLList):
        return _safe_gremlin_list(expected_type.of_type, argument_value)
    else:
        raise AssertionError(u'Could not safely represent the requested GraphQL type: '
                             u'{} {}'.format(expected_type, argument_value))


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
        arguments: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        string, a Gremlin query with inserted argument data
    """
    if compilation_result.language != GREMLIN_LANGUAGE:
        raise AssertionError(u'Unexpected query output language: {}'.format(compilation_result))

    base_query = compilation_result.query
    argument_types = compilation_result.input_metadata

    # The arguments are assumed to have already been validated against the query.
    sanitized_arguments = {
        key: _safe_gremlin_argument(argument_types[key], value)
        for key, value in six.iteritems(arguments)
    }

    return Template(base_query).substitute(sanitized_arguments)

######
