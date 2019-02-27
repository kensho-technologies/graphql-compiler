# Copyright 2017-present Kensho Technologies, LLC.
"""Safely insert runtime arguments into compiled GraphQL queries."""
import datetime
import decimal

import arrow
from graphql import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import six

from ..compiler import GREMLIN_LANGUAGE, MATCH_LANGUAGE, SQL_LANGUAGE
from ..exceptions import GraphQLInvalidArgumentError
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from .gremlin_formatting import insert_arguments_into_gremlin_query
from .match_formatting import insert_arguments_into_match_query
from .sql_formatting import insert_arguments_into_sql_query


######
# Public API
######

def _check_is_string_value(value):
    """Raise if the value is not a proper utf-8 string."""
    if not isinstance(value, six.string_types):
        if isinstance(value, bytes):  # should only happen in py3
            value.decode('utf-8')  # decoding should not raise errors
        else:
            raise GraphQLInvalidArgumentError(u'Attempting to convert a non-string into a string: '
                                              u'{}'.format(value))


# TODO(bojanserafimov): test this function
def _validate_argument_type(expected_type, value):
    """Check if the value is appropriate for the type and usable in any of our backends."""
    if GraphQLString.is_same_type(expected_type):
        _check_is_string_value(value)
    elif GraphQLID.is_same_type(expected_type):
        # IDs can be strings or numbers, but the GraphQL library coerces them to strings.
        # We will follow suit and treat them as strings.
        _check_is_string_value(value)
    elif GraphQLFloat.is_same_type(expected_type):
        if not isinstance(value, float):
            raise GraphQLInvalidArgumentError(u'Attempting to represent a non-float as a float: '
                                              u'{}'.format(value))
    elif GraphQLInt.is_same_type(expected_type):
        # Special case: in Python, isinstance(True, int) returns True.
        # Safeguard against this with an explicit check against bool type.
        if isinstance(value, bool) or not isinstance(value, six.integer_types):
            raise GraphQLInvalidArgumentError(u'Attempting to represent a non-int as an int: '
                                              u'{}'.format(value))
    elif GraphQLBoolean.is_same_type(expected_type):
        if not isinstance(value, bool):
            raise GraphQLInvalidArgumentError(u'Attempting to represent a non-bool as a bool: '
                                              u'{}'.format(value))
    elif GraphQLDecimal.is_same_type(expected_type):
        if not isinstance(value, decimal.Decimal):
            try:
                decimal.Decimal(value)
            except decimal.InvalidOperation as e:
                raise GraphQLInvalidArgumentError(e)
    elif GraphQLDate.is_same_type(expected_type):
        if not isinstance(value, datetime.date):
            raise GraphQLInvalidArgumentError(u'Attempting to represent a non-date as a date: '
                                              u'{}'.format(value))
    elif GraphQLDateTime.is_same_type(expected_type):
        if not isinstance(value, (datetime.date, arrow.Arrow)):
            raise GraphQLInvalidArgumentError(u'Attempting to represent a non-date as a date: '
                                              u'{}'.format(value))
    elif isinstance(expected_type, GraphQLList):
        if not isinstance(value, list):
            raise GraphQLInvalidArgumentError(u'Attempting to represent a non-list as a list: '
                                              u'{}'.format(value))
    else:
        raise AssertionError(u'Could not safely represent the requested GraphQL type: '
                             u'{} {}'.format(expected_type, value))


def ensure_arguments_are_provided(expected_types, arguments, check_types=False):
    """Ensure that all arguments expected by the query were actually provided."""
    expected_arg_names = set(six.iterkeys(expected_types))
    provided_arg_names = set(six.iterkeys(arguments))

    if expected_arg_names != provided_arg_names:
        missing_args = expected_arg_names - provided_arg_names
        unexpected_args = provided_arg_names - expected_arg_names
        raise GraphQLInvalidArgumentError(u'Missing or unexpected arguments found: '
                                          u'missing {}, unexpected '
                                          u'{}'.format(missing_args, unexpected_args))
    if check_types:
        for name in expected_arg_names:
            _validate_argument_type(expected_types[name], arguments[name])


def insert_arguments_into_query(compilation_result, arguments):
    """Insert the arguments into the compiled GraphQL query to form a complete query.

    Args:
        compilation_result: a CompilationResult object derived from the GraphQL compiler
        arguments: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        string, a query in the appropriate output language, with inserted argument data
    """
    ensure_arguments_are_provided(compilation_result.input_metadata, arguments)

    if compilation_result.language == MATCH_LANGUAGE:
        return insert_arguments_into_match_query(compilation_result, arguments)
    elif compilation_result.language == GREMLIN_LANGUAGE:
        return insert_arguments_into_gremlin_query(compilation_result, arguments)
    elif compilation_result.language == SQL_LANGUAGE:
        return insert_arguments_into_sql_query(compilation_result, arguments)
    else:
        raise AssertionError(u'Unrecognized language in compilation result: '
                             u'{}'.format(compilation_result))

######
