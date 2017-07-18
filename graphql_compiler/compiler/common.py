# Copyright 2017 Kensho Technologies, Inc.
from collections import namedtuple

from . import emit_gremlin, emit_match, ir_lowering_gremlin, ir_lowering_match
from .compiler_frontend import graphql_to_ir


# The CompilationResult will have the following types for its members:
# - query: basestring, the resulting compiled query string, with placeholders for parameters
# - language: basestring, specifying the language to which the query was compiled
# - output_metadata: dict, output name -> OutputMetadata namedtuple object
# - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
CompilationResult = namedtuple('CompilationResult',
                               ('query', 'language', 'output_metadata', 'input_metadata'))

MATCH_LANGUAGE = 'MATCH'
GREMLIN_LANGUAGE = 'Gremlin'


def _preprocess_graphql_string(graphql_string):
    """Apply any necessary preprocessing to the input GraphQL string, returning the new version."""
    # HACK(predrag): Workaround for graphql-core issue, to avoid needless errors:
    #                https://github.com/graphql-python/graphql-core/issues/98
    return graphql_string + '\n'


def compile_graphql_to_match(schema, graphql_string):
    """Compile the GraphQL input using the schema into a MATCH query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_string: the GraphQL query to compile to MATCH, as a basestring

    Returns:
        a CompilationResult object
    """
    graphql_string = _preprocess_graphql_string(graphql_string)

    ir_blocks, output_metadata, input_metadata, location_types = \
        graphql_to_ir(schema, graphql_string)

    lowered_ir_blocks = ir_lowering_match.lower_ir(ir_blocks, location_types)

    query = emit_match.emit_code_from_ir(lowered_ir_blocks)

    return CompilationResult(
        query=query,
        language=MATCH_LANGUAGE,
        output_metadata=output_metadata,
        input_metadata=input_metadata)


def compile_graphql_to_gremlin(schema, graphql_string, type_equivalence_hints=None):
    """Compile the GraphQL input using the schema into a Gremlin query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_string: the GraphQL query to compile to Gremlin, as a basestring
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
        a CompilationResult object
    """
    graphql_string = _preprocess_graphql_string(graphql_string)

    ir_blocks, output_metadata, input_metadata, location_types = \
        graphql_to_ir(schema, graphql_string)

    lowered_ir_blocks = ir_lowering_gremlin.lower_ir(ir_blocks, location_types,
                                                     type_equivalence_hints=type_equivalence_hints)

    query = emit_gremlin.emit_code_from_ir(lowered_ir_blocks)

    return CompilationResult(
        query=query,
        language=GREMLIN_LANGUAGE,
        output_metadata=output_metadata,
        input_metadata=input_metadata)
