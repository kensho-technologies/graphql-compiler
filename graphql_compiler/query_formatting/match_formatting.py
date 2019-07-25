# Copyright 2017-present Kensho Technologies, LLC.
"""Safely represent arguments for MATCH-language GraphQL queries."""
import datetime
import json

import arrow
from graphql import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import six

from ..compiler import MATCH_LANGUAGE
from ..compiler.helpers import strip_non_null_from_type
from ..exceptions import GraphQLInvalidArgumentError
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from .representations import coerce_to_decimal, represent_float_as_str, type_check_and_str


def _safe_match_string(value):
    """Sanitize and represent a string argument in MATCH."""
    if not isinstance(value, six.string_types):
        if isinstance(value, bytes):  # should only happen in py3
            value = value.decode('utf-8')
        else:
            raise GraphQLInvalidArgumentError(u'Attempting to convert a non-string into a string: '
                                              u'{}'.format(value))

    # Using JSON encoding means that all unicode literals and special chars
    # (e.g. newlines and backslashes) are replaced by appropriate escape sequences.
    # JSON has the same escaping rules as MATCH / SQL, so no further escaping is necessary.
    return json.dumps(value)


def _safe_match_date_and_datetime(graphql_type, expected_python_types, value):
    """Represent date and datetime objects as MATCH strings."""
    # Python datetime.datetime is a subclass of datetime.date,
    # but in this case, the two are not interchangeable.
    # Rather than using isinstance, we will therefore check for exact type equality.
    value_type = type(value)
    if not any(value_type == x for x in expected_python_types):
        raise GraphQLInvalidArgumentError(u'Expected value to be exactly one of '
                                          u'python types {}, but was {}: '
                                          u'{}'.format(expected_python_types, value_type, value))

    # The serialize() method of GraphQLDate and GraphQLDateTime produces the correct
    # ISO-8601 format that MATCH expects. We then simply represent it as a regular string.
    try:
        serialized_value = graphql_type.serialize(value)
    except ValueError as e:
        raise GraphQLInvalidArgumentError(e)

    return _safe_match_string(serialized_value)


def _safe_match_decimal(value):
    """Represent decimal objects as MATCH strings."""
    decimal_value = coerce_to_decimal(value)
    return 'decimal(' + _safe_match_string(str(decimal_value)) + ')'


def _safe_match_list(inner_type, argument_value):
    """Represent the list of "inner_type" objects in MATCH form."""
    stripped_type = strip_non_null_from_type(inner_type)
    if isinstance(stripped_type, GraphQLList):
        raise GraphQLInvalidArgumentError(u'MATCH does not currently support nested lists, '
                                          u'but inner type was {}: '
                                          u'{}'.format(inner_type, argument_value))

    if not isinstance(argument_value, list):
        raise GraphQLInvalidArgumentError(u'Attempting to represent a non-list as a list: '
                                          u'{}'.format(argument_value))

    components = (
        _safe_match_argument(stripped_type, x)
        for x in argument_value
    )
    return u'[' + u','.join(components) + u']'


def _safe_match_argument(expected_type, argument_value):
    """Return a MATCH (SQL) string representing the given argument value."""
    if GraphQLString.is_same_type(expected_type):
        return _safe_match_string(argument_value)
    elif GraphQLID.is_same_type(expected_type):
        # IDs can be strings or numbers, but the GraphQL library coerces them to strings.
        # We will follow suit and treat them as strings.
        if not isinstance(argument_value, six.string_types):
            if isinstance(argument_value, bytes):  # should only happen in py3
                argument_value = argument_value.decode('utf-8')
            else:
                argument_value = six.text_type(argument_value)
        return _safe_match_string(argument_value)
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
        return _safe_match_decimal(argument_value)
    elif GraphQLDate.is_same_type(expected_type):
        return _safe_match_date_and_datetime(expected_type, (datetime.date,), argument_value)
    elif GraphQLDateTime.is_same_type(expected_type):
        return _safe_match_date_and_datetime(expected_type,
                                             (datetime.datetime, arrow.Arrow), argument_value)
    elif isinstance(expected_type, GraphQLList):
        return _safe_match_list(expected_type.of_type, argument_value)
    else:
        raise AssertionError(u'Could not safely represent the requested GraphQL type: '
                             u'{} {}'.format(expected_type, argument_value))


######
# Public API
######

def insert_arguments_into_match_query(compilation_result, arguments):
    """Insert the arguments into the compiled MATCH query to form a complete query.

    Args:
        compilation_result: a CompilationResult object derived from the GraphQL compiler
        arguments: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        string, a MATCH query with inserted argument data
    """
    if compilation_result.language != MATCH_LANGUAGE:
        raise AssertionError(u'Unexpected query output language: {}'.format(compilation_result))

    base_query = compilation_result.query
    argument_types = compilation_result.input_metadata

    # The arguments are assumed to have already been validated against the query.
    sanitized_arguments = {
        key: _safe_match_argument(argument_types[key], value)
        for key, value in six.iteritems(arguments)
    }

    return base_query.format(**sanitized_arguments)

######
