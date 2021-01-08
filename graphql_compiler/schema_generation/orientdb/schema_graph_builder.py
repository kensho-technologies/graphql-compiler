# Copyright 2019-present Kensho Technologies, LLC.
from itertools import chain
from typing import Dict, Set

from funcy.py3 import lsplit
from graphql.type import GraphQLList, GraphQLObjectType
import six

from ..exceptions import IllegalSchemaStateError
from ..schema_graph import (
    EdgeType,
    IndexDefinition,
    InheritanceStructure,
    NonGraphElement,
    PropertyDescriptor,
    SchemaGraph,
    VertexType,
    link_schema_elements,
)
from .schema_properties import (
    COLLECTION_PROPERTY_TYPES,
    EDGE_DESTINATION_PROPERTY_NAME,
    EDGE_END_NAMES,
    EDGE_SOURCE_PROPERTY_NAME,
    ORDERED_INDEX_TYPES,
    ORIENTDB_BASE_EDGE_CLASS_NAME,
    ORIENTDB_BASE_VERTEX_CLASS_NAME,
    PROPERTY_TYPE_LINK_ID,
    UNIQUE_INDEX_TYPES,
    parse_default_property_value,
    try_get_graphql_scalar_type,
)


def get_orientdb_schema_graph(schema_data, index_data):
    """Create a new SchemaGraph from the OrientDB schema data.

    Args:
        schema_data: list of dicts describing the classes in the OrientDB schema. The following
                     format is the way the data is structured in OrientDB 2. See
                     the README.md file for an example of how to query this data.
                     Each dict has the following string fields:
                        - name: string, the name of the class.
                        - superClasses (optional): list of strings, the name of the class's
                                                   superclasses.
                        - superClass (optional): string, the name of the class's superclass. May
                                                 be used instead of superClasses if there is
                                                 only one superClass. Used for backwards
                                                 compatibility with OrientDB.
                        - customFields (optional): dict, string -> string, data defined on the
                                                   class instead of instances of the class.
                        - abstract: bool, true if the class is abstract.
                        - properties: list of dicts, describing the class's properties.
                                      Each property dictionary has the following string fields:
                                         - name: string, the name of the property.
                                         - type: int, builtin OrientDB type ID of the field.
                                                 See schema_properties.py for the mapping.
                                         - linkedType (optional): int, if the property is a
                                                                  collection of builtin
                                                                  OrientDB objects, then it
                                                                  indicates their type ID.
                                         - linkedClass (optional): string, if the property is a
                                                                   collection of class
                                                                   instances, then it indicates
                                                                   the name of the class. If
                                                                   class is an edge class, and
                                                                   the field name is either
                                                                   'in' or 'out', then it
                                                                   describes the name of an
                                                                   endpoint of the edge.
                                         - defaultValue: string, the textual representation
                                                         of the default value for the
                                                         property, as returned by OrientDB's
                                                         schema introspection code, e.g.,
                                                         '{}' for the embedded set type. Note
                                                         that if the property is a collection
                                                         type, it must have a default value.
        index_data: list of dicts describing the schema indexes. Each dict must have
                    the following string fields:
                        - name: string, the name of the index.
                        - type: string, specifying the type of the index. It must be one of:
                                        'UNIQUE', 'NOTUNIQUE', 'UNIQUE_HASH_INDEX', or
                                        'NOTUNIQUE_HASH_INDEX'.
                        - indexDefinition: dict, defining the index. It must contain one of two
                                           string keys:
                                           - field: string, the name of the field which the index
                                                    encompasses.
                                           - indexDefinitions: list of dicts. Each one of these
                                                               dicts must contain a string field
                                                               key. These specify the
                                                               set of fields which the index
                                                               encompasses.
                        - className: string, the name of the class on which the index is defined.
                        - nullValuesIgnored: bool, indicating if the index ignores null values.

    Returns:
        fully-constructed SchemaGraph object
    """
    class_name_to_definition = {
        class_definition["name"]: class_definition for class_definition in schema_data
    }

    direct_superclass_sets = {
        class_name: get_superclasses_from_class_definition(class_definition)
        for class_name, class_definition in six.iteritems(class_name_to_definition)
    }

    inheritance_structure = InheritanceStructure(direct_superclass_sets)

    non_graph_elements = _get_non_graph_elements(class_name_to_definition, inheritance_structure)
    inner_collection_objs = _get_graphql_representation_of_non_graph_elements(
        non_graph_elements, inheritance_structure
    )

    elements = non_graph_elements
    elements.update(
        _get_edge_elements(class_name_to_definition, inheritance_structure, inner_collection_objs)
    )
    elements.update(
        _get_vertex_elements(class_name_to_definition, inheritance_structure, inner_collection_objs)
    )

    # Initialize the connections that show which schema classes can be connected to
    # which other schema classes, then freeze all schema elements.
    link_schema_elements(elements, inheritance_structure)
    for element in six.itervalues(elements):
        element.freeze()

    all_indexes = _get_indexes(index_data, elements)
    return SchemaGraph(elements, inheritance_structure, all_indexes)


def get_superclasses_from_class_definition(class_definition):
    """Extract a list of all superclass names from a class definition dict."""
    # New-style superclasses definition, supporting multiple-inheritance.
    superclasses = class_definition.get("superClasses", None)

    if superclasses:
        return list(superclasses)

    # Old-style superclass definition, single inheritance only.
    superclass = class_definition.get("superClass", None)
    if superclass:
        return [superclass]

    # No superclasses are present.
    return []


def _get_non_graph_elements(class_name_to_definition, inheritance_structure):
    """Return a dict mapping class name to NonGraphElement."""
    non_graph_elements = dict()
    _, _, non_graph_class_names = _get_vertex_edge_and_non_graph_class_names(inheritance_structure)

    for class_name in non_graph_class_names:
        class_definition = class_name_to_definition[class_name]
        class_fields = _get_class_fields(class_definition)
        abstract = _is_abstract(class_definition)

        inherited_property_definitions = _get_inherited_property_definitions(
            inheritance_structure.superclass_sets[class_name], class_name_to_definition
        )
        (
            link_property_definitions,
            non_link_property_definitions,
        ) = _get_link_and_non_link_properties(inherited_property_definitions)

        if len(link_property_definitions) > 0:
            raise AssertionError(
                "There are links {} defined on non-edge class {}".format(
                    link_property_definitions, class_name
                )
            )

        property_name_to_descriptor = _get_element_properties(
            class_name, non_link_property_definitions, non_graph_class_names, []
        )

        non_graph_elements[class_name] = NonGraphElement(
            class_name, abstract, property_name_to_descriptor, class_fields
        )
    return non_graph_elements


def _get_edge_elements(class_name_to_definition, inheritance_structure, inner_collection_objs):
    """Return a dict mapping class name to EdgeType."""
    edge_elements = dict()

    (
        vertex_class_names,
        edge_class_names,
        non_graph_class_names,
    ) = _get_vertex_edge_and_non_graph_class_names(inheritance_structure)

    for class_name in edge_class_names:
        class_definition = class_name_to_definition[class_name]
        class_fields = _get_class_fields(class_definition)
        abstract = _is_abstract(class_definition)

        inherited_property_definitions = _get_inherited_property_definitions(
            inheritance_structure.superclass_sets[class_name], class_name_to_definition
        )
        (
            link_property_definitions,
            non_link_property_definitions,
        ) = _get_link_and_non_link_properties(inherited_property_definitions)

        for definition in link_property_definitions:
            _validate_link_definition(
                class_name_to_definition, definition, vertex_class_names, inheritance_structure
            )

        links = _get_end_direction_to_superclasses(link_property_definitions)

        maybe_base_in_connection, maybe_base_out_connection = _try_get_base_connections(
            class_name, inheritance_structure, links, abstract
        )

        property_name_to_descriptor = _get_element_properties(
            class_name, non_link_property_definitions, non_graph_class_names, inner_collection_objs
        )

        edge_elements[class_name] = EdgeType(
            class_name,
            abstract,
            property_name_to_descriptor,
            class_fields,
            maybe_base_in_connection,
            maybe_base_out_connection,
        )
    return edge_elements


def _get_vertex_elements(class_name_to_definition, inheritance_structure, inner_collection_objs):
    """Return a dict mapping class name to VertexType."""
    vertex_elements = dict()

    vertex_class_names, _, non_graph_class_names = _get_vertex_edge_and_non_graph_class_names(
        inheritance_structure
    )

    for class_name in vertex_class_names:
        class_definition = class_name_to_definition[class_name]
        class_fields = _get_class_fields(class_definition)
        abstract = _is_abstract(class_definition)

        inherited_property_definitions = _get_inherited_property_definitions(
            inheritance_structure.superclass_sets[class_name], class_name_to_definition
        )
        (
            link_property_definitions,
            non_link_property_definitions,
        ) = _get_link_and_non_link_properties(inherited_property_definitions)

        if len(link_property_definitions) > 0:
            raise AssertionError(
                "There are links {} defined on non-edge class {}".format(
                    link_property_definitions, class_name
                )
            )

        property_name_to_descriptor = _get_element_properties(
            class_name, non_link_property_definitions, non_graph_class_names, inner_collection_objs
        )

        vertex_elements[class_name] = VertexType(
            class_name, abstract, property_name_to_descriptor, class_fields
        )
    return vertex_elements


def _get_vertex_edge_and_non_graph_class_names(inheritance_structure):
    """Return the vertex, edge and non-graph class names."""
    vertex_class_names = set()
    edge_class_names = set()
    non_graph_class_names = set()

    for class_name, superclass_set in six.iteritems(inheritance_structure.superclass_sets):
        is_vertex = ORIENTDB_BASE_VERTEX_CLASS_NAME in superclass_set
        is_edge = ORIENTDB_BASE_EDGE_CLASS_NAME in superclass_set

        if is_vertex and is_edge:
            raise AssertionError(
                "Class {} appears to be both a vertex and an edge class: "
                "{}".format(class_name, superclass_set)
            )
        elif is_vertex:
            vertex_class_names.add(class_name)
        elif is_edge:
            edge_class_names.add(class_name)
        else:
            non_graph_class_names.add(class_name)

    return vertex_class_names, edge_class_names, non_graph_class_names


def _get_class_fields(class_definition):
    """Return the class fields."""
    class_fields = class_definition.get("customFields")
    if class_fields is None:
        # OrientDB likes to make empty collections be None instead.
        # We convert this field back to an empty dict, for our general happiness.
        class_fields = dict()
    return class_fields


def _is_abstract(class_definition):
    """Return if the class is abstract. We pretend the V and E OrientDB classes are abstract."""
    orientdb_base_classes = frozenset(
        {
            ORIENTDB_BASE_VERTEX_CLASS_NAME,
            ORIENTDB_BASE_EDGE_CLASS_NAME,
        }
    )
    return class_definition["name"] in orientdb_base_classes or class_definition["abstract"]


def _get_inherited_property_definitions(superclass_set, class_name_to_definition):
    """Return a class's inherited OrientDB property definitions."""
    return list(
        chain.from_iterable(
            class_name_to_definition[inherited_class_name]["properties"]
            for inherited_class_name in superclass_set
        )
    )


def _get_link_and_non_link_properties(property_definitions):
    """Return a class's link and non link OrientDB property definitions."""
    return lsplit(lambda x: x["name"] in EDGE_END_NAMES, property_definitions)


def _get_element_properties(
    class_name, non_link_property_definitions, non_graph_class_names, inner_collection_objs
):
    """Return the SchemaElement's properties from the OrientDB non-link property definitions."""
    property_name_to_descriptor = {}
    for property_definition in non_link_property_definitions:
        property_name = property_definition["name"]

        if property_name in property_name_to_descriptor:
            raise AssertionError(
                'The property "{}" on class "{}" is defined '
                "more than once, this is not allowed!".format(property_name, class_name)
            )

        maybe_graphql_type = _try_get_graphql_type(
            class_name, property_definition, non_graph_class_names, inner_collection_objs
        )

        if maybe_graphql_type is not None:
            default_value = _get_default_value(class_name, property_definition)
            property_descriptor = PropertyDescriptor(maybe_graphql_type, default_value)
            property_name_to_descriptor[property_name] = property_descriptor
    return property_name_to_descriptor


def _try_get_graphql_type(
    class_name, property_definition, non_graph_class_names, inner_collection_objs
):
    """Return the GraphQLType corresponding to the non-link property definition."""
    name = property_definition["name"]
    type_id = property_definition["type"]
    linked_class = property_definition.get("linkedClass", None)
    linked_type = property_definition.get("linkedType", None)

    maybe_graphql_type = None
    if type_id == PROPERTY_TYPE_LINK_ID:
        raise AssertionError(
            "Found a improperly named property of type Link: "
            '{} {}. Links must be named either "in" or "out"'.format(name, class_name)
        )
    elif type_id in COLLECTION_PROPERTY_TYPES:
        if linked_class is not None and linked_type is not None:
            raise AssertionError(
                'Property "{}" unexpectedly has both a linked class and '
                "a linked type: {}".format(name, property_definition)
            )
        elif linked_type is not None and linked_class is None:
            # No linked class, must be a linked native OrientDB type.
            maybe_inner_type = try_get_graphql_scalar_type(name + " inner type", linked_type)
            if maybe_inner_type is not None:
                maybe_graphql_type = GraphQLList(maybe_inner_type)
        elif linked_class is not None and linked_type is None:
            # No linked type, must be a linked non-graph user-defined type.
            if class_name in non_graph_class_names:
                raise AssertionError(
                    "Class {} is a non-graph class that contains a "
                    "collection property {}. Only graph classes are allowed "
                    "to have collections as properties.".format(class_name, property_definition)
                )
            if linked_class not in inner_collection_objs:
                raise AssertionError(
                    'Property "{}" is declared as the inner type of '
                    "an embedded collection, but the inner class {} is not a "
                    "non-graph class with no superclasses other than "
                    "itself.".format(name, linked_class)
                )

            maybe_graphql_type = GraphQLList(inner_collection_objs[linked_class])
        else:
            raise AssertionError(
                'Property "{}" is an embedded collection but has '
                "neither a linked class nor a linked type: "
                "{}".format(name, property_definition)
            )
    else:
        maybe_graphql_type = try_get_graphql_scalar_type(name, type_id)

    return maybe_graphql_type


def _get_default_value(class_name, property_definition):
    """Return the default value of the OrientDB property."""
    default_value = None
    default_value_string = property_definition.get("defaultValue", None)
    if default_value_string is not None:
        default_value = parse_default_property_value(
            property_definition["name"], property_definition["type"], default_value_string
        )

    # We don't want properties of collection type having "null" values, since that may cause
    # unexpected errors during GraphQL query execution and other operations.
    if property_definition["type"] in COLLECTION_PROPERTY_TYPES:
        if default_value is None:
            raise IllegalSchemaStateError(
                'Class "{}" has a property "{}" of collection type with '
                "no default value.".format(class_name, property_definition)
            )

    return default_value


def _validate_link_definition(
    class_name_to_definition, property_definition, vertex_class_names, inheritance_structure
):
    """Validate that property named either 'in' or 'out' is properly defined as a link."""
    name = property_definition["name"]
    type_id = property_definition["type"]
    linked_class = property_definition["linkedClass"]
    if type_id != PROPERTY_TYPE_LINK_ID:
        raise AssertionError(
            'Expected property named "{}" to be of type Link: {}'.format(name, property_definition)
        )
    if linked_class is None:
        raise AssertionError(
            'Property "{}" is declared with type Link but has no '
            "linked class: {}".format(name, property_definition)
        )
    if linked_class not in vertex_class_names:
        is_linked_class_abstract = class_name_to_definition[linked_class]["abstract"]
        all_subclasses_are_vertices = True
        for subclass in inheritance_structure.subclass_sets[linked_class]:
            if subclass != linked_class and subclass not in vertex_class_names:
                all_subclasses_are_vertices = False
                break
        if not (is_linked_class_abstract and all_subclasses_are_vertices):
            raise AssertionError(
                'Property "{}" is declared as a Link to class {}, but '
                "that class is neither a vertex nor is it an "
                "abstract class whose subclasses are all vertices!".format(name, linked_class)
            )


def _get_end_direction_to_superclasses(link_property_definitions):
    """Return the set of superclasses that classes at each edge end must inherit from."""
    links: Dict[str, Set[str]] = {
        EDGE_SOURCE_PROPERTY_NAME: set(),
        EDGE_DESTINATION_PROPERTY_NAME: set(),
    }
    for property_definition in link_property_definitions:
        links[property_definition["name"]].add(property_definition["linkedClass"])
    return links


def _try_get_base_connections(class_name, inheritance_structure, links, abstract):
    """Return a tuple with the EdgeType's base connections. Each tuple element may be None."""
    base_connections = {}

    for end_direction, linked_classes in six.iteritems(links):
        # The linked_classes set is the complete set of superclasses that a class must
        # inherit from in order to be allowed in the edge end specified by end_direction.
        # The base connection of an edge's end is the superclass of all classes allowed in the
        # edge's end. Therefore, the base connection of the end specified by end_direction,
        # if it exists, must be the class in linked_classes that is a subclass of all other
        # classes in linked_classes.
        for linked_class in linked_classes:
            superclass_set = inheritance_structure.superclass_sets[linked_class]
            if set(linked_classes).issubset(superclass_set):
                base_connections[end_direction] = linked_class

        if end_direction not in base_connections and not abstract:
            raise AssertionError(
                'For edge end direction "{}" of non-abstract edge class '
                '"{}", no such subclass-of-all-elements exists.'.format(end_direction, class_name)
            )
    return (
        base_connections.get(EDGE_SOURCE_PROPERTY_NAME, None),
        base_connections.get(EDGE_DESTINATION_PROPERTY_NAME, None),
    )


def _get_graphql_representation_of_non_graph_elements(non_graph_elements, inheritance_structure):
    """Return a dict mapping name to GraphQL Object for non graph elements without superclasses."""
    graphql_reps = {}
    for element_name, element in six.iteritems(non_graph_elements):
        if inheritance_structure.superclass_sets[element_name] == {element_name}:
            fields = {name: property_obj.type for name, property_obj in element.properties.items()}
            graphql_reps[element_name] = GraphQLObjectType(element_name, fields, [])
    return graphql_reps


def _get_indexes(index_data, elements):
    """Return a set of IndexDefinitions describing the indexes defined in the OrientDB database."""
    all_indexes = set()

    # Get indexes from OrientDB.
    all_class_names = set(elements.keys())

    for index in index_data:
        index_name = index["name"]
        index_type = index["type"]
        index_unique = index_type in UNIQUE_INDEX_TYPES
        index_ordered = index_type in ORDERED_INDEX_TYPES
        index_definition = index["indexDefinition"]
        index_base_classname = index_definition["className"]
        index_ignore_nulls = index_definition["nullValuesIgnored"]

        # Exclude indexes on OrientDB metadata classes (e.g. OUser).
        if index_base_classname not in all_class_names:
            continue

        # Index fields can be specified in one of two ways:
        #   - directly on the "indexDefinition" dict, if only a single field is covered;
        #   - within a nested "indexDefinitions" dict inside
        #     the top-level "indexDefinition" dict, if multiple fields are covered.
        single_field = index_definition.get("field", None)
        if single_field is not None:
            index_fields = frozenset((single_field,))
        else:
            index_fields = frozenset(
                subdefinition["field"] for subdefinition in index_definition["indexDefinitions"]
            )

        if not index_fields:
            raise AssertionError("Unable to load index fields for index: {}".format(index))

        if index_ignore_nulls and len(index_fields) != 1:
            raise AssertionError(
                "Index {} ignores nulls, but covers more than one field. "
                "We don't know how OrientDB handles such indexes, so they are not allowed. "
                "{}".format(index_name, index)
            )

        definition = IndexDefinition(
            name=index_name,
            base_classname=index_base_classname,
            fields=index_fields,
            unique=index_unique,
            ignore_nulls=index_ignore_nulls,
            ordered=index_ordered,
        )
        all_indexes.add(definition)

    return frozenset(all_indexes)
