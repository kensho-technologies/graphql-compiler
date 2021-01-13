# Copyright 2017-present Kensho Technologies, LLC.
"""Safely insert runtime arguments into compiled GraphQL queries."""
import datetime
import decimal
from typing import Any, Collection, Dict, Mapping, NoReturn, Type

from graphql import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLString,
    GraphQLType,
)
import six

from ..compiler import (
    CYPHER_LANGUAGE,
    GREMLIN_LANGUAGE,
    MATCH_LANGUAGE,
    SQL_LANGUAGE,
    CompilationResult,
)
from ..compiler.helpers import strip_non_null_from_type
from ..deserialization import deserialize_value
from ..exceptions import GraphQLInvalidArgumentError
from ..global_utils import is_same_type
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from ..typedefs import QueryArgumentGraphQLType
from .cypher_formatting import insert_arguments_into_cypher_query_redisgraph
from .gremlin_formatting import insert_arguments_into_gremlin_query
from .match_formatting import insert_arguments_into_match_query
from .sql_formatting import insert_arguments_into_sql_query


def _raise_invalid_type_error(
    name: str, expected_python_types: Collection[Type], value: Any
) -> NoReturn:
    """Raise a GraphQLInvalidArgumentError that states that the argument type is invalid."""
    raise GraphQLInvalidArgumentError(
        f"Invalid type for argument {name}. Expected one of {expected_python_types}. Got value "
        f"{value} of type {type(value).__name__} instead."
    )


######
# Public API
######


def validate_argument_type(name: str, expected_type: QueryArgumentGraphQLType, value: Any) -> None:
    """Ensure the value has the expected type and is usable in any of our backends, or raise errors.

    Backends are the database languages we have the ability to compile to, like OrientDB MATCH,
    Gremlin, or SQLAlchemy. This function should be stricter than the validation done by any
    specific backend. That way code that passes validation can be compiled to any backend.

    Args:
        name: string, the name of the argument. It will be used to provide a more descriptive error
              message if an error is raised.
        expected_type: GraphQLType we expect. All GraphQLNonNull type wrappers are stripped.
        value: object that can be interpreted as being of that type
    """
    stripped_type = strip_non_null_from_type(expected_type)
    if is_same_type(GraphQLString, stripped_type):
        if not isinstance(value, six.string_types):
            _raise_invalid_type_error(name, (str,), value)
    elif is_same_type(GraphQLID, stripped_type):
        # IDs can be strings or numbers, but the GraphQL library coerces them to strings.
        # We will follow suit and treat them as strings.
        if not isinstance(value, six.string_types):
            _raise_invalid_type_error(name, (str,), value)
    elif is_same_type(GraphQLFloat, stripped_type):
        if not isinstance(value, float):
            _raise_invalid_type_error(name, (float,), value)
    elif is_same_type(GraphQLInt, stripped_type):
        # Special case: in Python, isinstance(True, int) returns True.
        # Safeguard against this with an explicit check against bool type.
        if isinstance(value, bool) or not isinstance(value, six.integer_types):
            _raise_invalid_type_error(name, (int,), value)
    elif is_same_type(GraphQLBoolean, stripped_type):
        if not isinstance(value, bool):
            _raise_invalid_type_error(name, (bool,), value)
    elif is_same_type(GraphQLDecimal, stripped_type):
        # Types we support are int, float, and Decimal, but not bool.
        # isinstance(True, int) returns True, so we explicitly forbid bool.
        if isinstance(value, bool):
            _raise_invalid_type_error(name, (bool,), value)
        if not isinstance(value, decimal.Decimal):
            try:
                decimal.Decimal(value)
            except decimal.InvalidOperation as e:
                raise GraphQLInvalidArgumentError(e)
    elif is_same_type(GraphQLDate, stripped_type):
        # Datetimes pass as instances of date. We want to explicitly only allow dates.
        if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
            _raise_invalid_type_error(name, (datetime.date,), value)
        try:
            GraphQLDate.serialize(value)
        except ValueError as e:
            raise GraphQLInvalidArgumentError(e)
    elif is_same_type(GraphQLDateTime, stripped_type):
        if not isinstance(value, datetime.datetime):
            _raise_invalid_type_error(name, (datetime.datetime,), value)
        try:
            GraphQLDateTime.serialize(value)
        except ValueError as e:
            raise GraphQLInvalidArgumentError(e)
    elif isinstance(stripped_type, GraphQLList):
        if not isinstance(value, list):
            _raise_invalid_type_error(name, (list,), value)
        inner_type = strip_non_null_from_type(stripped_type.of_type)
        for element in value:
            validate_argument_type(name, inner_type, element)
    else:
        raise AssertionError(
            "Could not safely represent the requested GraphQLType: "
            "{} {}".format(stripped_type, value)
        )


def ensure_arguments_are_provided(
    expected_types: Mapping[str, GraphQLType], arguments: Mapping[str, Any]
) -> None:
    """Ensure that all arguments expected by the query were actually provided."""
    expected_arg_names = set(six.iterkeys(expected_types))
    provided_arg_names = set(six.iterkeys(arguments))

    if expected_arg_names != provided_arg_names:
        missing_args = expected_arg_names - provided_arg_names
        unexpected_args = provided_arg_names - expected_arg_names
        raise GraphQLInvalidArgumentError(
            "Missing or unexpected arguments found: "
            "missing {}, unexpected "
            "{}".format(missing_args, unexpected_args)
        )


def validate_arguments(
    expected_types: Mapping[str, QueryArgumentGraphQLType], arguments: Mapping[str, Any]
) -> None:
    """Ensure that all arguments are provided and that they are of the expected type.

    Backends are the database languages we have the ability to compile to, like OrientDB MATCH,
    Gremlin, or SQLAlchemy. This function should be stricter than the validation done by any
    specific backend. That way code that passes validation can be compiled to any backend.

    Args:
        arguments: mapping of argument names to arguments values.
        expected_types: mapping of argument names to the expected GraphQL types. All GraphQLNonNull
                        type wrappers are stripped.
    """
    ensure_arguments_are_provided(expected_types, arguments)
    for name in expected_types:
        validate_argument_type(name, expected_types[name], arguments[name])


def insert_arguments_into_query(
    compilation_result: CompilationResult,
    arguments: Dict[str, Any],
) -> Any:
    """Insert the arguments into the compiled GraphQL query to form a complete query.

    Args:
        compilation_result: a CompilationResult object derived from the GraphQL compiler
        arguments: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        string or SQLAlchemy query object, representing the query in the appropriate
        output language, with inserted argument data
    """
    validate_arguments(compilation_result.input_metadata, arguments)

    if compilation_result.language == MATCH_LANGUAGE:
        return insert_arguments_into_match_query(compilation_result, arguments)
    elif compilation_result.language == GREMLIN_LANGUAGE:
        return insert_arguments_into_gremlin_query(compilation_result, arguments)
    elif compilation_result.language == SQL_LANGUAGE:
        return insert_arguments_into_sql_query(compilation_result, arguments)
    elif compilation_result.language == CYPHER_LANGUAGE:
        return insert_arguments_into_cypher_query_redisgraph(compilation_result, arguments)
    else:
        raise AssertionError(
            "Unrecognized language in compilation result: {}".format(compilation_result)
        )


def deserialize_argument(
    name: str,
    expected_type: QueryArgumentGraphQLType,
    value: Any,
) -> Any:
    """Deserialize a GraphQL argument, raising a GraphQLInvalidArgumentError if invalid."""
    try:
        return deserialize_value(expected_type, value)
    except (ValueError, TypeError) as e:
        raise GraphQLInvalidArgumentError(f"Error parsing argument {name}: {e}")


def deserialize_multiple_arguments(
    arguments: Mapping[str, Any],
    expected_types: Mapping[str, QueryArgumentGraphQLType],
) -> Dict[str, Any]:
    """Deserialize GraphQL arguments, raising GraphQLInvalidArgumentError if any are invalid."""
    ensure_arguments_are_provided(expected_types, arguments)
    return {
        name: deserialize_argument(name, expected_types[name], value)
        for name, value in arguments.items()
    }


######
