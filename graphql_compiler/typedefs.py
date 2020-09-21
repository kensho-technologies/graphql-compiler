# Copyright 2020-present Kensho Technologies, LLC.
from typing import Union

from graphql import GraphQLList, GraphQLNonNull, GraphQLScalarType


# The below code contains import shims for typing constructs introduced after Python 3.6:
# we don't want to conditionally import them from every file that needs them. Instead, we
# conditionally import them here and then import from this file in every other location where
# they is needed.
#
# Hence, the "unused import" warnings here are false-positives.
try:
    from typing import TypedDict  # noqa  # pylint: disable=unused-import
except ImportError:  # TypedDict was only added to typing in Python 3.8
    from typing_extensions import TypedDict  # noqa  # pylint: disable=unused-import

try:
    from typing import Literal  # noqa  # pylint: disable=unused-import
except ImportError:
    from typing_extensions import Literal  # type: ignore  # noqa  # pylint: disable=unused-import

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
