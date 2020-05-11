# Copyright 2020-present Kensho Technologies, LLC.
"""Convert values to their underlying GraphQLType."""
from types import MappingProxyType
from typing import Any, Callable, Dict, Mapping, Tuple, Type

from graphql import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLScalarType,
    GraphQLString,
)

from graphql_compiler import GraphQLInvalidArgumentError
from graphql_compiler.compiler.helpers import strip_non_null_from_type
from graphql_compiler.global_utils import is_same_type
from graphql_compiler.typedefs import QueryArgumentGraphQLType

from .global_utils import assert_set_equality
from .schema import SUPPORTED_SCALAR_TYPES, GraphQLDate, GraphQLDateTime, GraphQLDecimal


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


def convert_scalar_value_to_graphql_type(expected_type: GraphQLScalarType, value: Any) -> Any:
    """Convert a scalar value to the appropriate type for the given GraphQLScalarType.

    Args:
        expected_type: a GraphQLScalarType to which value should be converted.
        value: object that can be interpreted as being of expected_type.

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
        TypeError: if the value was not of the expected type.
    """
    types_and_deserialization = _JSON_TYPES_AND_DESERIALIZATION_FUNCTIONS.get(expected_type.name)
    if types_and_deserialization is None:
        raise TypeError(
            f"Unexpected GraphQLType {expected_type}. No deserialization function known."
        )
    expected_python_types, deserialization_function = types_and_deserialization
    if not isinstance(value, expected_python_types):
        raise TypeError(
            f"{value} ({type(value)} cannot be deserialized to GraphQL type {expected_type}."
        )
    return deserialization_function(value)


def deserialize_scalar_argument(name: str, expected_type: GraphQLScalarType, value: Any) -> Any:
    """Deserialize a serialized scalar argument. See docstring of deserialize_argument.

    Args:
        name: the name of the argument.
        expected_type: a GraphQLScalarType to which value should be converted.
        value: object that can be interpreted as being of expected_type.

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
    # Explicitly disallow passing boolean values for non-boolean types.
    if isinstance(value, bool) and not is_same_type(GraphQLBoolean, expected_type):
        raise GraphQLInvalidArgumentError("")
    try:
        return convert_scalar_value_to_graphql_type(expected_type, value)
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
        name: he name of the argument. It will be used to provide a more descriptive error
              message if an error is raised.
        expected_type: the GraphQL type. All GraphQLNonNull type wrappers are stripped.
        value: object that can be interpreted as being of that type.

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
            raise GraphQLInvalidArgumentError(
                f"Attempted to convert argument {name} to a GraphQLList, but {name} had a non-list "
                f"value {value}."
            )

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
    return {
        name: deserialize_argument(name, expected_types[name], value)
        for name, value in arguments.items()
    }
