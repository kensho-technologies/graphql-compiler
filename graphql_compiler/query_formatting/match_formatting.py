# Copyright 2017-present Kensho Technologies, LLC.
"""Safely represent arguments for MATCH-language GraphQL queries."""
import json

from graphql import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import six

from ..compiler import MATCH_LANGUAGE
from ..compiler.helpers import strip_non_null_from_type
from ..exceptions import GraphQLInvalidArgumentError
from ..global_utils import is_same_type
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from .representations import coerce_to_decimal, represent_float_as_str, type_check_and_str


def _safe_match_string(value):
    """Sanitize and represent a string argument in MATCH."""
    if not isinstance(value, six.string_types):
        if isinstance(value, bytes):  # likely to only happen in py2
            value = value.decode("utf-8")
        else:
            raise GraphQLInvalidArgumentError(
                "Attempting to convert a non-string into a string: {}".format(value)
            )

    # Using JSON encoding means that all unicode literals and special chars
    # (e.g. newlines and backslashes) are replaced by appropriate escape sequences.
    # JSON has the same escaping rules as MATCH / SQL, so no further escaping is necessary.
    return json.dumps(value)


def _safe_match_date(value):
    """Represent date objects as MATCH strings."""
    try:
        serialized_value = GraphQLDate.serialize(value)
    except ValueError as e:
        raise GraphQLInvalidArgumentError(e)

    return _safe_match_string(serialized_value)


def _safe_match_datetime(value):
    """Represent datetime objects as MATCH strings."""
    try:
        serialized_value = GraphQLDateTime.serialize(value)
    except ValueError as e:
        raise GraphQLInvalidArgumentError(e)

    return _safe_match_string(serialized_value)


def _safe_match_decimal(value):
    """Represent decimal objects as MATCH strings."""
    decimal_value = coerce_to_decimal(value)
    return "decimal(" + _safe_match_string(str(decimal_value)) + ")"


def _safe_match_list(inner_type, argument_value):
    """Represent the list of "inner_type" objects in MATCH form."""
    stripped_type = strip_non_null_from_type(inner_type)
    if isinstance(stripped_type, GraphQLList):
        raise GraphQLInvalidArgumentError(
            "MATCH does not currently support nested lists, "
            "but inner type was {}: "
            "{}".format(inner_type, argument_value)
        )

    if not isinstance(argument_value, list):
        raise GraphQLInvalidArgumentError(
            "Attempting to represent a non-list as a list: {}".format(argument_value)
        )

    components = (_safe_match_argument(stripped_type, x) for x in argument_value)
    return "[" + ",".join(components) + "]"


def _safe_match_argument(expected_type, argument_value):
    """Return a MATCH (SQL) string representing the given argument value."""
    if is_same_type(GraphQLString, expected_type):
        return _safe_match_string(argument_value)
    elif is_same_type(GraphQLID, expected_type):
        # IDs can be strings or numbers, but the GraphQL library coerces them to strings.
        # We will follow suit and treat them as strings.
        if not isinstance(argument_value, six.string_types):
            if isinstance(argument_value, bytes):  # likely to only happen in py2
                argument_value = argument_value.decode("utf-8")
            else:
                argument_value = six.text_type(argument_value)
        return _safe_match_string(argument_value)
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
        return _safe_match_decimal(argument_value)
    elif is_same_type(GraphQLDate, expected_type):
        return _safe_match_date(argument_value)
    elif is_same_type(GraphQLDateTime, expected_type):
        return _safe_match_datetime(argument_value)
    elif isinstance(expected_type, GraphQLList):
        return _safe_match_list(expected_type.of_type, argument_value)
    else:
        raise AssertionError(
            "Could not safely represent the requested GraphQL type: "
            "{} {}".format(expected_type, argument_value)
        )


######
# Public API
######


def insert_arguments_into_match_query(compilation_result, arguments):
    """Insert the arguments into the compiled MATCH query to form a complete query.

    Args:
        compilation_result: a CompilationResult object derived from the GraphQL compiler
        arguments: dict, str -> any, mapping argument name to its value, for every parameter the
                   query expects.

    Returns:
        string, a MATCH query with inserted argument data
    """
    if compilation_result.language != MATCH_LANGUAGE:
        raise AssertionError("Unexpected query output language: {}".format(compilation_result))

    base_query = compilation_result.query
    argument_types = compilation_result.input_metadata

    # The arguments are assumed to have already been validated against the query.
    sanitized_arguments = {
        key: _safe_match_argument(argument_types[key], value)
        for key, value in six.iteritems(arguments)
    }

    return base_query.format(**sanitized_arguments)


######
