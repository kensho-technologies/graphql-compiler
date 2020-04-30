# Copyright 2017-present Kensho Technologies, LLC.
"""Safely insert runtime arguments into compiled GraphQL queries."""
import datetime
import decimal
from typing import Any, Dict, Mapping, Union, NoReturn

import arrow
from graphql import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
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
from ..exceptions import GraphQLInvalidArgumentError
from ..global_utils import is_same_type
from ..schema import CUSTOM_SCALAR_TYPES, GraphQLDate, GraphQLDateTime, GraphQLDecimal
from ..typedefs import QueryArgumentGraphQLType
from .cypher_formatting import insert_arguments_into_cypher_query_redisgraph
from .gremlin_formatting import insert_arguments_into_gremlin_query
from .match_formatting import insert_arguments_into_match_query
from .sql_formatting import insert_arguments_into_sql_query


######
# Public API
######


def _raise_invalid_type_error(name: str, expected_python_type_name: str, value: Any) -> NoReturn:
    """Raise a GraphQLInvalidArgumentError that states that the argument type is invalid."""
    raise GraphQLInvalidArgumentError(
        "Invalid type for argument {}. Expected {}. Got value {} of "
        "type {}.".format(name, expected_python_type_name, value, type(value).__name__)
    )


def _deserialize_anonymous_json_argument(expected_type: GraphQLScalarType, value: Any) -> Any:
    """Deserialize argument. See docstring of deserialize_json_argument.

    Args:
        expected_type: GraphQL type we expect.
        value: object that can be interpreted as being of that type

    Returns:
        a value of the type produced by the parser of the expected type:
            GraphQLDate: datetime.date
            GraphQLDateTime: datetime.datetime with tzinfo=pytz.utc
            GraphQLFloat: float
            GraphQLDecimal: decimal.Decimal
            GraphQLInt: int
            GraphQLString: str
            GraphQLBoolean: bool
            GraphQLID: str

    Raises:
        ValueError if the value is not appropriate for the type. ValueError is chosen because
        it is already the base case of exceptions raised by the GraphQL parsers.
    """
    allowed_types_for_graphql_type = {
        GraphQLDate.name: (str,),
        GraphQLDateTime.name: (str,),
        GraphQLFloat.name: (str, float, int),
        GraphQLDecimal.name: (str, float, int),
        GraphQLInt.name: (int, str),
        GraphQLString.name: (str,),
        GraphQLBoolean.name: (bool,),
        GraphQLID.name: (int, str,),
    }

    # Check if the type of the value is correct
    correct_type = True
    expected_python_types = allowed_types_for_graphql_type[expected_type.name]
    if isinstance(value, bool) and not is_same_type(GraphQLBoolean, expected_type):
        correct_type = False  # We explicitly disallow passing boolean values for non-boolean types
    if not isinstance(value, expected_python_types):
        correct_type = False
    if not correct_type:
        raise ValueError(
            "Unexpected type {}. Expected one of {}.".format(type(value), expected_python_types)
        )

    name_to_custom_type = {graphql_type.name: graphql_type for graphql_type in CUSTOM_SCALAR_TYPES}
    # Bypass the GraphQLFloat parser and allow strings as input. The JSON spec allows only for
    # 64-bit floating point numbers, so large floats might have to be represented as strings.
    if is_same_type(expected_type, GraphQLFloat):
        return float(value)
    # Bypass the GraphQLInt parser and allow long ints and strings as input. The JSON spec allows
    # only for 64-bit floating point numbers, so large ints might have to be represented as strings.
    elif is_same_type(expected_type, GraphQLInt):
        return int(value)
    # Use the default GraphQL parser to parse the value
    elif expected_type.name in name_to_custom_type:
        # Since we cannot serialize the parse_value function of custom scalar types when
        # serializing a schema, it is possible that the parse_value is incorrectly set. We must,
        # therefore, use the parse_value function of the original scalar type definition.
        return name_to_custom_type[expected_type.name].parse_value(value)
    else:
        return expected_type.parse_value(value)


def deserialize_json_argument(
    name: str,
    expected_type: Union[GraphQLNonNull[GraphQLScalarType], GraphQLScalarType],
    value: Any,
) -> Any:
    """Deserialize a json serialized GraphQL argument.

    Passing arguments via jsonrpc, or via the GUI of standard GraphQL editors is tricky because
    json does not support certain types like Date, Datetime, Decimal, and also confuses floats
    for integers if there are no decimals. This function takes in a value received from a json,
    and converts it to a standard python representation that can be used in the query. Below are
    examples of accepted json encodings of all the types:
        GraphQLDate: "2018-02-01"
        GraphQLDateTime: "2018-02-01T05:11:54Z"
        GraphQLFloat: 4.3, "5.0", 5
        GraphQLDecimal: "5.00000000000000000000000000001"
        GraphQLInt: 4, "3803330000000000000000000000000000000000000000000"
        GraphQLString: "Hello"
        GraphQLBoolean: True
        GraphQLID: "13d72846-1777-6c3a-5743-5d9ced3032ed"

    Args:
        name: string, the name of the argument. It will be used to provide a more descriptive error
              message if an error is raised.
        expected_type: the GraphQL type. All GraphQLNonNull type wrappers are stripped.
        value: object that can be interpreted as being of that type

    Returns:
        a value of the type produced by the parser of the expected type:
            GraphQLDate: datetime.date
            GraphQLDateTime: datetime.datetime with tzinfo=pytz.utc
            GraphQLFloat: float
            GraphQLDecimal: decimal.Decimal
            GraphQLInt: int
            GraphQLString: str
            GraphQLBoolean: bool
            GraphQLID: str
    """
    try:
        return _deserialize_anonymous_json_argument(strip_non_null_from_type(expected_type), value)
    except (ValueError, TypeError) as e:
        raise GraphQLInvalidArgumentError("Error parsing argument {}: {}".format(name, e))


def deserialize_multiple_json_arguments(
    arguments: Mapping[str, Any],
    expected_types: Mapping[str, Union[GraphQLNonNull[GraphQLScalarType], GraphQLScalarType]],
) -> Dict[str, Any]:
    """Deserialize json serialized GraphQL arguments.

    Passing arguments via jsonrpc, or via the GUI of standard GraphQL editors is tricky because
    json does not support certain types like Date, Datetime, Decimal, and also confuses floats
    for integers if there are no decimals. This function takes in the values of json serialized
    arguments and converts them to standard python representations that can be used in queries.

    Below are examples of accepted json encodings of all the types:
        GraphQLDate: "2018-02-01"
        GraphQLDateTime: "2018-02-01T05:11:54Z"
        GraphQLFloat: 4.3, "5.0", 5
        GraphQLDecimal: "5.00000000000000000000000000001"
        GraphQLInt: 4, "3803330000000000000000000000000000000000000000000"
        GraphQLString: "Hello"
        GraphQLBoolean: True
        GraphQLID: "13d72846-1777-6c3a-5743-5d9ced3032ed"

    Args:
        arguments: mapping of argument names to json serialized argument values.
        expected_types: mapping of argument names to the expected GraphQL types. All
                        GraphQLNonNull wrappers are stripped.

    Returns:
        a mapping of argument names to deserialized argument values. The type of the deserialized
        argument value depends on the argument's GraphQL type:
            GraphQLDate: datetime.date
            GraphQLDateTime: datetime.datetime with tzinfo=pytz.utc
            GraphQLFloat: float
            GraphQLDecimal: decimal.Decimal
            GraphQLInt: int
            GraphQLString: str
            GraphQLBoolean: bool
            GraphQLID: str
    """
    ensure_arguments_are_provided(expected_types, arguments)
    return {
        name: deserialize_json_argument(name, expected_types[name], value)
        for name, value in arguments.items()
    }


def validate_argument_type(name: str, expected_type: QueryArgumentGraphQLType, value: Any):
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
            _raise_invalid_type_error(name, "string", value)
    elif is_same_type(GraphQLID, stripped_type):
        # IDs can be strings or numbers, but the GraphQL library coerces them to strings.
        # We will follow suit and treat them as strings.
        if not isinstance(value, six.string_types):
            _raise_invalid_type_error(name, "string", value)
    elif is_same_type(GraphQLFloat, stripped_type):
        if not isinstance(value, float):
            _raise_invalid_type_error(name, "float", value)
    elif is_same_type(GraphQLInt, stripped_type):
        # Special case: in Python, isinstance(True, int) returns True.
        # Safeguard against this with an explicit check against bool type.
        if isinstance(value, bool) or not isinstance(value, six.integer_types):
            _raise_invalid_type_error(name, "int", value)
    elif is_same_type(GraphQLBoolean, stripped_type):
        if not isinstance(value, bool):
            _raise_invalid_type_error(name, "bool", value)
    elif is_same_type(GraphQLDecimal, stripped_type):
        # Types we support are int, float, and Decimal, but not bool.
        # isinstance(True, int) returns True, so we explicitly forbid bool.
        if isinstance(value, bool):
            _raise_invalid_type_error(name, "decimal", value)
        if not isinstance(value, decimal.Decimal):
            try:
                decimal.Decimal(value)
            except decimal.InvalidOperation as e:
                raise GraphQLInvalidArgumentError(e)
    elif is_same_type(GraphQLDate, stripped_type):
        # Datetimes pass as instances of date. We want to explicitly only allow dates.
        if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
            _raise_invalid_type_error(name, "date", value)
        try:
            GraphQLDate.serialize(value)
        except ValueError as e:
            raise GraphQLInvalidArgumentError(e)
    elif is_same_type(GraphQLDateTime, stripped_type):
        if not isinstance(value, (datetime.date, arrow.Arrow)):
            _raise_invalid_type_error(name, "datetime", value)
        try:
            GraphQLDateTime.serialize(value)
        except ValueError as e:
            raise GraphQLInvalidArgumentError(e)
    elif isinstance(stripped_type, GraphQLList):
        if not isinstance(value, list):
            _raise_invalid_type_error(name, "list", value)
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


def insert_arguments_into_query(compilation_result: CompilationResult, arguments: Dict[str, Any]):
    """Insert the arguments into the compiled GraphQL query to form a complete query.

    Args:
        compilation_result: a CompilationResult object derived from the GraphQL compiler
        arguments: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        string, a query in the appropriate output language, with inserted argument data
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


######
