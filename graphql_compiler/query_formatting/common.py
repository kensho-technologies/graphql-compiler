# Copyright 2017-present Kensho Technologies, LLC.
"""Safely insert runtime arguments into compiled GraphQL queries."""
import datetime
import decimal

import arrow
from graphql import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import six

from ..compiler import CYPHER_LANGUAGE, GREMLIN_LANGUAGE, MATCH_LANGUAGE, SQL_LANGUAGE
from ..compiler.helpers import strip_non_null_from_type
from ..exceptions import GraphQLInvalidArgumentError
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from .cypher_formatting import insert_arguments_into_cypher_query_redisgraph
from .gremlin_formatting import insert_arguments_into_gremlin_query
from .match_formatting import insert_arguments_into_match_query
from .sql_formatting import insert_arguments_into_sql_query


######
# Public API
######

def _raise_invalid_type_error(expected_python_type_name, value, name):
    """Raise a GraphQLInvalidArgumentError that states that the argument type is invalid."""
    if name is not None:
        error_message_prefix = u'Invalid type for argument {}.'.format(name)
    else:
        error_message_prefix = u'Found argument with invalid type.'
    error_message_middle = ' Expected {}. '.format(expected_python_type_name)
    error_message_suffix = u'Got value {} of type {}.'.format(value, type(value).__name__)
    error_message = error_message_prefix + error_message_middle + error_message_suffix
    raise GraphQLInvalidArgumentError(error_message)


# TODO(pmantica1): Make name param required in validate_argument_type in major version bump.
def validate_argument_type(expected_type, value, name=None):
    """Ensure the value has the expected type and is usable in any of our backends, or raise errors.

    Backends are the database languages we have the ability to compile to, like OrientDB MATCH,
    Gremlin, or SQLAlchemy. This function should be stricter than the validation done by any
    specific backend. That way code that passes validation can be compiled to any backend.

    Args:
        expected_type: GraphQLType we expect. All GraphQLNonNull type wrappers are stripped.
        value: object that can be interpreted as being of that type
        name: optional string. If it is a string, it is the name of the argument and will be used to
              provide a more descriptive error message if an error is raised.
    """
    stripped_type = strip_non_null_from_type(expected_type)
    if GraphQLString.is_same_type(stripped_type):
        if not isinstance(value, six.string_types):
            _raise_invalid_type_error('string', value, name)
    elif GraphQLID.is_same_type(stripped_type):
        # IDs can be strings or numbers, but the GraphQL library coerces them to strings.
        # We will follow suit and treat them as strings.
        if not isinstance(value, six.string_types):
            _raise_invalid_type_error('string', value, name)
    elif GraphQLFloat.is_same_type(stripped_type):
        if not isinstance(value, float):
            _raise_invalid_type_error('float', value, name)
    elif GraphQLInt.is_same_type(stripped_type):
        # Special case: in Python, isinstance(True, int) returns True.
        # Safeguard against this with an explicit check against bool type.
        if isinstance(value, bool) or not isinstance(value, six.integer_types):
            _raise_invalid_type_error('int', value, name)
    elif GraphQLBoolean.is_same_type(stripped_type):
        if not isinstance(value, bool):
            _raise_invalid_type_error('bool', value, name)
    elif GraphQLDecimal.is_same_type(stripped_type):
        # Types we support are int, float, and Decimal, but not bool.
        # isinstance(True, int) returns True, so we explicitly forbid bool.
        if isinstance(value, bool):
            _raise_invalid_type_error('decimal', value, name)
        if not isinstance(value, decimal.Decimal):
            try:
                decimal.Decimal(value)
            except decimal.InvalidOperation as e:
                raise GraphQLInvalidArgumentError(e)
    elif GraphQLDate.is_same_type(stripped_type):
        # Datetimes pass as instances of date. We want to explicitly only allow dates.
        if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
            _raise_invalid_type_error('date', value, name)
        try:
            stripped_type.serialize(value)
        except ValueError as e:
            raise GraphQLInvalidArgumentError(e)
    elif GraphQLDateTime.is_same_type(stripped_type):
        if not isinstance(value, (datetime.date, arrow.Arrow)):
            _raise_invalid_type_error('datetime', value, name)
        try:
            stripped_type.serialize(value)
        except ValueError as e:
            raise GraphQLInvalidArgumentError(e)
    elif isinstance(stripped_type, GraphQLList):
        if not isinstance(value, list):
            _raise_invalid_type_error('list', value, name)
        inner_type = strip_non_null_from_type(stripped_type.of_type)
        for element in value:
            validate_argument_type(inner_type, element, name=name)
    else:
        raise AssertionError(u'Could not safely represent the requested GraphQLType: '
                             u'{} {}'.format(stripped_type, value))


def ensure_arguments_are_provided(expected_types, arguments):
    """Ensure that all arguments expected by the query were actually provided."""
    expected_arg_names = set(six.iterkeys(expected_types))
    provided_arg_names = set(six.iterkeys(arguments))

    if expected_arg_names != provided_arg_names:
        missing_args = expected_arg_names - provided_arg_names
        unexpected_args = provided_arg_names - expected_arg_names
        raise GraphQLInvalidArgumentError(u'Missing or unexpected arguments found: '
                                          u'missing {}, unexpected '
                                          u'{}'.format(missing_args, unexpected_args))
    for name in expected_arg_names:
        validate_argument_type(expected_types[name], arguments[name], name=name)


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
    elif compilation_result.language == CYPHER_LANGUAGE:
        return insert_arguments_into_cypher_query_redisgraph(compilation_result, arguments)
    else:
        raise AssertionError(u'Unrecognized language in compilation result: '
                             u'{}'.format(compilation_result))

######
