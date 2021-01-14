# Copyright 2020-present Kensho Technologies, LLC.
import sys
from typing import Union

from graphql import GraphQLList, GraphQLNonNull, GraphQLScalarType
from graphql.language.ast import (
    BooleanValueNode,
    EnumValueNode,
    FloatValueNode,
    IntValueNode,
    StringValueNode,
)


# The below code is an import shim for libraries added in Python 3.8: we don't want to conditionally
# import them from every file that needs them. Instead, we conditionally import them here and then
# import from this file in every other location where they are needed.
#
# We prefer the explicit sys.version_info check instead of the more common try-except ImportError
# approach, because at the moment mypy seems to have an easier time with the sys.version_info check:
# https://github.com/python/mypy/issues/1393
#
# Hence, the "unused import" warnings here are false-positives.
if sys.version_info[:2] >= (3, 8):
    # These were only added to typing in Python 3.8
    from typing import Literal, TypedDict, Protocol  # noqa  # pylint: disable=unused-import
else:
    from typing_extensions import (  # noqa  # pylint: disable=unused-import
        Literal,
        TypedDict,
        Protocol,
    )

# #####################
# End of import shims #
# #####################


# The compiler's supported GraphQL types for query arguments. The GraphQL type of a query argument
# is the type of the field that the argument references. Not to be confused with the GraphQLArgument
# class in the GraphQL core library.
QueryArgumentGraphQLType = Union[
    GraphQLScalarType,
    GraphQLList[GraphQLScalarType],
    GraphQLList[GraphQLNonNull[GraphQLScalarType]],
    GraphQLNonNull[GraphQLScalarType],
    GraphQLNonNull[GraphQLList[GraphQLScalarType]],
    GraphQLNonNull[GraphQLList[GraphQLNonNull[GraphQLScalarType]]],
]

ScalarConstantValueNodes = (
    BooleanValueNode,
    EnumValueNode,
    FloatValueNode,
    IntValueNode,
    StringValueNode,
)
