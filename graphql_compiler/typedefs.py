# Copyright 2020-present Kensho Technologies, LLC.
from typing import Union

from graphql import GraphQLList, GraphQLNonNull, GraphQLScalarType


try:
    from typing import TypedDict
except ImportError:  # TypedDict was only added to typing in Python 3.8
    from typing_extensions import TypedDict


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
