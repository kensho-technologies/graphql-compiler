# Copyright 2020-present Kensho Technologies, LLC.
"""Convert values to their underlying GraphQLType."""
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Callable, Mapping, Tuple, Type

from graphql import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLScalarType,
    GraphQLString,
)

from .compiler.helpers import strip_non_null_from_type
from .global_utils import assert_set_equality, is_same_type
from .schema import SUPPORTED_SCALAR_TYPES, GraphQLDate, GraphQLDateTime, GraphQLDecimal
from .typedefs import QueryArgumentGraphQLType


_ALLOWED_SCALAR_TYPES: Mapping[str, Tuple[Type, ...]] = MappingProxyType(
    {
        GraphQLDate.name: (str, date),
        GraphQLDateTime.name: (str, date, datetime),
        GraphQLFloat.name: (str, float, int),
        GraphQLDecimal.name: (str, float, int),
        GraphQLInt.name: (int, str),
        GraphQLString.name: (str,),
        GraphQLBoolean.name: (bool, int, str),
        GraphQLID.name: (int, str),
    }
)
assert_set_equality(
    set(_ALLOWED_SCALAR_TYPES.keys()),
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
            f"Received unexpected GraphQLBoolean value {value} of type {type(value)}. Expected one "
            f"of: {true_values + false_values}."
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

_ALLOWED_TYPES_AND_DESERIALIZATION_FUNCTIONS: Mapping[
    str, Tuple[Tuple[Type, ...], Callable[[Any], Any]]
] = MappingProxyType(
    {
        scalar_type.name: (
            _ALLOWED_SCALAR_TYPES[scalar_type.name],
            _CUSTOM_SCALAR_DESERIALIZATION_FUNCTIONS.get(scalar_type.name, scalar_type.parse_value),
        )
        for scalar_type in SUPPORTED_SCALAR_TYPES
    }
)


def deserialize_scalar_value(expected_type: GraphQLScalarType, value: Any) -> Any:
    """Convert a scalar value to the appropriate type for the given GraphQLScalarType.

    Below are examples of accepted encodings of all the types:
        GraphQLDate: "2018-02-01"
        GraphQLDateTime: "2018-02-01T05:11:54"
        GraphQLFloat: 4.3, "5.0", 5
        GraphQLDecimal: "5.00000000000000000000000000001"
        GraphQLInt: 4, "3803330000000000000000000000000000000000000000000"
        GraphQLString: "Hello"
        GraphQLBoolean: True, 1, "1", "True", "true"
        GraphQLID: "13d72846-1777-6c3a-5743-5d9ced3032ed"

    Args:
        expected_type: a GraphQLScalarType to which value should be converted.
        value: object that can be interpreted as being of expected_type.

    Returns:
        a value of the type produced by the parser of the expected type:
            GraphQLDate: datetime.date
            GraphQLDateTime: datetime.datetime with tzinfo=None
            GraphQLFloat: float
            GraphQLDecimal: decimal.Decimal
            GraphQLInt: int
            GraphQLString: str
            GraphQLBoolean: bool
            GraphQLID: str

    Raises:
        ValueError: if the value is not appropriate for the type. ValueError is chosen because
                    it is already the base case of exceptions raised by the GraphQL parsers.
    """
    types_and_deserialization = _ALLOWED_TYPES_AND_DESERIALIZATION_FUNCTIONS.get(expected_type.name)
    if types_and_deserialization is None:
        raise AssertionError(
            f"Unexpected GraphQLType {expected_type}. No deserialization function known."
        )

    # Explicitly disallow passing boolean values for non-boolean types.
    if isinstance(value, bool) and not is_same_type(GraphQLBoolean, expected_type):
        raise ValueError(
            f"Cannot deserialize boolean value {value} to non-GraphQLBoolean type {expected_type}."
        )

    # Explicitly disallow passing datetime objects as date objects.
    # In Python, datetime subclasses date and therefore datetimes are treated as dates implicitly
    # by truncating the time and timezone components. However, this is a loss of precision,
    # and implicitly losing precision like this is undesirable for our purposes.
    if isinstance(value, datetime) and is_same_type(GraphQLDate, expected_type):
        raise ValueError(
            f"Cannot use the datetime object {value} as a GraphQL Date value. While Python "
            f"datetimes are subclasses of date, the default behavior of simply truncating the time "
            f"and time zone data is undesirable as an implicit default. Please instead use "
            f"a date object or a string representing a date in ISO-8601 'YYYY-MM-DD' format."
        )

    # Ensure value has an appropriate type and deserialize the value.
    expected_python_types, deserialization_function = types_and_deserialization
    if not isinstance(value, expected_python_types):
        raise ValueError(
            f"{value} ({type(value)} cannot be deserialized to GraphQL type {expected_type}."
        )
    return deserialization_function(value)


def deserialize_value(expected_type: QueryArgumentGraphQLType, value: Any) -> Any:
    """Convert a value to the appropriate type for the given GraphQLType.

    Accepted encodings include those described in deserialize_scalar_value and lists of
    GraphQLScalarType such as GraphQLList(GraphQLInt): [1, 2, 3]

    Args:
        expected_type: a GraphQLType to which value should be converted.
        value: object that can be interpreted as being of expected_type.

    Returns:
        a value of the type produced by the parser of the expected type:
            GraphQLDate: datetime.date
            GraphQLDateTime: datetime.datetime with tzinfo=None
            GraphQLFloat: float
            GraphQLDecimal: decimal.Decimal
            GraphQLInt: int
            GraphQLString: str
            GraphQLBoolean: bool
            GraphQLID: str
            GraphQLList: list of the inner type

    Raises:
        ValueError: if the value is not appropriate for the type. ValueError is chosen because
                    it is already the base case of exceptions raised by the GraphQL parsers.
    """
    stripped_type = strip_non_null_from_type(expected_type)
    if isinstance(stripped_type, GraphQLList):
        if not isinstance(value, list):
            raise ValueError(f"Cannot deserialize non-list value {value} to GraphQLList type.")
        inner_stripped_type = strip_non_null_from_type(stripped_type.of_type)

        return [deserialize_scalar_value(inner_stripped_type, element) for element in value]
    else:
        return deserialize_scalar_value(stripped_type, value)
