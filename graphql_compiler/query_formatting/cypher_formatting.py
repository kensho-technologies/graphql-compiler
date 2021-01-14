# Copyright 2019-present Kensho Technologies, LLC.
import datetime
import json
from string import Template

from graphql import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import six

from ..compiler import CYPHER_LANGUAGE
from ..compiler.helpers import strip_non_null_from_type
from ..exceptions import GraphQLInvalidArgumentError
from ..global_utils import is_same_type
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from .representations import represent_float_as_str, type_check_and_str


def _safe_cypher_string(argument_value):
    """Sanitize and represent a string argument in Cypher."""
    if not isinstance(argument_value, six.string_types):
        if isinstance(argument_value, bytes):  # likely to only happen in py2
            argument_value = argument_value.decode("utf-8")
        else:
            raise GraphQLInvalidArgumentError(
                "Attempting to convert a non-string into a string: {}".format(argument_value)
            )

    # Using JSON encoding means that all unicode literals and special chars
    # (e.g. newlines and backslashes) are replaced by appropriate escape sequences.
    # Unlike with Gremlin, unescaped dollar signs $ are not a problem when contained in a
    # string literal in Cypher because they do not allow for arbitrary code execution.
    escaped_and_quoted = json.dumps(argument_value)
    return escaped_and_quoted


def _safe_cypher_decimal(argument_value):
    """Cypher doesn't support decimals, only ints and floats, so we'll raise an error here."""
    raise NotImplementedError(
        "Cypher doesn't support Decimals, only ints and floats. See "
        "OpenCypher documentation. Argument value was {}".format(argument_value)
    )


def _safe_cypher_date_and_datetime(graphql_type, expected_python_types, value):
    """Represent date and datetime objects as Cypher strings."""
    # Note: since Neo4j's python client can handle parameters on its own, we only need to insert
    # query parameters manually for RedisGraph. RedisGraph doesn't support temporal values, so we
    # raise an error if we get a temporal value.
    raise NotImplementedError(
        "RedisGraph currently doesn't support temporal types like Date and Datetime."
    )


def _safe_cypher_list(inner_type, argument_value):
    """Represent the list of "inner_type" objects in Cypher form."""
    stripped_type = strip_non_null_from_type(inner_type)
    if isinstance(stripped_type, GraphQLList):
        raise GraphQLInvalidArgumentError(
            "Cypher does not currently support nested lists, "
            "but inner type was {}: "
            "{}".format(inner_type, argument_value)
        )

    if not isinstance(argument_value, list):
        raise GraphQLInvalidArgumentError(
            "Attempting to represent a non-list as a list: {}".format(argument_value)
        )

    components = (_safe_cypher_argument(stripped_type, x) for x in argument_value)
    return "[" + ",".join(components) + "]"


def _safe_cypher_argument(expected_type, argument_value):
    """Return a Cypher string representing the given argument value."""
    if is_same_type(GraphQLString, expected_type):
        return _safe_cypher_string(argument_value)
    elif is_same_type(GraphQLID, expected_type):
        # IDs can be strings or numbers, but the GraphQL library coerces them to strings.
        # We will follow suit and treat them as strings.
        if not isinstance(argument_value, six.string_types):
            if isinstance(argument_value, bytes):  # likely to only happen in py2
                argument_value = argument_value.decode("utf-8")
            else:
                argument_value = six.text_type(argument_value)
        return _safe_cypher_string(argument_value)
    elif is_same_type(GraphQLFloat, expected_type):
        return represent_float_as_str(argument_value)
    elif is_same_type(GraphQLInt, expected_type):
        # Special case: in Python, isinstance(True, int) returns True.
        # Safeguard against this with an explicit check against bool type.
        if isinstance(argument_value, bool):
            raise GraphQLInvalidArgumentError(
                "Attempting to represent a non-int as an int: {}".format(argument_value)
            )
        return type_check_and_str(int, argument_value)
    elif is_same_type(GraphQLBoolean, expected_type):
        return type_check_and_str(bool, argument_value)
    elif is_same_type(GraphQLDecimal, expected_type):
        return _safe_cypher_decimal(argument_value)
    elif is_same_type(GraphQLDate, expected_type):
        return _safe_cypher_date_and_datetime(expected_type, (datetime.date,), argument_value)
    elif is_same_type(GraphQLDateTime, expected_type):
        return _safe_cypher_date_and_datetime(expected_type, (datetime.datetime,), argument_value)
    elif isinstance(expected_type, GraphQLList):
        return _safe_cypher_list(expected_type.of_type, argument_value)
    else:
        raise AssertionError(
            "Could not safely represent the requested GraphQL type: "
            "{} {}".format(expected_type, argument_value)
        )


######
# Public API
######


def insert_arguments_into_cypher_query_redisgraph(compilation_result, arguments):
    """Insert the arguments into the compiled Cypher query to form a complete query.

    This is only for Redisgraph because Neo4j's client can do this on its own.
    Redisgraph doesn't support parameterized queries (as described in the Github issue:
    https://github.com/RedisGraph/RedisGraph/issues/544#issuecomment-507963576
    work is only expected to start in August 2019).

    Args:
        compilation_result: a CompilationResult object derived from the GraphQL compiler
        arguments: dict, str -> any, mapping argument name to its value, for every parameter the
                    query expects.

    Returns:
        string, a Cypher query with inserted argument data.
    """
    if compilation_result.language != CYPHER_LANGUAGE:
        raise AssertionError("Unexpected query output language: {}".format(compilation_result))

    base_query = compilation_result.query
    argument_types = compilation_result.input_metadata

    # The arguments are assumed to have already been validated against the query.
    sanitized_arguments = {
        key: _safe_cypher_argument(argument_types[key], value)
        for key, value in six.iteritems(arguments)
    }

    return Template(base_query).substitute(sanitized_arguments)


######
