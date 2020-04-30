# Copyright 2020-present Kensho Technologies, LLC.
from typing import Union

from graphql import GraphQLList, GraphQLNonNull, GraphQLScalarType


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
