# Copyright 2017-present Kensho Technologies, LLC.
"""Commonly-used functions and data types from this package."""
from .compiler import (  # noqa
    CompilationResult,
    OutputMetadata,
    compile_graphql_to_gremlin,
    compile_graphql_to_match,
    compile_graphql_to_sql,
)
from .query_formatting import insert_arguments_into_query  # noqa
from .query_formatting.graphql_formatting import pretty_print_graphql  # noqa
from .exceptions import (  # noqa
    GraphQLCompilationError, GraphQLError, GraphQLInvalidArgumentError, GraphQLParsingError,
    GraphQLValidationError
)
from .schema import (  # noqa
    DIRECTIVES, EXTENDED_META_FIELD_DEFINITIONS, GraphQLDate, GraphQLDateTime, GraphQLDecimal,
    insert_meta_fields_into_existing_schema, is_meta_field
)
from .schema_generation.schema_graph import SchemaGraph
from .schema_generation.schema_properties import ORIENTDB_BASE_VERTEX_CLASS_NAME
from .schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from .schema_generation.utils import toposort_classes


__package_name__ = 'graphql-compiler'
__version__ = '1.10.0'

# Match query used to generate OrientDB records that are themselves used to generate GraphQL schema.
ORIENTDB_SCHEMA_RECORDS_QUERY = (
    'SELECT FROM (SELECT expand(classes) FROM metadata:schema) '
    'WHERE name NOT IN [\'ORole\', \'ORestricted\', \'OTriggered\', '
    '\'ORIDs\', \'OUser\', \'OIdentity\', \'OSchedule\', \'OFunction\']'
)

def graphql_to_match(schema, graphql_query, parameters, type_equivalence_hints=None):
    """Compile the GraphQL input using the schema into a MATCH query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: the GraphQL query to compile to MATCH, as a string
        parameters: dict, mapping argument name to its value, for every parameter the query expects.
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
        a CompilationResult object, containing:
            - query: string, the resulting compiled and parameterized query string
            - language: string, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_match(
        schema, graphql_query, type_equivalence_hints=type_equivalence_hints)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters))


def graphql_to_sql(schema, graphql_query, parameters, compiler_metadata,
                   type_equivalence_hints=None):
    """Compile the GraphQL input using the schema into a SQL query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: the GraphQL query to compile to SQL, as a string
        parameters: dict, mapping argument name to its value, for every parameter the query expects.
        compiler_metadata: CompilerMetadata object, provides SQLAlchemy specific backend
                           information
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
        a CompilationResult object, containing:
            - query: string, the resulting compiled and parameterized query string
            - language: string, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_sql(
        schema, graphql_query, compiler_metadata, type_equivalence_hints=type_equivalence_hints)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters))


def graphql_to_gremlin(schema, graphql_query, parameters, type_equivalence_hints=None):
    """Compile the GraphQL input using the schema into a Gremlin query and associated metadata.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: the GraphQL query to compile to Gremlin, as a string
        parameters: dict, mapping argument name to its value, for every parameter the query expects.
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
        a CompilationResult object, containing:
            - query: string, the resulting compiled and parameterized query string
            - language: string, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_gremlin(
        schema, graphql_query, type_equivalence_hints=type_equivalence_hints)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters))


def get_graphql_schema_from_orientdb_records(schema_records, class_to_field_type_overrides=None,
                                             hidden_classes=None):
    """Construct a GraphQL schema from a list of OrientDB schema records.

    Args:
        schema_records: list of pyorient.otypes.OrientRecord describing the OrientDB schema.
                        Generated by running ORIENTDB_SCHEMA_RECORDS_QUERY on OrientDB.
        class_to_field_type_overrides: optional dict, class name -> {field name -> field type},
                                       (string -> {string -> GraphQLType}). Used to override the
                                       type of a field in the class where it's first defined and all
                                       the the class's subclasses.
        hidden_classes: optional set of strings, classes to not include in the GraphQL schema.

    Returns:
        tuple (GraphQL schema object, GraphQL type equivalence hints dict), or (None, None)
        if there is no schema data in the graph yet.
        For example, the graph has no schema data if applying schema updates from the very
        first update. We have to return None because the GraphQL library does not support
        empty schema objects -- the root object must have some keys and values.
    """
    schema_query_data = toposort_classes([x.oRecordData for x in schema_records])
    schema_graph = SchemaGraph(schema_query_data)
    # If the OrientDB base vertex class no properties defined, hide it since
    # classes with no properties are not representable in the GraphQL schema.
    base_vertex = schema_graph.get_element_by_class_name(ORIENTDB_BASE_VERTEX_CLASS_NAME)
    if len(base_vertex.properties) == 0:
        if hidden_classes is None:
            hidden_classes = set()
        hidden_classes.add(ORIENTDB_BASE_VERTEX_CLASS_NAME)
    return get_graphql_schema_from_schema_graph(schema_graph, class_to_field_type_overrides,
                                                hidden_classes)
