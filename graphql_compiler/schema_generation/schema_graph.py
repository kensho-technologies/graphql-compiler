# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod
from collections import namedtuple

import six

from .exceptions import (
    ILLEGAL_PROPERTY_NAME_PREFIXES, IllegalSchemaStateError, InvalidClassError,
    InvalidPropertyError
)


class SchemaGraph(object):
    """The SchemaGraph is a graph utility used to represent a OrientDB schema.

    The SchemaGraph contains a representation of all vertex and edge types in the graph,
    as well as their possible connections. This is useful when working with with paths
    on the graph. It also holds a fully denormalized schema for the graph.
    """

    def __init__(self, elements, inheritance_sets):
        """Create a new SchemaGraph.

        Args:
            elements: a dict, string -> SchemaElement, mapping each class in the schema to its
                      corresponding SchemaElement object.
            inheritance_sets: a dict, string -> set of strings, mapping each class to its
                              superclasses. The set of superclasses includes the class itself and
                              the transitive superclasses. For instance, if A is a superclass of B,
                              and B is a superclass of C, then C's inheritance set is {'A', 'B'}.

        Returns:
            fully-constructed SchemaGraph object
        """
        self._elements = elements
        self._inheritance_sets = inheritance_sets
        self._subclass_sets = get_subclass_sets_from_inheritance_sets(inheritance_sets)

        self._vertex_class_names = self._get_element_names_of_class(VertexType)
        self._edge_class_names = self._get_element_names_of_class(EdgeType)
        self._non_graph_class_names = self._get_element_names_of_class(NonGraphElement)

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

    def _get_element_names_of_class(self, cls):
        """Return a dict mapping an element name to """
        return {
            name: element
            for name, element in self._elements.items()
            if isinstance(element, cls)
        }


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


class EdgeType(GraphElement):
    def __init__(self, class_name, abstract, properties, class_fields,
                 base_in_connection=None, base_out_connection=None):
        """Create a new EdgeType object.

        Args:
            class_name: string, the name of the schema element class.
            abstract: bool, True if the class is abstract, and False otherwise.
            properties: dict, property name -> PropertyDescriptor describing the properties of
                        the schema element.
            class_fields: dict, class field name -> class field value, both strings
            base_in_connection: optional string, the class allowed at tail end of the edge
                                end and is a superclass of all the classes allowed in the tail end
                                edge end. If the edge is abstract, the field may be None
                                since such a class might not exist.
            base_out_connection: optional string, similarly defined as base_in_connection.

        Returns:
            a EdgeType with the given parameters
        """
        super(EdgeType, self).__init__(class_name, abstract, properties, class_fields,
                                       base_in_connection, base_out_connection)

        if not abstract:
            _validate_non_abstract_edge_has_defined_base_connections(
                class_name, base_in_connection, base_out_connection)
        self._base_in_connection = base_in_connection
        self._base_out_connection = base_out_connection

    @property
    def base_in_connection(self):
        """Return the base in connection of the edge."""
        return self._base_in_connection

    @property
    def base_out_connection(self):
        """Return the base out connection of the edge."""
        return self._base_out_connection


class NonGraphElement(SchemaElement):
    def __init__(self, class_name, abstract, properties, class_fields):
        super(NonGraphElement, self).__init__(class_name, abstract, properties, class_fields)


def _validate_non_abstract_edge_has_defined_base_connections(
        class_name, base_in_connection, base_out_connection):
    """Validate that the non-abstract edge has its in/out base connections defined."""
    if not (base_in_connection and base_out_connection):
        raise IllegalSchemaStateError(u'Found a non-abstract edge class with undefined or illegal '
                                      u'in/out base_connection: {} {} {}'
                                      .format(class_name, base_in_connection, base_out_connection))


def _validate_property_names(class_name, properties):
    """Validate that properties do not have names that may cause problems in the GraphQL schema."""
    for property_name in properties:
        if not property_name or property_name.startswith(ILLEGAL_PROPERTY_NAME_PREFIXES):
            raise IllegalSchemaStateError(u'Class "{}" has a property with an illegal name: '
                                          u'{}'.format(class_name, property_name))


def get_subclass_sets_from_inheritance_sets(inheritance_sets):
    """Return a dict mapping each class to its set of subclasses."""
    subclass_sets = dict()
    for subclass_name, superclass_names in six.iteritems(inheritance_sets):
        for superclass_name in superclass_names:
            subclass_sets.setdefault(superclass_name, set()).add(subclass_name)

    # Freeze all subclass sets so they can never be modified again,
    # making a list of all keys before modifying any of their values.
    # It's bad practice to mutate a dict while iterating over it.
    for class_name in list(six.iterkeys(subclass_sets)):
        subclass_sets[class_name] = frozenset(subclass_sets[class_name])

    return subclass_sets


# A way to describe a property's type and associated information:
#   - type: GraphQLType, the type of this property
#   - default: the default value for the property, used when a record is inserted without an
#              explicit value for this property. Set to None if no default is given in the schema.
PropertyDescriptor = namedtuple('PropertyDescriptor', ('type', 'default'))
