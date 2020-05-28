# Copyright 2017-present Kensho Technologies, LLC.
"""Commonly-used functions and data types from this package."""
from typing import Any, Dict

from .compiler import (  # noqa
    CompilationResult,
    OutputMetadata,
    compile_graphql_to_cypher,
    compile_graphql_to_gremlin,
    compile_graphql_to_match,
    compile_graphql_to_sql,
)
from .exceptions import (  # noqa
    GraphQLCompilationError,
    GraphQLError,
    GraphQLInvalidArgumentError,
    GraphQLParsingError,
    GraphQLValidationError,
)
from .query_formatting import insert_arguments_into_query  # noqa
from .query_formatting.graphql_formatting import pretty_print_graphql  # noqa
from .schema import (  # noqa
    DIRECTIVES,
    EXTENDED_META_FIELD_DEFINITIONS,
    GraphQLDate,
    GraphQLDateTime,
    GraphQLDecimal,
    insert_meta_fields_into_existing_schema,
    is_meta_field,
)
from .schema.schema_info import CommonSchemaInfo, SQLSchemaInfo
from .schema_generation.orientdb import get_graphql_schema_from_orientdb_schema_data  # noqa
from .schema_generation.sqlalchemy import get_sql_schema_info  # noqa


__package_name__ = "graphql-compiler"
__version__ = "1.11.0"


def graphql_to_match(
    common_schema_info: CommonSchemaInfo, graphql_query: str, parameters: Dict[str, Any]
) -> CompilationResult:
    """Compile the GraphQL input using the schema into a MATCH query and associated metadata.

    Args:
        common_schema_info: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: str, GraphQL query to compile to MATCH
        parameters: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        CompilationResult object, containing:
            - query: string, the resulting compiled and parameterized query string
            - language: string, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_match(common_schema_info, graphql_query)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters)
    )


def graphql_to_sql(
    sql_schema_info: SQLSchemaInfo, graphql_query: str, parameters: Dict[str, Any]
) -> CompilationResult:
    """Compile the GraphQL input using the schema into a SQL query and associated metadata.

    Args:
        sql_schema_info: SQLSchemaInfo used to compile the query.
        graphql_query: str, GraphQL query to compile to SQL
        parameters: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        CompilationResult object, containing:
            - query: sqlalchemy Query, the resulting compiled and parameterized query. It can be
                     executed in a sqlalchemy Engine which can be created through the
                     sqlalchemy.create_engine function.
            - language: string, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_sql(sql_schema_info, graphql_query)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters)
    )


def graphql_to_gremlin(
    common_schema_info: CommonSchemaInfo, graphql_query: str, parameters: Dict[str, Any]
) -> CompilationResult:
    """Compile the GraphQL input using the schema into a Gremlin query and associated metadata.

    Args:
        common_schema_info: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: str, GraphQL query to compile to Gremlin

    Returns:
        CompilationResult object, containing:
            - query: string, the resulting compiled and parameterized query string
            - language: string, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_gremlin(common_schema_info, graphql_query)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters)
    )


def graphql_to_redisgraph_cypher(
    common_schema_info: CommonSchemaInfo, graphql_query: str, parameters: Dict[str, Any]
) -> CompilationResult:
    """Compile the GraphQL input into a RedisGraph Cypher query and associated metadata.

    Note that the corresponding function that would convert GraphQL to Cypher for Neo4j does not
    exist because Neo4j supports query parameters but RedisGraph doesn't. So, for Neo4j we will use
    the Neo4j client's own query parameter handling method but for RedisGraph we'll manually
    interpolate values in the query string.

    See README.md for a more detailed explanation.

    Args:
        common_schema_info: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: str, GraphQL query to compile to Cypher

    Returns:
        CompilationResult object, containing:
            - query: string, the resulting compiled and parameterized query string
            - language: string, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_cypher(common_schema_info, graphql_query)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters)
    )
