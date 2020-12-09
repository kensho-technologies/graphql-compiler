# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod
from collections import OrderedDict, namedtuple
from itertools import chain
from typing import Set

import six

from .exceptions import IllegalSchemaStateError, InvalidClassError, InvalidPropertyError


ILLEGAL_PROPERTY_NAME_PREFIXES = (
    # Prefixes that would make the GraphQL schema ambiguous,
    # since this is how it represents adjacent vertices.
    "out_",
    "in_",
    # Prefixes reserved for future extensions to the GraphQL schema,
    # in case we want to, e.g., add edge-based traversals, or "both()"-style traversals.
    "outE",
    "inE",
    "outV",
    "inV",
    "both_",
    "bothE_",
    "bothV_",
)


ILLEGAL_PROPERTY_NAMES = (
    # Names we reserve for referencing base connections as fields of an IndexDefinition object.
    "out",
    "in",
)


class SchemaGraph(object):
    """The SchemaGraph is a graph utility used to represent a OrientDB schema.

    The SchemaGraph contains a representation of all vertex and edge types in the graph,
    as well as their possible connections. This is useful when working with with paths
    on the graph. It also holds a fully denormalized schema for the graph.
    """

    def __init__(self, elements, inheritance_structure, all_indexes):
        """Create a new SchemaGraph.

        Args:
            elements: a dict, string -> SchemaElement, mapping each class in the schema to its
                      corresponding SchemaElement object.
            inheritance_structure: InheritanceStructure object, (with superclass_sets and
                                   subclass_sets properties), describing the inheritance structure
                                   of the SchemaGraph.
            all_indexes: set of IndexDefinitions, describing the indexes defined on the schema.

        Returns:
            fully-constructed SchemaGraph object
        """
        self._elements = elements
        self._inheritance_structure = inheritance_structure
        self._all_indexes = all_indexes
        self._class_to_indexes = self._get_class_to_indexes()

        self._vertex_class_names = _get_element_names_of_class(elements, VertexType)
        self._edge_class_names = _get_element_names_of_class(elements, EdgeType)
        self._non_graph_class_names = _get_element_names_of_class(elements, NonGraphElement)

    def get_element_by_class_name(self, class_name):
        """Return the SchemaElement for the specified class name."""
        return self._elements[class_name]

    def get_superclass_set(self, cls):
        """Return all class names that the given class inherits from, including itself."""
        return self._inheritance_structure.superclass_sets[cls]

    def get_subclass_set(self, cls):
        """Return all class names that inherit from this class, including itself."""
        return self._inheritance_structure.subclass_sets[cls]

    def get_default_property_values(self, classname):
        """Return a dict with default values for all properties declared on this class."""
        schema_element = self.get_element_by_class_name(classname)

        result = {
            property_name: property_descriptor.default
            for property_name, property_descriptor in six.iteritems(schema_element.properties)
        }

        return result

    def get_property_values_with_defaults(self, classname, property_values):
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
            raise InvalidClassError("Class does not exist: {}".format(class_name))

        return self._elements[class_name]

    def get_vertex_schema_element_or_raise(self, vertex_classname):
        """Return the schema element with the given name, asserting that it's of vertex type."""
        schema_element = self.get_element_by_class_name_or_raise(vertex_classname)

        if not schema_element.is_vertex:
            raise InvalidClassError("Non-vertex class provided: {}".format(vertex_classname))

        return schema_element

    def get_edge_schema_element_or_raise(self, edge_classname):
        """Return the schema element with the given name, asserting that it's of edge type."""
        schema_element = self.get_element_by_class_name_or_raise(edge_classname)

        if not schema_element.is_edge:
            raise InvalidClassError("Non-edge class provided: {}".format(edge_classname))

        return schema_element

    def get_unique_indexes_for_class(self, cls):
        """Return a frozenset of IndexDefinitions of unique indexes that apply to this class."""
        return frozenset(
            {
                index_definition
                for index_definition in self.get_all_indexes_for_class(cls)
                if index_definition.unique
            }
        )

    def get_properties_captured_by_index(self, index_definition, classname, props):
        """Return the dict of values captured by the index, or None if the index does not apply.

        Args:
            index_definition: IndexDefinition describing the index to be checked for coverage
            classname: string, the class to check for index coverage
            props: dict, the properties on the vertex or edge being checked for coverage
                   under the index

        Returns:
            dict or None:
                - dict of the key-value pairs covered by the index, if the index applies, or
                - None, if the index does not cover the specified class and properties
        """
        indexed_classes = self.get_subclass_set(index_definition.base_classname)
        if classname not in indexed_classes:
            return None

        covered_props = {field_name: props[field_name] for field_name in index_definition.fields}

        if index_definition.ignore_nulls:
            for value in six.itervalues(covered_props):
                if value is None:
                    # We found a None value in a null-ignoring index.
                    # The index does not apply.
                    return None

        return covered_props

    def get_all_indexes_for_class(self, cls):
        """Return a frozenset of all IndexDefinitions (unique or not) that apply to this class."""
        return self._class_to_indexes.get(cls, frozenset())

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
            raise InvalidClassError(
                "Expected a non-abstract vertex class, but {} is abstract".format(vertex_classname)
            )

    def validate_is_non_abstract_edge_type(self, edge_classname):
        """Validate that a edge classname corresponds to a non-abstract edge class."""
        element = self.get_edge_schema_element_or_raise(edge_classname)

        if element.abstract:
            raise InvalidClassError(
                "Expected a non-abstract vertex class, but {} is abstract".format(edge_classname)
            )

    def validate_properties_exist(self, classname, property_names):
        """Validate that the specified property names are indeed defined on the given class."""
        schema_element = self.get_element_by_class_name(classname)

        requested_properties = set(property_names)
        available_properties = set(schema_element.properties.keys())
        non_existent_properties = requested_properties - available_properties
        if non_existent_properties:
            raise InvalidPropertyError(
                'Class "{}" does not have definitions for properties "{}": '
                "{}".format(classname, non_existent_properties, property_names)
            )

    @property
    def class_names(self):
        """Return the set of all class names."""
        return set(six.iterkeys(self._elements))

    @property
    def vertex_class_names(self) -> Set[str]:
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

    @property
    def all_indexes(self):
        """Return the set of all indexes in the schema."""
        return self._all_indexes

    @property
    def unique_indexes(self):
        """Return the set of all unique indexes in the schema."""
        return frozenset(
            {index_definition for index_definition in self._all_indexes if index_definition.unique}
        )

    def _get_class_to_indexes(self):
        """Return a dict mapping class name to the class indexes."""
        # Record the fact that the index applies to all subclasses of the index base class.
        indexes_per_class = {}
        for index in self._all_indexes:
            for subclass_name in self.get_subclass_set(index.base_classname):
                indexes_per_class.setdefault(subclass_name, []).append(index)

        # Convert the lists into frozensets and assign to the property value.
        class_to_indexes = {
            classname: frozenset(definitions)
            for classname, definitions in six.iteritems(indexes_per_class)
        }

        return class_to_indexes


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

        # In the schema graph, both vertices and edges are represented with vertices.
        # These dicts have the name of the adjacent schema vertex in the appropriate direction.
        #
        # For vertex classes and non-graph classes:
        #   in  = the edge is attached with its head / arrow side
        #   out = the edge is attached with its tail side
        #
        # For edge classes:
        #   in  = the tail side of the edge
        #   out = the head / arrow side of the edge
        #
        # A non-graph class may only have connections if it's abstract and all of its non-abstract
        # subclasses are vertices.
        self.in_connections = set()
        self.out_connections = set()

        self._print_args = (
            class_name,
            abstract,
            properties,
            class_fields,
            self.in_connections,
            self.out_connections,
        ) + args
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
        """Make the SchemaElement's connections immutable."""
        self.in_connections = frozenset(self.in_connections)
        self.out_connections = frozenset(self.out_connections)

    def __str__(self):
        """Return a human-readable unicode representation of this SchemaElement."""
        printed_args = []
        if self._print_args:
            printed_args.append("{args}")
        if self._print_kwargs:
            printed_args.append("{kwargs}")

        template = "{cls_name}(" + ", ".join(printed_args) + ")"
        return template.format(
            cls_name=type(self).__name__, args=self._print_args, kwargs=self._print_kwargs
        )

    def __repr__(self):
        """Return a human-readable str representation of the SchemaElement object."""
        return self.__str__()


class VertexType(SchemaElement):

    # The parent class' __init__ method is marked abstract, and must be overridden.
    # See the parent class for more details.
    # pylint: disable=useless-super-delegation
    def __init__(self, class_name, abstract, properties, class_fields):
        """See base class __init__ method."""
        super(VertexType, self).__init__(class_name, abstract, properties, class_fields)

    # pylint: enable=useless-super-delegation


class EdgeType(SchemaElement):
    def __init__(
        self,
        class_name,
        abstract,
        properties,
        class_fields,
        base_in_connection=None,
        base_out_connection=None,
    ):
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
        super(EdgeType, self).__init__(
            class_name, abstract, properties, class_fields, base_in_connection, base_out_connection
        )

        if not abstract:
            _validate_non_abstract_edge_has_defined_base_connections(
                class_name, base_in_connection, base_out_connection
            )
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

    # The parent class' __init__ method is marked abstract, and must be overridden.
    # See the parent class for more details.
    # pylint: disable=useless-super-delegation
    def __init__(self, class_name, abstract, properties, class_fields):
        """See base class __init__ method."""
        super(NonGraphElement, self).__init__(class_name, abstract, properties, class_fields)

    # pylint: enable=useless-super-delegation


def _validate_non_abstract_edge_has_defined_base_connections(
    class_name, base_in_connection, base_out_connection
):
    """Validate that the non-abstract edge has its in/out base connections defined."""
    if not (base_in_connection and base_out_connection):
        raise IllegalSchemaStateError(
            "Found a non-abstract edge class with undefined or illegal "
            "in/out base_connection: {} {} {}".format(
                class_name, base_in_connection, base_out_connection
            )
        )


def _validate_property_names(class_name, properties):
    """Validate that properties do not have names that may cause problems in the GraphQL schema."""
    for property_name in properties:
        is_illegal_name = (
            not property_name
            or property_name.startswith(ILLEGAL_PROPERTY_NAME_PREFIXES)
            or property_name in ILLEGAL_PROPERTY_NAMES
        )
        if is_illegal_name:
            raise IllegalSchemaStateError(
                'Class "{}" has a property with an illegal name: '
                "{}".format(class_name, property_name)
            )


class InheritanceStructure(object):
    def __init__(self, direct_superclass_sets):
        """Create a new InheritanceStructure object.

        Args:
            direct_superclass_sets: dict, string -> set of strings, mapping a class
                                    to its direct superclasses.

        Returns:
            an InheritanceStructure object.
        """
        direct_superclass_sets = _get_toposorted_direct_superclass_sets(direct_superclass_sets)
        self._superclass_sets = _get_transitive_superclass_sets(direct_superclass_sets)
        self._subclass_sets = _get_subclass_sets_from_superclass_sets(self._superclass_sets)

    @property
    def superclass_sets(self):
        """Return a dict mapping each class to all classes it inherit from, including itself."""
        return self._superclass_sets

    @property
    def subclass_sets(self):
        """Return a dict mapping each class to all classes that inherit it, including itself."""
        return self._subclass_sets


def _get_toposorted_direct_superclass_sets(direct_superclass_sets):
    """Return a topologically sorted OrderedDict that maps each class to its direct superclasses.

    Args:
        direct_superclass_sets: dict, string -> set of strings, mapping a class
                                to its direct superclasses.

    Return:
        an OrderedDict toposorted by class inheritance. Each class appears before its subclasses.
    """

    def get_class_topolist(class_name, processed_classes, current_trace):
        """Return a topologically sorted list of this class's superclasses and the class itself.

        Args:
            class_name: string, name of the class to process.
            processed_classes: set of strings, a set of classes that have already been processed.
            current_trace: list of strings, list of classes traversed during the recursion.

        Returns:
            list of dicts, list of class names sorted in topological order.
        """
        # Check if this class has already been handled
        if class_name in processed_classes:
            return []

        if class_name in current_trace:
            raise AssertionError(
                "Encountered self-reference in dependency chain of {}".format(class_name)
            )

        class_list = []
        # Recursively process superclasses
        current_trace.add(class_name)
        for superclass_name in direct_superclass_sets[class_name]:
            class_list.extend(get_class_topolist(superclass_name, processed_classes, current_trace))
        current_trace.remove(class_name)
        # Do the bookkeeping
        class_list.append(class_name)
        processed_classes.add(class_name)

        return class_list

    toposorted = []
    for name in direct_superclass_sets.keys():
        toposorted.extend(get_class_topolist(name, set(), set()))
    return OrderedDict(
        (class_name, direct_superclass_sets[class_name]) for class_name in toposorted
    )


def _get_transitive_superclass_sets(toposorted_direct_superclass_sets):
    """Return the transitive superclass sets from the toposorted direct superclass sets."""
    # For each class name, construct its superclass set:
    # itself + the set of class names from which it inherits.
    superclass_sets = dict()
    for class_name, direct_superclass_set in six.iteritems(toposorted_direct_superclass_sets):
        superclass_set = set(direct_superclass_set)
        superclass_set.add(class_name)

        # Since the input data must be in topological order, the superclasses of
        # the current class should have already been processed.
        # A KeyError on the following line would mean that the input
        # was not topologically sorted.
        superclass_set.update(
            chain.from_iterable(
                superclass_sets[superclass_name] for superclass_name in direct_superclass_set
            )
        )

        # Freeze the superclass set so it can't ever be modified again.
        superclass_sets[class_name] = frozenset(superclass_set)
    return superclass_sets


def _get_subclass_sets_from_superclass_sets(superclass_sets):
    """Return a dict mapping each class to its set of subclasses."""
    subclass_sets = dict()
    for subclass_name, superclass_names in six.iteritems(superclass_sets):
        for superclass_name in superclass_names:
            subclass_sets.setdefault(superclass_name, set()).add(subclass_name)

    # Freeze all subclass sets so they can never be modified again,
    # making a list of all keys before modifying any of their values.
    # It's bad practice to mutate a dict while iterating over it.
    for class_name in list(six.iterkeys(subclass_sets)):
        subclass_sets[class_name] = frozenset(subclass_sets[class_name])

    return subclass_sets


def _get_element_names_of_class(elements, cls):
    """Return a frozenset of the names of the elements are instances of the class."""
    return frozenset({name for name, element in elements.items() if isinstance(element, cls)})


def link_schema_elements(elements, inheritance_structure):
    """For each edge, link the schema elements it connects to each other."""
    for edge_class_name in _get_element_names_of_class(elements, EdgeType):
        edge_element = elements[edge_class_name]

        from_class_name = edge_element.base_in_connection
        to_class_name = edge_element.base_out_connection

        if not from_class_name or not to_class_name:
            continue

        edge_schema_element = elements[edge_class_name]

        # Link from_class_name with edge_class_name
        for from_class in inheritance_structure.subclass_sets[from_class_name]:
            from_schema_element = elements[from_class]
            from_schema_element.out_connections.add(edge_class_name)
            edge_schema_element.in_connections.add(from_class)

        # Link edge_class_name with to_class_name
        for to_class in inheritance_structure.subclass_sets[to_class_name]:
            to_schema_element = elements[to_class]
            edge_schema_element.out_connections.add(to_class)
            to_schema_element.in_connections.add(edge_class_name)


# A way to describe a property's type and associated information:
#   - type: GraphQLType, the type of this property
#   - default: the default value for the property, used when a record is inserted without an
#              explicit value for this property. Set to None if no default is given in the schema.
PropertyDescriptor = namedtuple("PropertyDescriptor", ("type", "default"))


# A way to describe an index:
#   - name: Optional[string], the name of the index or None if the index does not have a name.
#   - base_classname: string, the name of the class on which the index is defined.
#   - fields: frozenset of strings, indicating which objects the index encompasses.
#             The 'in' and 'out' strings refer to the base connections.
#             All other strings reference the base class's properties.
#   - unique: bool, indicating whether this index is unique.
#   - ordered: bool, indicating whether this index is ordered.
#   - ignore_nulls: bool, indicating if the index ignores null values.
IndexDefinition = namedtuple(
    "IndexDefinition", ("name", "base_classname", "fields", "unique", "ordered", "ignore_nulls")
)
