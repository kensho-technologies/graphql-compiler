# Copyright 2017-present Kensho Technologies, LLC.
from collections import namedtuple

from . import emit_gremlin, emit_match, ir_lowering_gremlin, ir_lowering_match
from .compiler_frontend import graphql_to_ir


# The CompilationResult will have the following types for its members:
# - query: string, the resulting compiled query string, with placeholders for parameters
# - language: string, specifying the language to which the query was compiled
# - output_metadata: dict, output name -> OutputMetadata namedtuple object
# - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
CompilationResult = namedtuple('CompilationResult',
                               ('query', 'language', 'output_metadata', 'input_metadata'))

MATCH_LANGUAGE = 'MATCH'
GREMLIN_LANGUAGE = 'Gremlin'


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
    lowering_func = ir_lowering_match.lower_ir
    query_emitter_func = emit_match.emit_code_from_ir

    return _compile_graphql_generic(
        MATCH_LANGUAGE, lowering_func, query_emitter_func,
        schema, graphql_string, type_equivalence_hints)


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
    lowering_func = ir_lowering_gremlin.lower_ir
    query_emitter_func = emit_gremlin.emit_code_from_ir

    return _compile_graphql_generic(
        GREMLIN_LANGUAGE, lowering_func, query_emitter_func,
        schema, graphql_string, type_equivalence_hints)


def _compile_graphql_generic(language, lowering_func, query_emitter_func,
                             schema, graphql_string, type_equivalence_hints):
    """Compile the GraphQL input, lowering and emitting the query using the given functions."""
    ir_and_metadata = graphql_to_ir(
        schema, graphql_string, type_equivalence_hints=type_equivalence_hints)

    lowered_ir_blocks = lowering_func(
        ir_and_metadata.ir_blocks, ir_and_metadata.location_types,
        ir_and_metadata.coerced_locations,
        type_equivalence_hints=type_equivalence_hints)

    query = query_emitter_func(lowered_ir_blocks)

    return CompilationResult(
        query=query,
        language=language,
        output_metadata=ir_and_metadata.output_metadata,
        input_metadata=ir_and_metadata.input_metadata)
