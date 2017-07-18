# Copyright 2017 Kensho Technologies, Inc.
"""Commonly-used functions and data types from this package."""
from .compiler import CompilationResult, OutputMetadata  # noqa
from .compiler import compile_graphql_to_gremlin, compile_graphql_to_match  # noqa
from .query_formatting import insert_arguments_into_query  # noqa

from .exceptions import GraphQLError  # noqa
from .exceptions import GraphQLParsingError, GraphQLCompilationError  # noqa
from .exceptions import GraphQLValidationError, GraphQLInvalidArgumentError  # noqa

from .schema import DIRECTIVES  # noqa
from .schema import GraphQLDate, GraphQLDateTime  # noqa


def graphql_to_match(schema, graphql_query, parameters):
    """Compile the GraphQL input using the schema into a MATCH query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_string: the GraphQL query to compile to MATCH, as a basestring
        parameters: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        a CompilationResult object, containing:
            - query: basestring, the resulting compiled and parameterized query string
            - language: basestring, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_match(schema, graphql_query)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters))


def graphql_to_gremlin(schema, graphql_query, parameters, type_equivalence_hints=None):
    """Compile the GraphQL input using the schema into a Gremlin query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_string: the GraphQL query to compile to Gremlin, as a basestring
        parameters: dict, mapping argument name to its value, for every parameter the query expects.
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for Gremlin's lack of inheritance-awareness.
                                When this parameter is not specified or is empty, type coercion
                                coerces to the *exact* type being coerced to without regard for
                                subclasses of that type. This parameter allows the user to
                                manually specify which GraphQL interfaces and types are
                                superclasses of which other types, and emits Gremlin code
                                that performs type coercion with this information in mind.
                                No recursive expansion of type equivalence hints will be performed,
                                and only type-level correctness of the hints is enforced.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        a CompilationResult object, containing:
            - query: basestring, the resulting compiled and parameterized query string
            - language: basestring, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_gremlin(schema, graphql_query)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters))
