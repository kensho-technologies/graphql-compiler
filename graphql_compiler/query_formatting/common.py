# Copyright 2017-present Kensho Technologies, LLC.
"""Safely insert runtime arguments into compiled GraphQL queries."""
import datetime
import decimal
from types import MappingProxyType
from typing import Any, Callable, Collection, Dict, Mapping, NoReturn, Type, Union

import arrow
from funcy.compat import zip
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

from ..compiler import CYPHER_LANGUAGE, GREMLIN_LANGUAGE, MATCH_LANGUAGE, SQL_LANGUAGE
from ..compiler.helpers import strip_non_null_from_type
from ..exceptions import GraphQLInvalidArgumentError
from ..global_utils import assert_that_mappings_have_the_same_keys, is_same_type
from ..schema import SCALAR_TYPE_NAME_TO_VALUE, GraphQLDate, GraphQLDateTime, GraphQLDecimal
from .cypher_formatting import insert_arguments_into_cypher_query_redisgraph
from .gremlin_formatting import insert_arguments_into_gremlin_query
from .match_formatting import insert_arguments_into_match_query
from .sql_formatting import insert_arguments_into_sql_query


######
# Public API
######


def _raise_invalid_type_error(
    name: str, expected_python_types: Collection[Type], value: Any
) -> NoReturn:
    """Raise a GraphQLInvalidArgumentError that states that the argument type is invalid."""
    raise GraphQLInvalidArgumentError(
        f"Invalid type for argument {name}. Expected one of {expected_python_types}. Got value "
        f"{value} of type {type(value).__name__} instead."
    )


_ALLOWED_JSON_SCALAR_TYPES = MappingProxyType(
    {
        GraphQLDate.name: (str,),
        GraphQLDateTime.name: (str,),
        GraphQLFloat.name: (str, float, int),
        GraphQLDecimal.name: (str, float, int),
        GraphQLInt.name: (int, str),
        GraphQLString.name: (str,),
        GraphQLBoolean.name: (bool,),
        GraphQLID.name: (int, str,),
    }
)
_CUSTOM_SCALAR_DESERIALIZATION_FUNCTIONS = MappingProxyType(
    {GraphQLInt.name: int, GraphQLFloat.name: float}
)
_SCALAR_DESERIALIZATION_FUNCTIONS = MappingProxyType(
    {
        name: _CUSTOM_SCALAR_DESERIALIZATION_FUNCTIONS.get(name, graphql_type.parse_value)
        for name, graphql_type in SCALAR_TYPE_NAME_TO_VALUE.items()
    }
)
_ALLOWED_JSON_SCALAR_TYPES_AND_DESERIALIZATION_FUNCTION = MappingProxyType(
    {
        name: (allowed_types, _SCALAR_DESERIALIZATION_FUNCTIONS[name])
        for name, allowed_types in _ALLOWED_JSON_SCALAR_TYPES.items()
    }
)
assert_that_mappings_have_the_same_keys(
    _ALLOWED_JSON_SCALAR_TYPES_AND_DESERIALIZATION_FUNCTION, SCALAR_TYPE_NAME_TO_VALUE
)


def _deserialize_json_scalar_argument(name, expected_type: GraphQLScalarType, value: Any) -> Any:
    """Deserialize the json serialized scalar argument."""
    allowed_types_and_deserialization = _ALLOWED_JSON_SCALAR_TYPES_AND_DESERIALIZATION_FUNCTION.get(
        expected_type.name
    )
    if allowed_types_and_deserialization is None:
        raise AssertionError(
            f"Got unsupported GraphQL type {expected_type} for argument {name} with value {value}."
        )
    else:
        expected_python_types, deserialization_function = allowed_types_and_deserialization
        if (
            not isinstance(value, expected_python_types) or
            # We explicitly disallow passing boolean values for non-boolean types
            (isinstance(value, bool) and is_same_type(GraphQLBoolean, expected_type))
        ):
            _raise_invalid_type_error(name, expected_python_types, value)
        else:
            try:
                return deserialization_function(value)
            except (ValueError, TypeError) as e:
                raise GraphQLInvalidArgumentError("Error parsing argument {}: {}".format(name, e))


def deserialize_json_argument(
    name: str,
    expected_type: Union[
        GraphQLScalarType,
        GraphQLList[GraphQLScalarType],
        GraphQLList[GraphQLNonNull[GraphQLScalarType]],
        GraphQLNonNull[GraphQLScalarType],
        GraphQLNonNull[GraphQLList[GraphQLScalarType]],
        GraphQLNonNull[GraphQLList[GraphQLNonNull[GraphQLScalarType]]],
    ],
    value: Any,
) -> Any:
    """Deserialize a GraphQL argument parsed from a json file.

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
        GraphQLList: [1,2,3]

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
    """
    stripped_type = strip_non_null_from_type(expected_type)

    if isinstance(stripped_type, GraphQLList):
        if not isinstance(value, list):
            _raise_invalid_type_error(name, (list,), value)

        inner_stripped_type = strip_non_null_from_type(stripped_type.of_type)
        return [
            _deserialize_json_scalar_argument(name, inner_stripped_type, element)
            for element in value
        ]
    else:
        return _deserialize_json_scalar_argument(name, stripped_type, value)


def deserialize_multiple_json_arguments(
    arguments: Mapping[str, Any],
    expected_types: Mapping[
        str,
        Union[
            GraphQLScalarType,
            GraphQLList[GraphQLScalarType],
            GraphQLList[GraphQLNonNull[GraphQLScalarType]],
            GraphQLNonNull[GraphQLScalarType],
            GraphQLNonNull[GraphQLList[GraphQLScalarType]],
            GraphQLNonNull[GraphQLList[GraphQLNonNull[GraphQLScalarType]]],
        ],
    ],
) -> Dict[str, Any]:
    """Deserialize GraphQL arguments parsed from a json file.

    Args:
        arguments: mapping of argument names to json serialized values.
        expected_types: mapping of argument names to the expected GraphQL types.

    Returns:
        a mapping of argument names to their deserialized values. See the docstring of
        deserialize_json_argument for more info on how arguments are deserialized.
    """
    ensure_arguments_are_provided(expected_types, arguments)
    return {
        name: deserialize_json_argument(name, expected_types[name], value)
        for name, value in arguments.items()
    }


def validate_argument_type(name, expected_type, value):
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
            _raise_invalid_type_error(name, "date", value)
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
    expected_types: Mapping[str, GraphQLType], arguments: Mapping[str, Any]
) -> None:
    """Ensure that all arguments are provided and that they are of the expected type."""
    ensure_arguments_are_provided(expected_types, arguments)
    for name in expected_types:
        validate_argument_type(name, expected_types[name], arguments[name])


def insert_arguments_into_query(compilation_result, arguments):
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
