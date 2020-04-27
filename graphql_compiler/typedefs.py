from typing import Union

from graphql import GraphQLList, GraphQLNonNull, GraphQLScalarType


# Supported types for query arguments.
GraphQLArgumentType = Union[
    GraphQLScalarType,
    GraphQLList[GraphQLScalarType],
    GraphQLList[GraphQLNonNull[GraphQLScalarType]],
    GraphQLNonNull[GraphQLScalarType],
    GraphQLNonNull[GraphQLList[GraphQLScalarType]],
    GraphQLNonNull[GraphQLList[GraphQLNonNull[GraphQLScalarType]]],
]
