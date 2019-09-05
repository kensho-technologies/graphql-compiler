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
from .schema.schema_info import make_sqlalchemy_schema_info
from .schema_generation.graphql_schema import get_graphql_schema_from_schema_graph
from .schema_generation.orientdb.schema_graph_builder import get_orientdb_schema_graph
from .schema_generation.sqlalchemy.edge_descriptors import get_join_descriptors
from .schema_generation.sqlalchemy.schema_graph_builder import get_sqlalchemy_schema_graph


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
    vertex_name_to_table, direct_edges, junction_table_edges, dialect,
    class_to_field_type_overrides=None
):
    """Return a SQLAlchemyInfo from the metadata.

    Args:
        vertex_name_to_table: dict, str -> SQLAlchemy Table. This dictionary is used to generate the
                              GraphQL objects in the schema in the SQLAlchemySchemaInfo. Each
                              SQLAlchemyTable will be represented as a GraphQL object. The GraphQL
                              object names are the dictionary keys. The fields of the GraphQL
                              objects will be inferred from the columns of the underlying tables.
                              The fields will have the same name as the underlying columns and
                              columns with unsupported types, (SQL types with no matching GraphQL
                              type), will be ignored.
        direct_edges: dict, str-> DirectEdgeDescriptor. Direct edges are edges that do not
                      use a junction table, (see junction_table_edges). The traversal of a direct
                      edge gets compiled to a SQL join in graphql_to_sql(). Therefore, each
                      DirectEdgeDescriptor not only specifies the source and destination GraphQL
                      objects, but also which columns to use to use when generating a SQL join
                      between the underlying source and destination tables. The names of the edges
                      are the keys in the dictionary and the edges will be rendered as vertex fields
                      named out_<edgeName> and in_<edgeName> in the source and destination GraphQL
                      objects respectively. The direct edge names must not conflict with the GraphQL
                      object names.
        junction_table_edges: dict, str -> JunctionTableEdgeDescriptor. Junction table edges are
                              edges that use a junction table to function as many-to-many edges.
                              The traversal of a junction table edges gets compiled to two SQL joins
                              in graphql_to_sql(): one from the source table to the junction table
                              and another from the junction table to the destination table.
                              Therefore, each JunctionTableEdgeDescriptor specifies the source and
                              destination GraphQL objects and how to generate SQL joins between the
                              junction table and the underlying source and destination tables. The
                              names of the edges are the corresponding keys in the dictionary and
                              the edges will be rendered as vertex fields named out_<edgeName> and
                              in_<edgeName> the source and destination GraphQL objects. The junction
                              table edge names must not conflict with either the GraphQL object
                              names or direct edge names.
        dialect: sqlalchemy.engine.interfaces.Dialect, specifying the dialect we are compiling to
                 (e.g. sqlalchemy.dialects.mssql.dialect()).
        class_to_field_type_overrides: optional dict, class name -> {field name -> field type},
                                       (string -> {string -> GraphQLType}). Used to override the
                                       type of a field in the class where it's first defined and all
                                       the class's subclasses.
    Return:
        SQLAlchemySchemaInfo containing the full information needed to compile SQL queries.
    """
    schema_graph = get_sqlalchemy_schema_graph(
        vertex_name_to_table, direct_edges, junction_table_edges)

    # Since there will be no inheritance in the GraphQL schema, it is simpler to omit the class.
    hidden_classes = set()
    graphql_schema, _ = get_graphql_schema_from_schema_graph(
        schema_graph, class_to_field_type_overrides, hidden_classes)

    join_descriptors = get_join_descriptors(direct_edges, junction_table_edges)

    # type_equivalence_hints exists as field in SQLAlchemySchemaInfo to make testing easier for
    # the SQL backend. However, there is no inheritance in SQLAlchemy and there will be no GraphQL
    # union types in the schema, so we set the type_equivalence_hints to be an empty dict.
    type_equivalence_hints = {}

    return make_sqlalchemy_schema_info(
        graphql_schema, type_equivalence_hints, dialect, vertex_name_to_table, join_descriptors)
