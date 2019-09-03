# Copyright 2017-present Kensho Technologies, LLC.
"""Commonly-used functions and data types from this package."""
from .compiler import (  # noqa
    CompilationResult, OutputMetadata, compile_graphql_to_cypher, compile_graphql_to_gremlin,
    compile_graphql_to_match, compile_graphql_to_sql
)
from .exceptions import (  # noqa
    GraphQLCompilationError, GraphQLError, GraphQLInvalidArgumentError, GraphQLParsingError,
    GraphQLValidationError
)
from .query_formatting import insert_arguments_into_query  # noqa
from .query_formatting.graphql_formatting import pretty_print_graphql  # noqa
from .schema import (  # noqa
    DIRECTIVES, EXTENDED_META_FIELD_DEFINITIONS, GraphQLDate, GraphQLDateTime, GraphQLDecimal,
    insert_meta_fields_into_existing_schema, is_meta_field
)
from .schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from .schema_generation.orientdb.schema_graph_builder import get_orientdb_schema_graph
from .schema_generation.sqlalchemy.schema_graph_builder import (
    get_sqlalchemy_schema_graph, get_restructured_edge_descriptors
)
from .schema.schema_info import make_sqlalchemy_schema_info




__package_name__ = 'graphql-compiler'
__version__ = '1.11.0'


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


def graphql_to_sql(sql_schema_info, graphql_query, parameters):
    """Compile the GraphQL input using the schema into a SQL query and associated metadata.

    Args:
        sql_schema_info: SQLAlchemySchemaInfo used to compile the query.
        graphql_string: the GraphQL query to compile to SQL, as a string
        parameters: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        a CompilationResult object, containing:
            - query: string, the resulting compiled and parameterized query string
            - language: string, specifying the language to which the query was compiled
            - output_metadata: dict, output name -> OutputMetadata namedtuple object
            - input_metadata: dict, name of input variables -> inferred GraphQL type, based on use
    """
    compilation_result = compile_graphql_to_sql(sql_schema_info, graphql_query)
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


def get_graphql_schema_from_orientdb_schema_data(schema_data, class_to_field_type_overrides=None,
                                                 hidden_classes=None):
    """Construct a GraphQL schema from an OrientDB schema.

    Args:
        schema_data: list of dicts describing the classes in the OrientDB schema. The following
                     format is the way the data is structured in OrientDB 2. See
                     the README.md file for an example of how to query this data.
                     Each dict has the following string fields:
                        - name: string, the name of the class.
                        - superClasses (optional): list of strings, the name of the class's
                                                   superclasses.
                        - superClass (optional): string, the name of the class's superclass. May be
                                                 used instead of superClasses if there is only one
                                                 superClass. Used for backwards compatibility with
                                                 OrientDB.
                        - customFields (optional): dict, string -> string, data defined on the class
                                                   instead of instances of the class.
                        - abstract: bool, true if the class is abstract.
                        - properties: list of dicts, describing the class's properties.
                                      Each property dictionary has the following string fields:
                                         - name: string, the name of the property.
                                         - type: int, builtin OrientDB type ID of the property.
                                                 See schema_properties.py for the mapping.
                                         - linkedType (optional): int, if the property is a
                                                                  collection of builtin OrientDB
                                                                  objects, then it indicates their
                                                                  type ID.
                                         - linkedClass (optional): string, if the property is a
                                                                   collection of class instances,
                                                                   then it indicates the name of
                                                                   the class. If class is an edge
                                                                   class, and the field name is
                                                                   either 'in' or 'out', then it
                                                                   describes the name of an
                                                                   endpoint of the edge.
                                         - defaultValue: string, the textual representation of the
                                                         default value for the property, as
                                                         returned by OrientDB's schema
                                                         introspection code, e.g., '{}' for
                                                         the embedded set type. Note that if the
                                                         property is a collection type, it must
                                                         have a default value.
        class_to_field_type_overrides: optional dict, class name -> {field name -> field type},
                                       (string -> {string -> GraphQLType}). Used to override the
                                       type of a field in the class where it's first defined and all
                                       the class's subclasses.
        hidden_classes: optional set of strings, classes to not include in the GraphQL schema.

    Returns:
        tuple of (GraphQL schema object, GraphQL type equivalence hints dict).
        The tuple is of type (GraphQLSchema, {GraphQLObjectType -> GraphQLUnionType}).
    """
    schema_graph = get_orientdb_schema_graph(schema_data, [])
    return get_graphql_schema_from_schema_graph(schema_graph, class_to_field_type_overrides,
                                                hidden_classes)


def graphql_to_redisgraph_cypher(schema, graphql_query, parameters, type_equivalence_hints=None):
    """Compile the GraphQL input into a RedisGraph Cypher query and associated metadata.

    Note that the corresponding function that would convert GraphQL to Cypher for Neo4j does not
    exist because Neo4j supports query parameters but RedisGraph doesn't. So, for Neo4j we will use
    the Neo4j client's own query parameter handling method but for RedisGraph we'll manually
    interpolate values in the query string.

    See README.md for a more detailed explanation.

    Args:
        schema: GraphQL schema object describing the schema of the graph to be queried
        graphql_query: the GraphQL query to compile to Cypher, as a string
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
    compilation_result = compile_graphql_to_cypher(
        schema, graphql_query, type_equivalence_hints=type_equivalence_hints)
    return compilation_result._replace(
        query=insert_arguments_into_query(compilation_result, parameters))


def get_sqlalchemy_schema_info(
    tables, sql_edge_descriptors, junction_tables, dialect, class_to_field_type_overrides=None
):
    """Return a SQLAlchemyInfo from the metadata.

    Args:
        tables: dict, str -> SQLAlchemy Table, mapping every GraphQL object in the schema to a
                SQLAlchemy Table. The columns of each table, (with a supported type), will me mapped
                to a GraphQL field with the same name as the column in the corresponding GraphQL
                object.
        sql_edge_descriptors: dict, str-> SQLEdgeDescriptor, mapping the names of edges in
                              the schema to namedtuple objects specifying the source and destination
                              graphql objects and which columns of the underlying tables to use
                              when traversing the edges. These  edges will be rendered as vertex
                              fields named out_ <edgeName> and in_<edgeName> in the source and
                              destination graphql objects respectively. The edge names must not
                              conflict with the GraphQL object names.
        junction_tables: dict, str -> JunctionTableEdgeDescriptor, mapping the names of junction
                         table edges to namedtuple objects specifying the source and destination
                         GraphQL objects and how to use the junction tables as many-to-many edges.
                         Junction table edges names must not conflict with other edge names or
                         the names of GraphQL objects.
        dialect: sqlalchemy.engine.interfaces.Dialect, specifying the dialect we are compiling to
                 (e.g. sqlalchemy.dialects.mssql.dialect()).
        class_to_field_type_overrides: optional dict, class name -> {field name -> field type},
                                       (string -> {string -> GraphQLType}). Used to override the
                                       type of a field in the class where it's first defined and all
                                       the class's subclasses.
    Return:
        SQLAlchemySchemaInfo containing the full information needed to compile SQL queries.
    """
    schema_graph = get_sqlalchemy_schema_graph(tables, sql_edge_descriptors, junction_tables)

    # Since there will be no inheritance in the GraphQL schema, it is simpler to omit the class.
    hidden_classes = set()
    graphql_schema = get_graphql_schema_from_schema_graph(
        schema_graph, class_to_field_type_overrides, hidden_classes)

    join_descriptors = get_restructured_edge_descriptors(sql_edge_descriptors)

    # type_equivalence_hints exists as field in SQLAlchemySchemaInfo to make testing easier for
    # the SQL backend. However, there is no inheritance in SQLAlchemy and there will be no GraphQL
    # union types in the schema, so we set the type_equivalence_hints to be an empty dict.
    type_equivalence_hints = {}

    return make_sqlalchemy_schema_info(
        graphql_schema, tables, join_descriptors, type_equivalence_hints, dialect)
