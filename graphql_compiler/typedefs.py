# Copyright 2020-present Kensho Technologies, LLC.
from typing import Union

from graphql import GraphQLList, GraphQLNonNull, GraphQLScalarType


# The below code is an import shim for TypedDict: we don't want to conditionally import it from
# every file that needs it. Instead, we conditionally import it here and then import from this file
# in every other location where this is needed.
#
# Hence, the "unused import" warnings on TypedDict here are false-positives.
try:
    from typing import TypedDict  # noqa  # pylint: disable=unused-import
except ImportError:  # TypedDict was only added to typing in Python 3.8
    from typing_extensions import TypedDict  # noqa  # pylint: disable=unused-import


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
