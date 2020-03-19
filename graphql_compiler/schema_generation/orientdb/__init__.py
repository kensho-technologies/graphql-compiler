# Copyright 2019-present Kensho Technologies, LLC.
from ..graphql_schema import get_graphql_schema_from_schema_graph
from .schema_graph_builder import get_orientdb_schema_graph


def get_graphql_schema_from_orientdb_schema_data(
    schema_data, class_to_field_type_overrides=None, hidden_classes=None
):
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
    return get_graphql_schema_from_schema_graph(
        schema_graph,
        class_to_field_type_overrides=class_to_field_type_overrides,
        hidden_classes=hidden_classes,
    )
