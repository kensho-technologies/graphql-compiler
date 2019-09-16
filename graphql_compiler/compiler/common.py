# Copyright 2017-present Kensho Technologies, LLC.
from collections import namedtuple

from .. import backend
from ..schema.schema_info import CommonSchemaInfo
from .compiler_frontend import graphql_to_ir


# The CompilationResult will have the following types for its members:
# - query: Union[String, sqlalchemy Query], the resulting compiled query, with placeholders for
#          parameters.
# - language: string, specifying the language to which the query was compiled
# - output_metadata: dict, output name -> OutputMetadata namedtuple object
# - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
CompilationResult = namedtuple('CompilationResult',
                               ('query', 'language', 'output_metadata', 'input_metadata'))

MATCH_LANGUAGE = backend.match_backend.language
GREMLIN_LANGUAGE = backend.gremlin_backend.language
SQL_LANGUAGE = backend.sql_backend.language
CYPHER_LANGUAGE = backend.cypher_backend.language


def compile_graphql_to_match(schema, graphql_string, type_equivalence_hints=None):
    """Compile the GraphQL input using the schema into a MATCH query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_string: the GraphQL query to compile to MATCH, as a string
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        a CompilationResult object
    """
    schema_info = CommonSchemaInfo(schema, type_equivalence_hints)
    return _compile_graphql_generic(backend.match_backend, schema_info, graphql_string)


def compile_graphql_to_gremlin(schema, graphql_string, type_equivalence_hints=None):
    """Compile the GraphQL input using the schema into a Gremlin query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_string: the GraphQL query to compile to Gremlin, as a string
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        a CompilationResult object
    """
    schema_info = CommonSchemaInfo(schema, type_equivalence_hints)
    return _compile_graphql_generic(backend.gremlin_backend, schema_info, graphql_string)


def compile_graphql_to_sql(sql_schema_info, graphql_string):
    """Compile the GraphQL input using the schema into a SQL query and associated metadata.

    Args:
        sql_schema_info: SQLAlchemySchemaInfo used to compile the query.
        graphql_string: the GraphQL query to compile to SQL, as a string

    Returns:
        a CompilationResult object
    """
    return _compile_graphql_generic(backend.sql_backend, sql_schema_info, graphql_string)


def compile_graphql_to_cypher(schema, graphql_string, type_equivalence_hints=None):
    """Compile the GraphQL input using the schema into a Cypher query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_string: the GraphQL query to compile to Cypher, as a string
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        a CompilationResult object
    """
    schema_info = CommonSchemaInfo(schema, type_equivalence_hints)
    return _compile_graphql_generic(backend.cypher_backend, schema_info, graphql_string)


def _compile_graphql_generic(target_backend, schema_info, graphql_string):
    """Compile the GraphQL input, lowering and emitting the query using the given functions.

    Args:
        target_backend: Backend used to compile the query
        schema_info: target_backend.schemaInfoClass containing all necessary schema information.
        graphql_string: the GraphQL query to compile to the target language, as a string.

    Returns:
        a CompilationResult object
    """
    ir_and_metadata = graphql_to_ir(
        schema_info.schema, graphql_string,
        type_equivalence_hints=schema_info.type_equivalence_hints)

    lowered_ir_blocks = target_backend.lower_func(schema_info, ir_and_metadata)
    query = target_backend.emit_func(schema_info, lowered_ir_blocks)
    return CompilationResult(
        query=query,
        language=target_backend.language,
        output_metadata=ir_and_metadata.output_metadata,
        input_metadata=ir_and_metadata.input_metadata)
