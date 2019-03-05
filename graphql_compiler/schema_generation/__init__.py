# Copyright 2019-present Kensho Technologies, LLC.
# Match query used to generate OrientDB records that are themselves used to generate GraphQL schema.
from .utils import toposort_classes
from .schema_graph import SchemaGraph
from .schema_properties import ORIENTDB_BASE_VERTEX_CLASS_NAME
from .graphql_schema import get_graphql_schema_from_schema_graph


ORIENTDB_SCHEMA_RECORDS_QUERY = (
    'SELECT FROM (SELECT expand(classes) FROM metadata:schema) '
    'WHERE name NOT IN [\'ORole\', \'ORestricted\', \'OTriggered\', '
    '\'ORIDs\', \'OUser\', \'OIdentity\', \'OSchedule\', \'OFunction\']'
)


def get_graphql_schema_from_orientdb_schema_data(schema_data, class_to_field_type_overrides=None,
                                             hidden_classes=None):
    """Construct a GraphQL schema from an OrientDB schema.

    Args:
        schema_data: list of dicts describing the classes in the OrientDB schema.
                     Each dict has the following string fields.
                        - name: string, the name of the class.
                        - superClasses (optional): list of strings, the name of the class's
                                                   superclasses.
                        - superClass (optional): string, the name of the class's superclass. May be
                                                 used instead of superClasses if there is only one
                                                 superClass. Used for backwards compatibility.
                        - abstract: bool, true if the class is abstract.
                        - properties: list of dicts, describing the class's fields.
                            Each property dictionary has the following string fields.
                                - name: string, the name of the field.
                                - type_id: int, builtin OrientDB type ID of the field.
                                - linked_type (optional): int, if the field is a collection of
                                                          builtin OrientDB objects, then
                                                          it indicates their type ID.
                                - linked_class (optional): string, if the field is a collection of
                                                           class instance, then it indicates the
                                                           name of the class. If class is an edge
                                                           class, and the field name is either 'in'
                                                           or 'out' then it describes the name of
                                                           an endpoint of the edge.
        class_to_field_type_overrides: optional dict, class name -> {field name -> field type},
                                       (string -> {string -> GraphQLType}. Used to override the
                                       type of a field in the class where it's first defined and all
                                       the class's subclasses.
        hidden_classes: optional set of strings, classes to not include in the GraphQL schema.

    Returns:
        tuple of (GraphQL schema object, GraphQL type equivalence hints dict).
        The tuple is of type (GraphQLSchema, GraphQLUnionType).
    """
    if class_to_field_type_overrides is None:
        class_to_field_type_overrides = dict()
    if hidden_classes is None:
        hidden_classes = set()

    schema_query_data = toposort_classes([x.oRecordData for x in schema_data])
    schema_graph = SchemaGraph(schema_query_data)

    # If the OrientDB base vertex class no properties defined, hide it since
    # classes with no properties are not representable in the GraphQL schema.
    base_vertex = schema_graph.get_element_by_class_name(ORIENTDB_BASE_VERTEX_CLASS_NAME)
    if len(base_vertex.properties) == 0:
        hidden_classes.add(ORIENTDB_BASE_VERTEX_CLASS_NAME)

    return get_graphql_schema_from_schema_graph(schema_graph, class_to_field_type_overrides,
                                                hidden_classes)
