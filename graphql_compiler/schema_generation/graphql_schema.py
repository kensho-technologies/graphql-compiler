# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict
from itertools import chain

from graphql.type import (
    GraphQLBoolean, GraphQLField, GraphQLFloat, GraphQLInt, GraphQLInterfaceType, GraphQLList,
    GraphQLObjectType, GraphQLSchema, GraphQLString, GraphQLUnionType
)
import six

from ..schema import (
    DIRECTIVES, EXTENDED_META_FIELD_DEFINITIONS, GraphQLDate, GraphQLDateTime, GraphQLDecimal
)
from .exceptions import EmptySchemaError
from .schema_properties import (
    EDGE_DESTINATION_PROPERTY_NAME, EDGE_SOURCE_PROPERTY_NAME, ORIENTDB_BASE_VERTEX_CLASS_NAME,
    PROPERTY_TYPE_BOOLEAN_ID, PROPERTY_TYPE_DATE_ID, PROPERTY_TYPE_DATETIME_ID,
    PROPERTY_TYPE_DECIMAL_ID, PROPERTY_TYPE_DOUBLE_ID, PROPERTY_TYPE_EMBEDDED_LIST_ID,
    PROPERTY_TYPE_EMBEDDED_SET_ID, PROPERTY_TYPE_FLOAT_ID, PROPERTY_TYPE_INTEGER_ID,
    PROPERTY_TYPE_STRING_ID
)


def _get_inherited_field_types(class_to_field_type_overrides, schema_graph):
    """Return a dictionary describing the field type overrides in subclasses."""
    inherited_field_type_overrides = dict()
    for superclass_name, field_type_overrides in class_to_field_type_overrides.items():
        for subclass_name in schema_graph.get_subclass_set(superclass_name):
            inherited_field_type_overrides.setdefault(subclass_name, dict())
            inherited_field_type_overrides[subclass_name].update(field_type_overrides)
    return inherited_field_type_overrides


def _validate_overriden_fields_are_not_defined_in_superclasses(class_to_field_type_overrides,
                                                               schema_graph):
    """Assert that the fields we want to override are not defined in superclasses."""
    for class_name, field_type_overrides in six.iteritems(class_to_field_type_overrides):
        for superclass_name in schema_graph.get_inheritance_set(class_name):
            if superclass_name != class_name:
                superclass = schema_graph.get_element_by_class_name(superclass_name)
                for field_name in field_type_overrides:
                    if field_name in superclass.properties:
                        raise AssertionError(
                            u'Attempting to override field "{}" from class "{}", but the field is '
                            u'defined in superclass "{}"'
                            .format(field_name, class_name, superclass_name))


def _property_descriptor_to_graphql_type(property_obj):
    """Return the best GraphQL type representation for an OrientDB property descriptor."""
    property_type = property_obj.type_id
    scalar_types = {
        PROPERTY_TYPE_BOOLEAN_ID: GraphQLBoolean,
        PROPERTY_TYPE_DATE_ID: GraphQLDate,
        PROPERTY_TYPE_DATETIME_ID: GraphQLDateTime,
        PROPERTY_TYPE_DECIMAL_ID: GraphQLDecimal,
        PROPERTY_TYPE_DOUBLE_ID: GraphQLFloat,
        PROPERTY_TYPE_FLOAT_ID: GraphQLFloat,
        PROPERTY_TYPE_INTEGER_ID: GraphQLInt,
        PROPERTY_TYPE_STRING_ID: GraphQLString,
    }

    result = scalar_types.get(property_type, None)
    if result:
        return result

    mapping_types = {
        PROPERTY_TYPE_EMBEDDED_SET_ID: GraphQLList,
        PROPERTY_TYPE_EMBEDDED_LIST_ID: GraphQLList,
    }
    wrapping_type = mapping_types.get(property_type, None)
    if wrapping_type:
        linked_property_obj = property_obj.qualifier
        # There are properties that are embedded collections of non-primitive types,
        # for example, ProxyEventSet.scalar_parameters.
        # The GraphQL compiler does not currently support these.
        if linked_property_obj in scalar_types:
            return wrapping_type(scalar_types[linked_property_obj])

    # We weren't able to represent this property in GraphQL, so we'll hide it instead.
    return None


def _get_union_type_name(type_names_to_union):
    """Construct a unique union type name based on the type names being unioned."""
    if not type_names_to_union:
        raise AssertionError(u'Expected a non-empty list of type names to union, received: '
                             u'{}'.format(type_names_to_union))
    return u'Union__' + u'__'.join(sorted(type_names_to_union))


def _get_fields_for_class(schema_graph, graphql_types, field_type_overrides, hidden_classes,
                          cls_name):
    """Return a dict from field name to GraphQL field type, for the specified graph class."""
    properties = schema_graph.get_element_by_class_name(cls_name).properties

    # Add leaf GraphQL fields (class properties).
    all_properties = {
        property_name: _property_descriptor_to_graphql_type(property_obj)
        for property_name, property_obj in six.iteritems(properties)
    }
    result = {
        property_name: graphql_representation
        for property_name, graphql_representation in six.iteritems(all_properties)
        if graphql_representation is not None
    }

    # Add edge GraphQL fields (edges to other vertex classes).
    schema_element = schema_graph.get_element_by_class_name(cls_name)
    outbound_edges = (
        ('out_{}'.format(out_edge_name),
         schema_graph.get_element_by_class_name(out_edge_name).properties[
             EDGE_DESTINATION_PROPERTY_NAME].qualifier)
        for out_edge_name in schema_element.out_connections
    )
    inbound_edges = (
        ('in_{}'.format(in_edge_name),
         schema_graph.get_element_by_class_name(in_edge_name).properties[
             EDGE_SOURCE_PROPERTY_NAME].qualifier)
        for in_edge_name in schema_element.in_connections
    )
    for field_name, to_type_name in chain(outbound_edges, inbound_edges):
        edge_endpoint_type_name = None
        subclasses = schema_graph.get_subclass_set(to_type_name)

        to_type_abstract = schema_graph.get_element_by_class_name(to_type_name).abstract
        if not to_type_abstract and len(subclasses) > 1:
            # If the edge endpoint type has no subclasses, it can't be coerced into any other type.
            # If the edge endpoint type is abstract (an interface type), we can already
            # coerce it to the proper type with a GraphQL fragment. However, if the endpoint type
            # is non-abstract and has subclasses, we need to return its subclasses as an union type.
            # This is because GraphQL fragments cannot be applied on concrete types, and
            # GraphQL does not support inheritance of concrete types.
            type_names_to_union = [
                subclass
                for subclass in subclasses
                if subclass not in hidden_classes
            ]
            if type_names_to_union:
                edge_endpoint_type_name = _get_union_type_name(type_names_to_union)
        else:
            if to_type_name not in hidden_classes:
                edge_endpoint_type_name = to_type_name

        if edge_endpoint_type_name is not None:
            # If we decided to not hide this edge due to its endpoint type being non-representable,
            # represent the edge field as the GraphQL type List(edge_endpoint_type_name).
            result[field_name] = GraphQLList(graphql_types[edge_endpoint_type_name])

    for field_name, field_type in six.iteritems(field_type_overrides):
        if field_name not in result:
            raise AssertionError(u'Attempting to override field "{}" from class "{}", but the '
                                 u'class does not contain said field'.format(field_name, cls_name))
        else:
            result[field_name] = field_type

    return result


def _create_field_specification(schema_graph, graphql_types, field_type_overrides,
                                hidden_classes, cls_name):
    """Return a function that specifies the fields present on the given type."""
    def field_maker_func():
        """Create and return the fields for the given GraphQL type."""
        result = EXTENDED_META_FIELD_DEFINITIONS.copy()
        result.update(OrderedDict([
            (name, GraphQLField(value))
            for name, value in sorted(six.iteritems(_get_fields_for_class(
                schema_graph, graphql_types, field_type_overrides, hidden_classes, cls_name)),
                key=lambda x: x[0])
        ]))
        return result

    return field_maker_func


def _create_interface_specification(schema_graph, graphql_types, hidden_classes, cls_name):
    """Return a function that specifies the interfaces implemented by the given type."""
    def interface_spec():
        """Return a list of GraphQL interface types implemented by the type named 'cls_name'."""
        abstract_inheritance_set = (
            superclass_name
            for superclass_name in sorted(list(schema_graph.get_inheritance_set(cls_name)))
            if (superclass_name not in hidden_classes and
                schema_graph.get_element_by_class_name(superclass_name).abstract)
        )

        return [
            graphql_types[x]
            for x in abstract_inheritance_set
            if x not in hidden_classes
        ]

    return interface_spec


def _create_union_types_specification(schema_graph, graphql_types, hidden_classes, base_name):
    """Return a function that gives the types in the union type rooted at base_name."""
    # When edges point to vertices of type base_name, and base_name is both non-abstract and
    # has subclasses, we need to represent the edge endpoint type with a union type based on
    # base_name and its subclasses. This function calculates what types that union should include.
    def types_spec():
        """Return a list of GraphQL types that this class' corresponding union type includes."""
        return [
            graphql_types[x]
            for x in sorted(list(schema_graph.get_subclass_set(base_name)))
            if x not in hidden_classes
        ]

    return types_spec


def get_graphql_schema_from_schema_graph(schema_graph, class_to_field_type_overrides,
                                         hidden_classes):
    """Return a GraphQL schema object corresponding to the schema of the given schema graph.

    Args:
        schema_graph: SchemaGraph
        class_to_field_type_overrides: dict, class name -> {field name -> field type},
                                       (string -> {string -> GraphQLType}). Used to override the
                                       type of a field in the class where it's first defined and all
                                       the class's subclasses.
        hidden_classes: set of strings, classes to not include in the GraphQL schema.

    Returns:
        tuple of (GraphQL schema object, GraphQL type equivalence hints dict).
        The tuple is of type (GraphQLSchema, GraphQLUnionType).
    """
    _validate_overriden_fields_are_not_defined_in_superclasses(class_to_field_type_overrides,
                                                               schema_graph)

    # The field types of subclasses must also be overridden.
    # Remember that the result returned by get_subclass_set(class_name) includes class_name itself.
    inherited_field_type_overrides = _get_inherited_field_types(class_to_field_type_overrides,
                                                                schema_graph)

    # We remove the base vertex class from the schema if it has no properties.
    # If it has no properties, it's meaningless and makes the schema less syntactically sweet.
    if not schema_graph.get_element_by_class_name(ORIENTDB_BASE_VERTEX_CLASS_NAME).properties:
        hidden_classes.add(ORIENTDB_BASE_VERTEX_CLASS_NAME)

    graphql_types = OrderedDict()
    type_equivalence_hints = OrderedDict()

    # For each vertex class, construct its analogous GraphQL type representation.
    for vertex_cls_name in sorted(schema_graph.vertex_class_names):
        vertex_cls = schema_graph.get_element_by_class_name(vertex_cls_name)
        if vertex_cls_name in hidden_classes:
            continue

        inherited_field_type_overrides.setdefault(vertex_cls_name, dict())
        field_type_overrides = inherited_field_type_overrides[vertex_cls_name]

        # We have to use delayed type binding here, because some of the type references
        # are circular: if an edge connects vertices of types A and B, then
        # GraphQL type A has a List[B] field, and type B has a List[A] field.
        # To avoid the circular dependency, GraphQL allows us to initialize the types
        # initially without their field information, and fill in their field information
        # later using a lambda function as the second argument to GraphQLObjectType.
        # This lambda function will be called on each type after all types are created
        # in their initial blank state.
        #
        # However, 'cls_name' is a variable that would not be correctly bound
        # if we naively tried to construct a lambda in-place, because Python lambdas
        # are not closures. Instead, call a function with 'cls_name' as an argument,
        # and have that function construct and return the required lambda.
        field_specification_lambda = _create_field_specification(
            schema_graph, graphql_types, field_type_overrides, hidden_classes, vertex_cls_name)

        # Abstract classes are interfaces, concrete classes are object types.
        current_graphql_type = None
        if vertex_cls.abstract:
            # "fields" is a kwarg in the interface constructor, even though
            # it's a positional arg in the object type constructor.
            current_graphql_type = GraphQLInterfaceType(vertex_cls_name,
                                                        fields=field_specification_lambda)
        else:
            # For similar reasons as the field_specification_lambda,
            # we need to create an interface specification lambda function that
            # specifies the interfaces implemented by this type.
            interface_specification_lambda = _create_interface_specification(
                schema_graph, graphql_types, hidden_classes, vertex_cls_name)

            # N.B.: Ignore the "is_type_of" argument below, it is simply a circumvention of
            #       a sanity check inside the GraphQL library. The library assumes that we'll use
            #       its execution system, so it complains that we don't provide a means to
            #       differentiate between different implementations of the same interface.
            #       We don't care, because we compile the GraphQL query to a database query.
            current_graphql_type = GraphQLObjectType(vertex_cls_name,
                                                     field_specification_lambda,
                                                     interfaces=interface_specification_lambda,
                                                     is_type_of=lambda: None)

        graphql_types[vertex_cls_name] = current_graphql_type

    # For each vertex class, construct all union types representations.
    for vertex_cls_name in sorted(schema_graph.vertex_class_names):
        vertex_cls = schema_graph.get_element_by_class_name(vertex_cls_name)
        if vertex_cls_name in hidden_classes:
            continue

        vertex_cls_subclasses = schema_graph.get_subclass_set(vertex_cls_name)
        if not vertex_cls.abstract and len(vertex_cls_subclasses) > 1:
            # In addition to creating this class' corresponding GraphQL type, we'll need a
            # union type to represent it when it appears as the endpoint of an edge.
            union_type_name = _get_union_type_name(vertex_cls_subclasses)

            # For similar reasons as the field_specification_lambda,
            # we need to create a union type specification lambda function that specifies
            # the types that this union type is composed of.
            type_specification_lambda = _create_union_types_specification(
                schema_graph, graphql_types, hidden_classes, vertex_cls_name)

            union_type = GraphQLUnionType(union_type_name, types=type_specification_lambda)
            graphql_types[union_type_name] = union_type
            type_equivalence_hints[graphql_types[vertex_cls_name]] = union_type

    # Include all abstract non-vertex classes whose only non-abstract subclasses are vertices.
    for non_graph_cls_name in sorted(schema_graph.non_graph_class_names):
        if non_graph_cls_name in hidden_classes:
            continue
        if not schema_graph.get_element_by_class_name(non_graph_cls_name).abstract:
            continue

        cls_subclasses = schema_graph.get_subclass_set(non_graph_cls_name)
        # No need to add the possible abstract class if it doesn't have subclasses besides itself.
        if len(cls_subclasses) > 1:
            all_non_abstract_subclasses_are_vertices = True

            # Check all non-abstract subclasses are vertices.
            for subclass_name in cls_subclasses:
                subclass = schema_graph.get_element_by_class_name(subclass_name)
                if subclass_name != non_graph_cls_name:
                    if not subclass.abstract and not subclass.is_vertex:
                        all_non_abstract_subclasses_are_vertices = False
                        break

            if all_non_abstract_subclasses_are_vertices:
                # Add abstract class as an interface.
                inherited_field_type_overrides.setdefault(non_graph_cls_name, dict())
                field_type_overrides = inherited_field_type_overrides[non_graph_cls_name]
                field_specification_lambda = _create_field_specification(
                    schema_graph, graphql_types, field_type_overrides, hidden_classes,
                    non_graph_cls_name)
                graphql_type = GraphQLInterfaceType(non_graph_cls_name,
                                                    fields=field_specification_lambda)
                graphql_types[non_graph_cls_name] = graphql_type

    if not graphql_types:
        raise EmptySchemaError(u'After evaluating all subclasses of V, we were not able to find '
                               u'visible schema data to import into the GraphQL schema object')

    # Create the root query GraphQL type. Consists of all non-union classes, i.e.
    # all non-abstract classes (as GraphQL types) and all abstract classes (as GraphQL interfaces).
    RootSchemaQuery = GraphQLObjectType('RootSchemaQuery', OrderedDict([
        (name, GraphQLField(value))
        for name, value in sorted(six.iteritems(graphql_types), key=lambda x: x[0])
        if not isinstance(value, GraphQLUnionType)
    ]))

    schema = GraphQLSchema(RootSchemaQuery, directives=DIRECTIVES)
    return schema, type_equivalence_hints
