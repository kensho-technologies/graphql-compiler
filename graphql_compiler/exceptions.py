# Copyright 2017-present Kensho Technologies, LLC.
class GraphQLError(Exception):
    """Generic error when processing GraphQL."""


class GraphQLParsingError(GraphQLError):
    """Exception raised when the provided GraphQL string could not be parsed."""


class GraphQLValidationError(GraphQLError):
    """Exception raised when the provided GraphQL does not validate against the provided schema."""


class GraphQLCompilationError(GraphQLError):
    """Exception raised when the provided GraphQL cannot be compiled.

    This could be due to many reasons, such as:
    - the GraphQL has more than one root selection;
    - the GraphQL has directives in unsupported locations, e.g. vertex-only directive on property;
    - the GraphQL provides invalid / disallowed / wrong number of arguments.
    """


class GraphQLInvalidArgumentError(GraphQLError):
    """Exception raised when the arguments to a GraphQL query are invalid.

    For example:
    - there may be unexpected arguments;
    - expected arguments may be missing;
    - an argument may be of incorrect type (e.g. expected an int but received a string).
    """
