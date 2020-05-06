# Copyright 2017-present Kensho Technologies, LLC.
"""Safely insert runtime arguments into compiled GraphQL queries."""
import datetime
import decimal
from types import MappingProxyType
from typing import Any, Callable, Collection, Dict, Mapping, NoReturn, Tuple, Type

import arrow
from graphql import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
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
from ..global_utils import assert_set_equality, is_same_type
from ..schema import SUPPORTED_SCALAR_TYPES, GraphQLDate, GraphQLDateTime, GraphQLDecimal
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


_ALLOWED_JSON_SCALAR_TYPES: Mapping[str, Tuple[Type, ...]] = MappingProxyType(
    {
        GraphQLDate.name: (str,),
        GraphQLDateTime.name: (str,),
        GraphQLFloat.name: (str, float, int),
        GraphQLDecimal.name: (str, float, int),
        GraphQLInt.name: (int, str),
        GraphQLString.name: (str,),
        GraphQLBoolean.name: (bool, int, str),
        GraphQLID.name: (int, str,),
    }
)
assert_set_equality(
    set(_ALLOWED_JSON_SCALAR_TYPES.keys()),
    {graphql_type.name for graphql_type in SUPPORTED_SCALAR_TYPES},
)


def _custom_boolean_deserialization(value: Any) -> bool:
    """Deserialize a boolean, allowing for common string or int representations."""
    true_values = [1, "1", "true", "True", True]
    false_values = [0, "0", "false", "False", False]
    if value in true_values:
        return True
    elif value in false_values:
        return False
    else:
        raise ValueError(
            f"Received unexpected GraphQLBoolean value {value} ({type(value)}). Expected one "
            f"of the following {true_values + false_values}."
        )


_CUSTOM_SCALAR_DESERIALIZATION_FUNCTIONS: Mapping[str, Callable[[Any], Any]] = MappingProxyType(
    {
        # Bypass the GraphQLFloat parser and allow strings as input. The JSON spec allows only
        # for 64-bit floating point numbers, so large floats might have to be represented as
        # strings.
        GraphQLFloat.name: float,
        # Bypass the GraphQLInt parser and allow long ints and strings as input. The JSON spec
        # allows only for 64-bit floating point numbers, so large ints might have to be
        # represented as strings.
        GraphQLInt.name: int,
        # Bypass the GraphQLBoolean parser and allow some strings and ints as input.
        GraphQLBoolean.name: _custom_boolean_deserialization,
    }
)

_JSON_TYPES_AND_DESERIALIZATION_FUNCTIONS: Mapping[
    str, Tuple[Tuple[Type, ...], Callable[[Any], Any]]
] = MappingProxyType(
    {
        scalar_type.name: (
            _ALLOWED_JSON_SCALAR_TYPES[scalar_type.name],
            _CUSTOM_SCALAR_DESERIALIZATION_FUNCTIONS.get(scalar_type.name, scalar_type.parse_value),
        )
        for scalar_type in SUPPORTED_SCALAR_TYPES
    }
)


######
# Public API
######


def deserialize_scalar_argument(name: str, expected_type: GraphQLScalarType, value: Any) -> Any:
    """Deserialize a serialized scalar argument. See docstring of deserialize_argument.

    Args:
        name: the name of the argument
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
        GraphQLInvalidArgumentError: if the argument value was not of the expected type.
    """
    types_and_deserialization = _JSON_TYPES_AND_DESERIALIZATION_FUNCTIONS.get(expected_type.name)
    if types_and_deserialization is None:
        raise AssertionError(
            f"Got unsupported GraphQL type {expected_type} for argument {name} with value {value}."
        )
    else:
        expected_python_types, deserialization_function = types_and_deserialization
        if any(
            (
                not isinstance(value, expected_python_types),
                # We explicitly disallow passing boolean values for non-boolean types
                (isinstance(value, bool) and not is_same_type(GraphQLBoolean, expected_type)),
            )
        ):
            _raise_invalid_type_error(name, expected_python_types, value)
        try:
            return deserialization_function(value)
        except (ValueError, TypeError) as e:
            raise GraphQLInvalidArgumentError("Error parsing argument {}: {}".format(name, e))


def deserialize_argument(name: str, expected_type: QueryArgumentGraphQLType, value: Any,) -> Any:
    """Deserialize a serialized GraphQL argument.

    Passing arguments via jsonrpc, or via the GUI of standard GraphQL editors is tricky because
    json does not support certain types like Date, Datetime, Decimal, and also confuses floats
    for integers if there are no decimals. This function takes in a value and converts it to a
    standard python representation.

    Below are examples of accepted encodings of all the types:
        GraphQLDate: "2018-02-01"
        GraphQLDateTime: "2018-02-01T05:11:54Z"
        GraphQLFloat: 4.3, "5.0", 5
        GraphQLDecimal: "5.00000000000000000000000000001"
        GraphQLInt: 4, "3803330000000000000000000000000000000000000000000"
        GraphQLString: "Hello"
        GraphQLBoolean: True, 1, "1", "True", "true"
        GraphQLID: "13d72846-1777-6c3a-5743-5d9ced3032ed"
        GraphQLList(GraphQLInt): [1, 2, 3]

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
            GraphQLList: list of the inner type

    Raises:
        GraphQLInvalidArgumentError: if the argument value was not of the expected type.
    """
    stripped_type = strip_non_null_from_type(expected_type)
    if isinstance(stripped_type, GraphQLList):
        if not isinstance(value, list):
            _raise_invalid_type_error(name, (list,), value)

        inner_stripped_type = strip_non_null_from_type(stripped_type.of_type)

        return [
            deserialize_scalar_argument(name, inner_stripped_type, element) for element in value
        ]
    else:
        return deserialize_scalar_argument(name, stripped_type, value)


def deserialize_multiple_arguments(
    arguments: Mapping[str, Any], expected_types: Mapping[str, QueryArgumentGraphQLType],
) -> Dict[str, Any]:
    """Deserialize serialized GraphQL arguments.

    Passing arguments via jsonrpc, or via the GUI of standard GraphQL editors is tricky because
    json does not support certain types like Date, Datetime, Decimal, and also confuses floats
    for integers if there are no decimals. This function takes in values converts them to
    standard python representations.

    Below are examples of accepted json encodings of all the types:
        GraphQLDate: "2018-02-01"
        GraphQLDateTime: "2018-02-01T05:11:54Z"
        GraphQLFloat: 4.3, "5.0", 5
        GraphQLDecimal: "5.00000000000000000000000000001"
        GraphQLInt: 4, "3803330000000000000000000000000000000000000000000"
        GraphQLString: "Hello"
        GraphQLBoolean: True, 1, "1", "True", "true"
        GraphQLID: "13d72846-1777-6c3a-5743-5d9ced3032ed"
        GraphQLList(GraphQLInt): [1, 2, 3]

    Args:
        arguments: mapping of argument names to serialized argument values.
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
            GraphQLList: list of the inner type

    Raises:
        GraphQLInvalidArgumentError: if any of the argument values was not of the expected type.
    """
    ensure_arguments_are_provided(expected_types, arguments)
    return {
        name: deserialize_argument(name, expected_types[name], value)
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
        if not isinstance(value, (datetime.date, arrow.Arrow)):
            _raise_invalid_type_error(name, (datetime.date, arrow.Arrow), value)
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
