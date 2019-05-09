# Copyright 2019-present Kensho Technologies, LLC.
from itertools import chain

from funcy.py3 import lsplit
from graphql.type import GraphQLList, GraphQLObjectType
import six

from ..schema_graph import (
    VertexType, EdgeType, NonGraphElement, SchemaGraph, get_subclass_sets_from_inheritance_sets
)

from ..exceptions import IllegalSchemaStateError
from .schema_properties import (
    COLLECTION_PROPERTY_TYPES, ORIENTDB_BASE_EDGE_CLASS_NAME,
    ORIENTDB_BASE_VERTEX_CLASS_NAME, PROPERTY_TYPE_LINK_ID, PropertyDescriptor,
    get_graphql_scalar_type_or_raise, parse_default_property_value,
    EDGE_DESTINATION_PROPERTY_NAME, EDGE_END_NAMES, EDGE_SOURCE_PROPERTY_NAME
)
from .utils import toposort_classes
from enum import Enum

class OrientDBType(Enum):
    Vertex = 1
    Edge = 2
    NonGraph = 3


def get_superclasses_from_class_definition(class_definition):
    """Extract a list of all superclass names from a class definition dict."""
    # New-style superclasses definition, supporting multiple-inheritance.
    superclasses = class_definition.get('superClasses', None)

    if superclasses:
        return list(superclasses)

    # Old-style superclass definition, single inheritance only.
    superclass = class_definition.get('superClass', None)
    if superclass:
        return [superclass]

    # No superclasses are present.
    return []


def get_orientdb_schema_graph(outer_schema_data):
    """Create a new SchemaGraph from the OrientDB schema.

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

    Returns:
        fully-constructed SchemaGraph object
    """
    class SchemaGraphBuilder(object):
        def __init__(self, schema_data):
            toposorted_schema_data = toposort_classes(schema_data)
            self._elements = dict()

            self._inheritance_sets = _get_inheritance_sets_from_schema_data(toposorted_schema_data)
            self._subclass_sets = get_subclass_sets_from_inheritance_sets(self._inheritance_sets)

            class_name_to_definition = {
                class_definition['name']: class_definition
                for class_definition in toposorted_schema_data
            }

            # Initialize the _vertex_class_names, _edge_class_names, and _non_graph_class_names sets.
            self._vertex_class_names, self._edge_class_names, self._non_graph_class_names = (
                _split_classes_by_kind(self._inheritance_sets, class_name_to_definition)
            )

            self._set_up_non_graph_elements(class_name_to_definition)
            self._set_up_edge_elements(class_name_to_definition)
            self._set_up_vertex_elements(class_name_to_definition)

            # Initialize the connections that show which schema classes can be connected to
            # which other schema classes, then freeze all schema elements.
            self._link_vertex_and_edge_types()
            for element in six.itervalues(self._elements):
                element.freeze()

        def build(self):
            return SchemaGraph(self._elements, self._inheritance_sets)

        def _set_up_non_graph_elements(self, class_name_to_definition):
            """Load all NonGraphElements. Used as part of __init__."""
            for class_name in self._non_graph_class_names:
                class_definition = class_name_to_definition[class_name]
                class_fields = _get_class_fields(class_definition)
                abstract = _is_abstract(class_definition)

                inherited_property_definitions = _get_inherited_property_definitions(
                    self._inheritance_sets[class_name], class_name_to_definition)
                link_property_definitions, non_link_property_definitions = (
                    _get_link_and_non_link_properties(inherited_property_definitions))

                if len(link_property_definitions) > 0:
                    raise AssertionError(u'There are links {} defined on non-edge class {}'
                                         .format(link_property_definitions, class_name))

                property_name_to_descriptor = (self._get_element_properties(
                    class_name, non_link_property_definitions))

                self._elements[class_name] = NonGraphElement(
                    class_name, abstract, property_name_to_descriptor, class_fields)

        def _set_up_edge_elements(self, class_name_to_definition):
            """Load all EdgeTypes. Used as part of __init__."""
            for class_name in self._edge_class_names:
                class_definition = class_name_to_definition[class_name]
                class_fields = _get_class_fields(class_definition)
                abstract = _is_abstract(class_definition)

                inherited_property_definitions = _get_inherited_property_definitions(
                    self._inheritance_sets[class_name], class_name_to_definition)
                link_property_definitions, non_link_property_definitions = (
                    _get_link_and_non_link_properties(inherited_property_definitions))

                [_validate_link_definition(class_name_to_definition, definition,
                                           self._vertex_class_names, self._subclass_sets)
                 for definition in link_property_definitions]

                links = _get_end_direction_to_superclasses(link_property_definitions)

                maybe_base_in_connection, maybe_base_out_connection = _try_get_base_connections(
                    class_name, self._inheritance_sets, links, abstract)

                property_name_to_descriptor = self._get_element_properties(
                    class_name, non_link_property_definitions)

                self._elements[class_name] = EdgeType(
                    class_name, abstract, property_name_to_descriptor, class_fields,
                    maybe_base_in_connection, maybe_base_out_connection)

        def _set_up_vertex_elements(self, class_name_to_definition):
            """Load all VertexTypes. Used as part of __init__."""
            for class_name in self._vertex_class_names:
                class_definition = class_name_to_definition[class_name]
                class_fields = _get_class_fields(class_definition)
                abstract = _is_abstract(class_definition)

                inherited_property_definitions = _get_inherited_property_definitions(
                    self._inheritance_sets[class_name], class_name_to_definition)
                link_property_definitions, non_link_property_definitions = (
                    _get_link_and_non_link_properties(inherited_property_definitions))

                if len(link_property_definitions) > 0:
                    raise AssertionError(u'There are links {} defined on non-edge class {}'
                                         .format(link_property_definitions, class_name))

                property_name_to_descriptor = self._get_element_properties(
                    class_name, non_link_property_definitions)

                self._elements[class_name] = VertexType(
                    class_name, abstract, property_name_to_descriptor, class_fields)

        def _get_element_properties(self, class_name, non_link_property_definitions):
            """Return the SchemaElement's properties from the OrientDB non-link property definitions."""
            property_name_to_descriptor = {}
            for property_definition in non_link_property_definitions:
                property_name = property_definition['name']

                if property_name in property_name_to_descriptor:
                    raise AssertionError(u'The property "{}" on class "{}" is defined '
                                         u'more than once, this is not allowed!'
                                         .format(property_name, class_name))

                graphql_type = _get_graphql_type(class_name, property_definition,
                                                 self._non_graph_class_names)
                default_value = _get_default_value(class_name, property_definition)
                property_descriptor = PropertyDescriptor(graphql_type, default_value)
                property_name_to_descriptor[property_name] = property_descriptor
            return property_name_to_descriptor

        def _link_vertex_and_edge_types(self):
            """For each edge, link it to the vertex types it connects to each other."""
            for edge_class_name in self._edge_class_names:
                edge_element = self._elements[edge_class_name]

                from_class_name = edge_element.base_in_connection
                to_class_name = edge_element.base_out_connection

                if not from_class_name or not to_class_name:
                    continue

                edge_schema_element = self._elements[edge_class_name]

                # Link from_class_name with edge_class_name
                for from_class in self._subclass_sets[from_class_name]:
                    from_schema_element = self._elements[from_class]
                    from_schema_element.out_connections.add(edge_class_name)
                    edge_schema_element.in_connections.add(from_class)

                # Link edge_class_name with to_class_name
                for to_class in self._subclass_sets[to_class_name]:
                    to_schema_element = self._elements[to_class]
                    edge_schema_element.out_connections.add(to_class)
                    to_schema_element.in_connections.add(edge_class_name)

    def _get_inherited_property_definitions(superclass_set, class_name_to_definition):
        """Return a class's inherited OrientDB property definitions."""
        return list(chain.from_iterable(
            class_name_to_definition[inherited_class_name]['properties']
            for inherited_class_name in superclass_set
        ))


    return SchemaGraphBuilder(outer_schema_data).build()


def _split_classes_by_kind(inheritance_sets, class_name_to_definition):
    """Assign each class to the vertex, edge or non-graph type sets based on its kind."""
    vertex_class_names = set()
    edge_class_names = set()
    non_graph_class_names = set()
    for class_name in class_name_to_definition:
        inheritance_set = inheritance_sets[class_name]

        is_vertex = ORIENTDB_BASE_VERTEX_CLASS_NAME in inheritance_set
        is_edge = ORIENTDB_BASE_EDGE_CLASS_NAME in inheritance_set

        if is_vertex and is_edge:
            raise AssertionError(u'Class {} appears to be both a vertex and an edge class: '
                                 u'{}'.format(class_name, inheritance_set))
        elif is_vertex:
            vertex_class_names.add(class_name)
        elif is_edge:
            edge_class_names.add(class_name)
        else:
            non_graph_class_names.add(class_name)
    # Freeze the classname sets so they cannot be modified again.
    return (frozenset(names)
            for names in (vertex_class_names, edge_class_names, non_graph_class_names))


def _get_link_and_non_link_properties(property_definitions):
    """Return a class's link and non link OrientDB property definitions."""
    return lsplit(lambda x: x['name'] in EDGE_END_NAMES, property_definitions)


def _is_abstract(class_definition):
    """Return if the class is abstract. We pretend the V and E OrientDB classes are abstract."""
    orientdb_base_classes = frozenset({
        ORIENTDB_BASE_VERTEX_CLASS_NAME,
        ORIENTDB_BASE_EDGE_CLASS_NAME,
    })
    return class_definition['name'] in orientdb_base_classes or class_definition['abstract']


def _get_class_fields(class_definition):
    """Return the class fields."""
    class_fields = class_definition.get('customFields')
    if class_fields is None:
        # OrientDB likes to make empty collections be None instead.
        # We convert this field back to an empty dict, for our general sanity.
        class_fields = dict()
    return class_fields


def _get_default_value(class_name, property_definition):
    """Return the default value of the OrientDB property."""
    default_value = None
    default_value_string = property_definition.get('defaultValue', None)
    if default_value_string is not None:
        default_value = parse_default_property_value(
            property_definition['name'], property_definition['type'], default_value_string)

    # We don't want properties of collection type having "null" values, since that may cause
    # unexpected errors during GraphQL query execution and other operations.
    if property_definition['type'] in COLLECTION_PROPERTY_TYPES:
        if default_value is None:
            raise IllegalSchemaStateError(u'Class "{}" has a property "{}" of collection type with '
                                          u'no default value.'
                                          .format(class_name, property_definition))

    return default_value


def _get_inheritance_sets_from_schema_data(schema_data):
    """Load all inheritance data from the OrientDB schema. Used as part of __init__."""
    # For each class name, construct its inheritance set:
    # itself + the set of class names from which it inherits.
    inheritance_sets = dict()
    for class_definition in schema_data:
        class_name = class_definition['name']
        immediate_superclass_names = get_superclasses_from_class_definition(
            class_definition)

        inheritance_set = set(immediate_superclass_names)
        inheritance_set.add(class_name)

        # Since the input data must be in topological order, the superclasses of
        # the current class should have already been processed.
        # A KeyError on the following line would mean that the input
        # was not topologically sorted.
        inheritance_set.update(chain.from_iterable(
            inheritance_sets[superclass_name]
            for superclass_name in immediate_superclass_names
        ))

        # Freeze the inheritance set so it can't ever be modified again.
        inheritance_sets[class_name] = frozenset(inheritance_set)
    return inheritance_sets


def _try_get_base_connections(class_name, inheritance_sets, links, abstract):
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
            inheritance_set = inheritance_sets[linked_class]
            if set(linked_classes).issubset(inheritance_set):
                base_connections[end_direction] = linked_class

        if end_direction not in base_connections and not abstract:
            raise AssertionError(u'For edge end direction "{}" of non-abstract edge class '
                                 u'"{}", no such subclass-of-all-elements exists.'
                                 .format(end_direction, class_name))
    return (
        base_connections.get(EDGE_SOURCE_PROPERTY_NAME, None),
        base_connections.get(EDGE_DESTINATION_PROPERTY_NAME, None),
    )


def _get_end_direction_to_superclasses(link_property_definitions):
    links = {
        EDGE_SOURCE_PROPERTY_NAME: set(),
        EDGE_DESTINATION_PROPERTY_NAME: set(),
    }
    for property_definition in link_property_definitions:
        links[property_definition['name']].add(property_definition['linkedClass'])
    return links


def _validate_link_definition(class_name_to_definition, property_definition,
                              vertex_class_names, subclass_sets):
    """Validate that property named either 'in' or 'out' is properly defined as a link."""
    name = property_definition['name']
    type_id = property_definition['type']
    linked_class = property_definition['linkedClass']
    if type_id != PROPERTY_TYPE_LINK_ID:
        raise AssertionError(u'Expected property named "{}" to be of type Link: {}'
                             .format(name, property_definition))
    if linked_class is None:
        raise AssertionError(u'Property "{}" is declared with type Link but has no '
                             u'linked class: {}'.format(name, property_definition))
    if linked_class not in vertex_class_names:
        is_linked_class_abstract = class_name_to_definition[linked_class]['abstract']
        all_subclasses_are_vertices = True
        for subclass in subclass_sets[linked_class]:
            if subclass != linked_class and subclass not in vertex_class_names:
                all_subclasses_are_vertices = False
                break
        if not (is_linked_class_abstract and all_subclasses_are_vertices):
            raise AssertionError(u'Property "{}" is declared as a Link to class {}, but '
                                 u'that class is neither a vertex nor is it an '
                                 u'abstract class whose subclasses are all vertices!'
                                 .format(name, linked_class))

def _get_graphql_type(class_name, property_definition, non_graph_class_names):
    """Return the GraphQLType corresponding to the non-link property definition."""
    name = property_definition['name']
    type_id = property_definition['type']
    linked_class = property_definition.get('linkedClass', None)
    linked_type = property_definition.get('linkedType', None)

    graphql_type = None
    if type_id == PROPERTY_TYPE_LINK_ID:
        raise AssertionError(u'Found a improperly named property of type Link: '
                             u'{} {}. Links must be named either "in" or "out"'
                             .format(name, class_name))
    elif type_id in COLLECTION_PROPERTY_TYPES:
        if linked_class is not None and linked_type is not None:
            raise AssertionError(u'Property "{}" unexpectedly has both a linked class and '
                                 u'a linked type: {}'.format(name, property_definition))
        elif linked_type is not None and linked_class is None:
            # No linked class, must be a linked native OrientDB type.
            inner_type = get_graphql_scalar_type_or_raise(name + ' inner type', linked_type)
            graphql_type = GraphQLList(inner_type)
        elif linked_class is not None and linked_type is None:
            # No linked type, must be a linked non-graph user-defined type.
            if linked_class not in non_graph_class_names:
                raise AssertionError(u'Property "{}" is declared as the inner type of '
                                     u'an embedded collection, but is not a non-graph class: '
                                     u'{}'.format(name, linked_class))
            if class_name in non_graph_class_names:
                raise AssertionError('Class {} is a non-graph class that contains a '
                                     'collection property {}. Only graph classes are allowed '
                                     'to have collections as properties.'
                                     .format(class_name, property_definition))
            # Don't include the fields and implemented interfaces, this information is already
            # stored in the SchemaGraph.
            graphql_type = GraphQLList(GraphQLObjectType(linked_class, {}, []))
        else:
            raise AssertionError(u'Property "{}" is an embedded collection but has '
                                 u'neither a linked class nor a linked type: '
                                 u'{}'.format(name, property_definition))
    else:
        graphql_type = get_graphql_scalar_type_or_raise(name, type_id)

    return graphql_type
