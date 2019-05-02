# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod
from itertools import chain

from funcy.py3 import lsplit
import six

from .exceptions import IllegalSchemaStateError, InvalidClassError, InvalidPropertyError
from .schema_properties import (
    COLLECTION_PROPERTY_TYPES, EDGE_DESTINATION_PROPERTY_NAME, EDGE_SOURCE_PROPERTY_NAME,
    ILLEGAL_PROPERTY_NAME_PREFIXES, ORIENTDB_BASE_EDGE_CLASS_NAME, ORIENTDB_BASE_VERTEX_CLASS_NAME,
    PROPERTY_TYPE_LINK_ID, PropertyDescriptor, parse_default_property_value,
    validate_supported_property_type_id
)
from .utils import toposort_classes


def _validate_non_abstract_edge_has_defined_endpoint_types(class_name, base_connections):
    """Validate that the non-abstract edge has its in/out base connections defined."""
    edge_source = base_connections.get(EDGE_SOURCE_PROPERTY_NAME, None)
    edge_destination = base_connections.get(EDGE_DESTINATION_PROPERTY_NAME, None)
    if not edge_source and edge_destination:
        raise IllegalSchemaStateError(u'Found a non-abstract edge class with undefined or illegal '
                                      u'in/out base_connections: {} {}'.format(class_name,
                                                                               base_connections))


def _validate_non_edges_do_not_have_edge_like_properties(class_name, properties):
    """Validate that non-edges do not have the in/out properties defined."""
    has_source = EDGE_SOURCE_PROPERTY_NAME in properties
    has_destination = EDGE_DESTINATION_PROPERTY_NAME in properties

    if has_source or has_destination:
        raise IllegalSchemaStateError(u'Found a non-edge class that defines edge-like "in" or '
                                      u'"out" properties: {} {}'.format(class_name, properties))

    for property_name, property_descriptor in six.iteritems(properties):
        if property_descriptor.type_id == PROPERTY_TYPE_LINK_ID:
            raise IllegalSchemaStateError(u'Non-edge class "{}" has a property of type Link, this '
                                          u'is not allowed: {}'.format(class_name, property_name))


def _validate_edges_do_not_have_extra_links(class_name, properties):
    """Validate that edges do not have properties of Link type that aren't the edge endpoints."""
    for property_name, property_descriptor in six.iteritems(properties):
        if property_name in {EDGE_SOURCE_PROPERTY_NAME, EDGE_DESTINATION_PROPERTY_NAME}:
            continue

        if property_descriptor.type_id == PROPERTY_TYPE_LINK_ID:
            raise IllegalSchemaStateError(u'Edge class "{}" has a property of type Link that is '
                                          u'not an edge endpoint, this is not allowed: '
                                          u'{}'.format(class_name, property_name))


def _validate_property_names(class_name, properties):
    """Validate that properties do not have names that may cause problems in the GraphQL schema."""
    for property_name in properties:
        if not property_name or property_name.startswith(ILLEGAL_PROPERTY_NAME_PREFIXES):
            raise IllegalSchemaStateError(u'Class "{}" has a property with an illegal name: '
                                          u'{}'.format(class_name, property_name))


def _validate_collections_have_default_values(class_name, property_name, property_descriptor):
    """Validate that if the property is of collection type, it has a specified default value."""
    # We don't want properties of collection type having "null" values, since that may cause
    # unexpected errors during GraphQL query execution and other operations.
    if property_descriptor.type_id in COLLECTION_PROPERTY_TYPES:
        if property_descriptor.default is None:
            raise IllegalSchemaStateError(u'Class "{}" has a property "{}" of collection type with '
                                          u'no default value.'.format(class_name, property_name))


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


@six.python_2_unicode_compatible
@six.add_metaclass(ABCMeta)
class SchemaElement(object):

    # Since an abstract class without any abstract methods can be instantiated, we make the
    # init method abstract in order to make it impossible to instantiate this class.
    # Inspiration came from: https://stackoverflow.com/questions/44800659/python-abstract-class-init
    @abstractmethod
    def __init__(self, class_name, abstract, properties, class_fields, *args, **kwargs):
        """Create a new SchemaElement object.

        Args:
            class_name: string, the name of the schema element class.
            abstract: bool, True if the class is abstract, and False otherwise.
            properties: dict, property name -> PropertyDescriptor describing the properties of
                        the schema element.
            class_fields: dict, class field name -> class field value, both strings

        Returns:
            a SchemaElement with the given parameters
        """
        _validate_property_names(class_name, properties)

        self._class_name = class_name
        self._abstract = abstract
        self._properties = properties
        self._class_fields = class_fields

        self._print_args = (class_name, abstract, properties, class_fields) + args
        self._print_kwargs = kwargs

    @property
    def abstract(self):
        """Return True if the represented type is abstract, and False otherwise."""
        return self._abstract

    @property
    def class_name(self):
        """Return the name of the type that the schema element represents."""
        return self._class_name

    @property
    def properties(self):
        """Return a dict of property name to property descriptor for this schema element."""
        return self._properties

    @property
    def class_fields(self):
        """Return a dict containing all class fields defined on the schema element."""
        return self._class_fields

    @property
    def is_vertex(self):
        """Return True if the schema element represents a vertex type, and False otherwise."""
        return isinstance(self, VertexType)

    @property
    def is_edge(self):
        """Return True if the schema element represents an edge type, and False otherwise."""
        return isinstance(self, EdgeType)

    @property
    def is_non_graph(self):
        """Return True if the schema element represents a non-graph type, and False otherwise."""
        return isinstance(self, NonGraphElement)

    def freeze(self):
        """Make public mutable internal fields immutable."""
        pass

    def __str__(self):
        """Return a human-readable unicode representation of this SchemaElement."""
        printed_args = []
        if self._print_args:
            printed_args.append('{args}')
        if self._print_kwargs:
            printed_args.append('{kwargs}')

        template = u'{cls_name}(' + u', '.join(printed_args) + u')'
        return template.format(cls_name=type(self).__name__,
                               args=self._print_args,
                               kwargs=self._print_kwargs)

    def __repr__(self):
        """Return a human-readable str representation of the SchemaElement object."""
        return self.__str__()


class GraphElement(SchemaElement):

    # Since an abstract class without any abstract methods can be instantiated, we make the
    # init method abstract in order to make it impossible to instantiate this class.
    # Inspiration came from: https://stackoverflow.com/questions/44800659/python-abstract-class-init
    @abstractmethod
    def __init__(self, class_name, abstract, properties, class_fields, *args, **kwargs):
        super(GraphElement, self).__init__(class_name, abstract, properties, class_fields, args,
                                           kwargs)

        # In the schema graph, both vertices and edges are represented with vertices.
        # These dicts have the name of the adjacent schema vertex in the appropriate direction.
        #
        # For vertex classes:
        #   in  = the edge is attached with its head / arrow side
        #   out = the edge is attached with its tail side
        #
        # For edge classes:
        #   in  = the tail side of the edge
        #   out = the head / arrow side of the edge
        #
        # For non-graph classes, these properties are always empty sets.
        self.in_connections = set()
        self.out_connections = set()

    def freeze(self):
        """Make the SchemaElement's connections immutable."""
        super(GraphElement, self).freeze()
        self.in_connections = frozenset(self.in_connections)
        self.out_connections = frozenset(self.out_connections)


class VertexType(GraphElement):
    def __init__(self, class_name, abstract, properties, class_fields):
        super(VertexType, self).__init__(class_name, abstract, properties, class_fields)

        # Non-edges must not have properties like "in" or "out" defined, and
        # must not have properties of type "Link".
        _validate_non_edges_do_not_have_edge_like_properties(class_name, properties)


class EdgeType(GraphElement):
    def __init__(self, class_name, abstract, properties, class_fields, base_connections):
        """Create a new EdgeType object.

        Args:
            class_name: string, the name of the schema element class.
            abstract: bool, True if the class is abstract, and False otherwise.
            properties: dict, property name -> PropertyDescriptor describing the properties of
                        the schema element.
            class_fields: dict, class field name -> class field value, both strings
            base_connections: dict, string -> string. Maps a edge end, (one of 'in' or 'out'),
                              to the class that is allowed at that edge end and is the superclass of
                              all the classes allowed in that edge end. A base connection may
                              be missing for either end if the edge is abstract.

        Returns:
            a EdgeType with the given parameters
        """
        super(EdgeType, self).__init__(class_name, abstract, properties, class_fields,
                                       base_connections)

        _validate_edges_do_not_have_extra_links(class_name, base_connections)
        if not abstract:
            _validate_non_abstract_edge_has_defined_endpoint_types(class_name, base_connections)
        self._base_connections = base_connections

    @property
    def base_connections(self):
        """Return the base connections of the edge."""
        return self._base_connections


class NonGraphElement(SchemaElement):
    def __init__(self, class_name, abstract, properties, class_fields):
        super(NonGraphElement, self).__init__(class_name, abstract, properties, class_fields)

        # Non-edges must not have properties like "in" or "out" defined, and
        # must not have properties of type "Link".
        _validate_non_edges_do_not_have_edge_like_properties(class_name, properties)


class SchemaGraph(object):
    """The SchemaGraph is a graph utility used to represent a OrientDB schema.

    The SchemaGraph contains a representation of all vertex and edge types in the graph,
    as well as their possible connections. This is useful when working with with paths
    on the graph. It also holds a fully denormalized schema for the graph.
    """

    def __init__(self, schema_data):
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
        toposorted_schema_data = toposort_classes(schema_data)
        self._elements = dict()

        self._inheritance_sets = dict()
        self._subclass_sets = dict()

        self._vertex_class_names = set()
        self._edge_class_names = set()
        self._non_graph_class_names = set()

        self._set_up_inheritance_and_subclass_sets(toposorted_schema_data)

        class_name_to_definition = {
            class_definition['name']: class_definition
            for class_definition in toposorted_schema_data
        }

        # Initialize the _vertex_class_names, _edge_class_names, and _non_graph_class_names sets.
        self._split_classes_by_kind(class_name_to_definition)

        self._set_up_non_graph_elements(class_name_to_definition)
        self._set_up_edge_elements(class_name_to_definition)
        self._set_up_vertex_elements(class_name_to_definition)

        # Initialize the connections that show which schema classes can be connected to
        # which other schema classes, then freeze all schema elements.
        self._link_vertex_and_edge_types()
        for element in six.itervalues(self._elements):
            element.freeze()

    def get_element_by_class_name(self, class_name):
        """Return the SchemaElement for the specified class name"""
        return self._elements[class_name]

    def get_inheritance_set(self, cls):
        """Return all class names that the given class inherits from, including itself."""
        return self._inheritance_sets[cls]

    def get_subclass_set(self, cls):
        """Return all class names that inherit from this class, including itself."""
        return self._subclass_sets[cls]

    def get_default_property_values(self, classname):
        """Return a dict with default values for all properties declared on this class."""
        schema_element = self.get_element_by_class_name(classname)

        result = {
            property_name: property_descriptor.default
            for property_name, property_descriptor in six.iteritems(schema_element.properties)
        }

        if schema_element.is_edge:
            # Remove the source/destination properties for edges, if they exist.
            result.pop(EDGE_SOURCE_PROPERTY_NAME, None)
            result.pop(EDGE_DESTINATION_PROPERTY_NAME, None)

        return result

    def _get_property_values_with_defaults(self, classname, property_values):
        """Return the property values for the class, with default values applied where needed."""
        # To uphold OrientDB semantics, make a new dict with all property values set
        # to their default values, which are None if no default was set.
        # Then, overwrite its data with the supplied property values.
        final_values = self.get_default_property_values(classname)
        final_values.update(property_values)
        return final_values

    def get_element_by_class_name_or_raise(self, class_name):
        """Return the SchemaElement for the specified class name, asserting that it exists."""
        if class_name not in self._elements:
            raise InvalidClassError(u'Class does not exist: {}'.format(class_name))

        return self._elements[class_name]

    def get_vertex_schema_element_or_raise(self, vertex_classname):
        """Return the schema element with the given name, asserting that it's of vertex type."""
        schema_element = self.get_element_by_class_name_or_raise(vertex_classname)

        if not schema_element.is_vertex:
            raise InvalidClassError(u'Non-vertex class provided: {}'.format(vertex_classname))

        return schema_element

    def get_edge_schema_element_or_raise(self, edge_classname):
        """Return the schema element with the given name, asserting that it's of edge type."""
        schema_element = self.get_element_by_class_name_or_raise(edge_classname)

        if not schema_element.is_edge:
            raise InvalidClassError(u'Non-edge class provided: {}'.format(edge_classname))

        return schema_element

    def validate_is_vertex_type(self, vertex_classname):
        """Validate that a vertex classname indeed corresponds to a vertex class."""
        self.get_vertex_schema_element_or_raise(vertex_classname)

    def validate_is_edge_type(self, edge_classname):
        """Validate that a edge classname indeed corresponds to a edge class."""
        self.get_edge_schema_element_or_raise(edge_classname)

    def validate_is_non_abstract_vertex_type(self, vertex_classname):
        """Validate that a vertex classname corresponds to a non-abstract vertex class."""
        element = self.get_vertex_schema_element_or_raise(vertex_classname)

        if element.abstract:
            raise InvalidClassError(u'Expected a non-abstract vertex class, but {} is abstract'
                                    .format(vertex_classname))

    def validate_is_non_abstract_edge_type(self, edge_classname):
        """Validate that a edge classname corresponds to a non-abstract edge class."""
        element = self.get_edge_schema_element_or_raise(edge_classname)

        if element.abstract:
            raise InvalidClassError(u'Expected a non-abstract vertex class, but {} is abstract'
                                    .format(edge_classname))

    def validate_properties_exist(self, classname, property_names):
        """Validate that the specified property names are indeed defined on the given class."""
        schema_element = self.get_element_by_class_name(classname)

        requested_properties = set(property_names)
        available_properties = set(schema_element.properties.keys())
        non_existent_properties = requested_properties - available_properties
        if non_existent_properties:
            raise InvalidPropertyError(
                u'Class "{}" does not have definitions for properties "{}": '
                u'{}'.format(classname, non_existent_properties, property_names))

    @property
    def class_names(self):
        """Return the set of all class names"""
        return set(six.iterkeys(self._elements))

    @property
    def vertex_class_names(self):
        """Return the set of vertex class names in the SchemaGraph."""
        return self._vertex_class_names

    @property
    def edge_class_names(self):
        """Return the set of edge class names in the SchemaGraph."""
        return self._edge_class_names

    @property
    def non_graph_class_names(self):
        """Return the set of non-graph class names in the SchemaGraph."""
        return self._non_graph_class_names

    def _set_up_inheritance_and_subclass_sets(self, schema_data):
        """Load all inheritance data from the OrientDB schema. Used as part of __init__."""
        # For each class name, construct its inheritance set:
        # itself + the set of class names from which it inherits.
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
                self._inheritance_sets[superclass_name]
                for superclass_name in immediate_superclass_names
            ))

            # Freeze the inheritance set so it can't ever be modified again.
            self._inheritance_sets[class_name] = frozenset(inheritance_set)

        # For each class name, construct its subclass set:
        # itself + the set of class names that inherit from it.
        for subclass_name, superclass_names in six.iteritems(self._inheritance_sets):
            for superclass_name in superclass_names:
                self._subclass_sets.setdefault(
                    superclass_name, set()).add(subclass_name)

        # Freeze all subclass sets so they can never be modified again,
        # making a list of all keys before modifying any of their values.
        # It's bad practice to mutate a dict while iterating over it.
        for class_name in list(six.iterkeys(self._subclass_sets)):
            self._subclass_sets[class_name] = frozenset(self._subclass_sets[class_name])

    def _split_classes_by_kind(self, class_name_to_definition):
        """Assign each class to the vertex, edge or non-graph type sets based on its kind."""
        for class_name in class_name_to_definition:
            inheritance_set = self._inheritance_sets[class_name]

            is_vertex = ORIENTDB_BASE_VERTEX_CLASS_NAME in inheritance_set
            is_edge = ORIENTDB_BASE_EDGE_CLASS_NAME in inheritance_set

            if is_vertex and is_edge:
                raise AssertionError(u'Class {} appears to be both a vertex and an edge class: '
                                     u'{}'.format(class_name, inheritance_set))
            elif is_vertex:
                self._vertex_class_names.add(class_name)
            elif is_edge:
                self._edge_class_names.add(class_name)
            else:
                self._non_graph_class_names.add(class_name)

        # Freeze the classname sets so they cannot be modified again.
        self._vertex_class_names = frozenset(self._vertex_class_names)
        self._edge_class_names = frozenset(self._edge_class_names)
        self._non_graph_class_names = frozenset(self._non_graph_class_names)

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

            base_connections = self._get_base_connections(
                class_name, class_name_to_definition, link_property_definitions, abstract)
            property_name_to_descriptor = self._get_element_properties(
                class_name, non_link_property_definitions)

            self._elements[class_name] = EdgeType(
                class_name, abstract, property_name_to_descriptor, class_fields, base_connections)

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

    def _get_base_connections(self, class_name, class_name_to_definition,
                              link_property_definitions, abstract):
        """Return the base connections of an EdgeType."""
        base_connections = {}
        links = {EDGE_DESTINATION_PROPERTY_NAME: set(), EDGE_SOURCE_PROPERTY_NAME: set()}

        for property_definition in link_property_definitions:
            self._validate_link_definition(class_name_to_definition, property_definition)
            links[property_definition['name']].add(property_definition['linkedClass'])

        for link_direction, linked_classes in six.iteritems(links):
            # If there are multiple in/out properties, we choose to include the one that
            # is a subclass of all the elements present in the in/out properties.
            for linked_class in linked_classes:
                subclass_set = self._subclass_sets[linked_class]
                if len(linked_classes.intersection(subclass_set)) == 1:
                    base_direction_connection = base_connections.get(link_direction, None)
                    if base_direction_connection and base_direction_connection != linked_class:
                        raise AssertionError(u'There already exists class "{}" in addition '
                                             u'to class "{}" which is a subclass of all '
                                             u'{} properties for class "{}".'
                                             .format(base_direction_connection,
                                                     linked_class, link_direction, class_name))
                    base_connections[link_direction] = linked_class

            if link_direction not in base_connections and not abstract:
                raise AssertionError(u'For link direction "{}" of non-abstract edge class "{}", '
                                     u'no such subclass-of-all-elements exists.'
                                     .format(link_direction, class_name))
        return base_connections

    def _validate_link_definition(self, class_name_to_definition, property_definition):
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
        if linked_class not in self._vertex_class_names:
            is_linked_class_abstract = class_name_to_definition[linked_class]['abstract']
            all_subclasses_are_vertices = True
            for subclass in self._subclass_sets[linked_class]:
                if subclass != linked_class and subclass not in self.vertex_class_names:
                    all_subclasses_are_vertices = False
                    break
            if not (is_linked_class_abstract and all_subclasses_are_vertices):
                raise AssertionError(u'Property "{}" is declared as a Link to class {}, but '
                                     u'that class is neither a vertex nor is it an '
                                     u'abstract class whose subclasses are all vertices!'
                                     .format(name, linked_class))

    def _get_element_properties(self, class_name, non_link_property_definitions):
        """Return the SchemaElement's properties from the OrientDB non-link property definitions."""
        property_name_to_descriptor = {}
        for property_definition in non_link_property_definitions:
            property_name = property_definition['name']

            if property_name in property_name_to_descriptor:
                raise AssertionError(u'The property "{}" on class "{}" is defined '
                                     u'more than once, this is not allowed!'
                                     .format(property_name, class_name))

            property_descriptor = self._create_descriptor_from_property_definition(
                class_name, property_definition)
            property_name_to_descriptor[property_name] = property_descriptor
        return property_name_to_descriptor

    def _create_descriptor_from_property_definition(self, class_name, property_definition):
        """Return a PropertyDescriptor corresponding to the non-link property definition."""
        name = property_definition['name']
        type_id = property_definition['type']
        linked_class = property_definition.get('linkedClass', None)
        linked_type = property_definition.get('linkedType', None)
        qualifier = None

        validate_supported_property_type_id(name, type_id)

        if type_id == PROPERTY_TYPE_LINK_ID:
            raise AssertionError(u'Found a property of type Link on a non-edge class: '
                                 u'{} {}'.format(name, class_name))
        elif type_id in COLLECTION_PROPERTY_TYPES:
            if linked_class is not None and linked_type is not None:
                raise AssertionError(u'Property "{}" unexpectedly has both a linked class and '
                                     u'a linked type: {}'.format(name, property_definition))
            elif linked_type is not None and linked_class is None:
                # No linked class, must be a linked native OrientDB type.
                validate_supported_property_type_id(name + ' inner type', linked_type)

                qualifier = linked_type
            elif linked_class is not None and linked_type is None:
                # No linked type, must be a linked non-graph user-defined type.
                if linked_class not in self._non_graph_class_names:
                    raise AssertionError(u'Property "{}" is declared as the inner type of '
                                         u'an embedded collection, but is not a non-graph class: '
                                         u'{}'.format(name, linked_class))

                qualifier = linked_class
            else:
                raise AssertionError(u'Property "{}" is an embedded collection but has '
                                     u'neither a linked class nor a linked type: '
                                     u'{}'.format(name, property_definition))

        default_value = None
        default_value_string = property_definition.get('defaultValue', None)
        if default_value_string is not None:
            default_value = parse_default_property_value(name, type_id, default_value_string)

        descriptor = PropertyDescriptor(type_id=type_id, qualifier=qualifier, default=default_value)
        # Sanity-check the descriptor before returning it.
        _validate_collections_have_default_values(class_name, name, descriptor)
        return descriptor

    def _link_vertex_and_edge_types(self):
        """For each edge, link it to the vertex types it connects to each other."""
        for edge_class_name in self._edge_class_names:
            edge_element = self._elements[edge_class_name]

            if (EDGE_SOURCE_PROPERTY_NAME not in edge_element.base_connections or
                    EDGE_DESTINATION_PROPERTY_NAME not in edge_element.base_connections):
                if edge_element.abstract:
                    continue
                else:
                    raise AssertionError(u'Found a non-abstract edge class with undefined '
                                         u'endpoint types: {}'.format(edge_element))

            from_class_name = edge_element.base_connections[EDGE_SOURCE_PROPERTY_NAME]
            to_class_name = edge_element.base_connections[EDGE_DESTINATION_PROPERTY_NAME]

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


def _get_link_and_non_link_properties(property_definitions):
    """Return a class's link and non link OrientDB property definitions."""
    link_property_names = {EDGE_DESTINATION_PROPERTY_NAME, EDGE_SOURCE_PROPERTY_NAME}
    return lsplit(lambda x: x['name'] in link_property_names, property_definitions)


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
