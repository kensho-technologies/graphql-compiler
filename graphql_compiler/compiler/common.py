# Copyright 2017-present Kensho Technologies, LLC.
from collections import namedtuple
from typing import Union

from .. import backend
from ..backend import Backend
from ..schema.schema_info import CommonSchemaInfo, SQLAlchemySchemaInfo
from .compiler_frontend import graphql_to_ir


# The CompilationResult will have the following types for its members:
# - query: Union[String, sqlalchemy Query], the resulting compiled query, with placeholders for
#          parameters.
# - language: string, specifying the language to which the query was compiled
# - output_metadata: dict, output name -> OutputMetadata namedtuple object
# - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
CompilationResult = namedtuple(
    "CompilationResult", ("query", "language", "output_metadata", "input_metadata")
)

MATCH_LANGUAGE = backend.match_backend.language
GREMLIN_LANGUAGE = backend.gremlin_backend.language
SQL_LANGUAGE = backend.sql_backend.language
CYPHER_LANGUAGE = backend.cypher_backend.language


def compile_graphql_to_match(
    common_schema_info: CommonSchemaInfo, graphql_query: str
) -> CompilationResult:
    """Compile the GraphQL input using the schema into a MATCH query and associated metadata.

    Args:
        common_schema_info: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: str, GraphQL query to compile to MATCH

    Returns:
        CompilationResult object
    """
    return _compile_graphql_generic(backend.match_backend, common_schema_info, graphql_query)


def compile_graphql_to_gremlin(
    common_schema_info: CommonSchemaInfo, graphql_query: str
) -> CompilationResult:
    """Compile the GraphQL input using the schema into a Gremlin query and associated metadata.

    Args:
        common_schema_info: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: the GraphQL query to compile to Gremlin, as a string

    Returns:
        CompilationResult object
    """
    return _compile_graphql_generic(backend.gremlin_backend, common_schema_info, graphql_query)


def compile_graphql_to_sql(
    sql_schema_info: SQLAlchemySchemaInfo, graphql_query: str
) -> CompilationResult:
    """Compile the GraphQL input using the schema into a SQL query and associated metadata.

    Args:
        sql_schema_info: SQLAlchemySchemaInfo used to compile the query.
        graphql_query: str, GraphQL query to compile to SQL

    Returns:
        CompilationResult object
    """
    return _compile_graphql_generic(backend.sql_backend, sql_schema_info, graphql_query)


def compile_graphql_to_cypher(
    common_schema_info: CommonSchemaInfo, graphql_query: str
) -> CompilationResult:
    """Compile the GraphQL input using the schema into a Cypher query and associated metadata.

    Args:
        common_schema_info: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: the GraphQL query to compile to Cypher, as a string

    Returns:
        CompilationResult object
    """
    return _compile_graphql_generic(backend.cypher_backend, common_schema_info, graphql_query)


def _compile_graphql_generic(
    target_backend: Backend,
    schema_info: Union[CommonSchemaInfo, SQLAlchemySchemaInfo],
    graphql_string: str,
) -> CompilationResult:
    """Compile the GraphQL input, lowering and emitting the query using the given functions.

    Args:
        target_backend: Backend used to compile the query
        schema_info: target_backend.schemaInfoClass containing all necessary schema information.
        graphql_string: str, GraphQL query to compile to the target language

    Returns:
        CompilationResult object
    """
    ir_and_metadata = graphql_to_ir(
        schema_info.schema,
        graphql_string,
        type_equivalence_hints=schema_info.type_equivalence_hints,
    )

    lowered_ir_blocks = target_backend.lower_func(schema_info, ir_and_metadata)
    query = target_backend.emit_func(schema_info, lowered_ir_blocks)
    return CompilationResult(
        query=query,
        language=target_backend.language,
        output_metadata=ir_and_metadata.output_metadata,
        input_metadata=ir_and_metadata.input_metadata,
    )
