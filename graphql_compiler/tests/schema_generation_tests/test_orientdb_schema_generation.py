# Copyright 2018-present Kensho Technologies, LLC.
import unittest

from graphql.type import GraphQLInterfaceType, GraphQLList, GraphQLObjectType, GraphQLString
import pytest
import six

from ...global_utils import is_same_type
from ...schema_generation.graphql_schema import _get_union_type_name
from ...schema_generation.orientdb import get_graphql_schema_from_orientdb_schema_data
from ...schema_generation.orientdb.schema_graph_builder import get_orientdb_schema_graph
from ...schema_generation.orientdb.schema_properties import (
    ORIENTDB_BASE_EDGE_CLASS_NAME,
    ORIENTDB_BASE_VERTEX_CLASS_NAME,
    PROPERTY_TYPE_EMBEDDED_LIST_ID,
    PROPERTY_TYPE_EMBEDDED_SET_ID,
    PROPERTY_TYPE_LINK_ID,
    PROPERTY_TYPE_STRING_ID,
)


BASE_VERTEX = {"name": ORIENTDB_BASE_VERTEX_CLASS_NAME, "abstract": False, "properties": []}

BASE_EDGE = {"name": ORIENTDB_BASE_EDGE_CLASS_NAME, "abstract": False, "properties": []}

EXTERNAL_SOURCE = {"name": "ExternalSource", "abstract": False, "properties": []}

ENTITY = {
    "name": "Entity",
    "abstract": True,
    "superClasses": [ORIENTDB_BASE_VERTEX_CLASS_NAME],
    "properties": [
        {
            "name": "name",
            "type": PROPERTY_TYPE_STRING_ID,
        }
    ],
}

PERSON = {
    "name": "Person",
    "abstract": False,
    "superClass": "Entity",
    "properties": [
        {
            "name": "alias",
            "type": PROPERTY_TYPE_EMBEDDED_SET_ID,
            "linkedType": PROPERTY_TYPE_STRING_ID,
            "defaultValue": "{}",
        },
    ],
}

BABY = {"name": "Baby", "abstract": False, "superClass": "Person", "properties": []}


DATA_POINT = {
    "name": "DataPoint",
    "abstract": True,
    "properties": [
        {
            "name": "data_source",
            "type": PROPERTY_TYPE_EMBEDDED_LIST_ID,
            "linkedClass": "ExternalSource",
            "defaultValue": "[]",
        }
    ],
    "superClass": "V",
}

PERSON_LIVES_IN_EDGE = {
    "name": "Person_LivesIn",
    "abstract": False,
    "customFields": {
        "human_name_in": "Location where person lives",
        "human_name_out": "Person",
    },
    "properties": [
        {
            "name": "in",
            "type": PROPERTY_TYPE_LINK_ID,
            "linkedClass": "Location",
        },
        {
            "name": "out",
            "type": PROPERTY_TYPE_LINK_ID,
            "linkedClass": "Person",
        },
    ],
    "superClass": ORIENTDB_BASE_EDGE_CLASS_NAME,
}


BABY_LIVES_IN_EDGE = {
    "name": "Baby_LivesIn",
    "abstract": False,
    "properties": [
        {
            "name": "in",
            "type": PROPERTY_TYPE_LINK_ID,
            "linkedClass": "Location",
        },
        {
            "name": "out",
            "type": PROPERTY_TYPE_LINK_ID,
            "linkedClass": "Baby",
        },
    ],
    "superClass": "Person_LivesIn",
}

LOCATION = {
    "name": "Location",
    "abstract": False,
    "superClasses": ["Entity"],
    "properties": [
        {
            "name": "description",
            "type": PROPERTY_TYPE_STRING_ID,
        }
    ],
}

CLASS_WITH_INVALID_PROPERTY_NAME = {
    "name": "ClassWithInvalidPropertyName",
    "abstract": False,
    "superClasses": [ORIENTDB_BASE_VERTEX_CLASS_NAME],
    "properties": [{"name": "$invalid_name", "type": PROPERTY_TYPE_STRING_ID}],
}

# We add arbitrary properties to the following classes to make the data as "real" as possible.
ABSTRACT_NON_GRAPH_CLASS_WITH_NON_VERTEX_CONCRETE_SUBCLASS = {
    "name": "AbstractNonGraphClassWithNonVertexConcreteSubclass",
    "abstract": True,
    "superClasses": [],
    "properties": [
        {
            "name": "arbitrary_property_1",
            "type": PROPERTY_TYPE_STRING_ID,
        }
    ],
}

ABSTRACT_NON_GRAPH_CLASS_WITH_ONLY_VERTEX_CONCRETE_SUBCLASSES = {
    "name": "AbstractNonGraphClassWithOnlyVertexConcreteSubclasses",
    "abstract": True,
    "superClasses": [],
    "properties": [
        {
            "name": "arbitrary_property_2",
            "type": PROPERTY_TYPE_STRING_ID,
        }
    ],
}

CONCRETE_NON_GRAPH_CLASS_WITH_NON_VERTEX_CONCRETE_SUBCLASS = {
    "name": "ConcreteNonGraphClassWithNonVertexConcreteSubclass",
    "abstract": False,
    "superClasses": [],
    "properties": [
        {
            "name": "arbitrary_property_3",
            "type": PROPERTY_TYPE_STRING_ID,
        }
    ],
}

CONCRETE_NON_GRAPH_CLASS_WITH_ONLY_VERTEX_CONCRETE_SUBCLASSES = {
    "name": "ConcreteNonGraphClassWithOnlyVertexConcreteSubclasses",
    "abstract": False,
    "superClasses": [],
    "properties": [
        {
            "name": "arbitrary_property_4",
            "type": PROPERTY_TYPE_STRING_ID,
        }
    ],
}

ABSTRACT_NON_GRAPH_CLASS_WITH_NO_SUBCLASSES = {
    "name": "AbstractNonGraphClassWithNoSubclasses",
    "abstract": True,
    "superClasses": [],
    "properties": [
        {
            "name": "arbitrary_property_5",
            "type": PROPERTY_TYPE_STRING_ID,
        }
    ],
}

ARBITRARY_CONCRETE_VERTEX_CLASS = {
    "name": "ArbitraryConcreteVertexClass",
    "abstract": False,
    "superClasses": [
        ORIENTDB_BASE_VERTEX_CLASS_NAME,
        ABSTRACT_NON_GRAPH_CLASS_WITH_NON_VERTEX_CONCRETE_SUBCLASS["name"],
        ABSTRACT_NON_GRAPH_CLASS_WITH_ONLY_VERTEX_CONCRETE_SUBCLASSES["name"],
        CONCRETE_NON_GRAPH_CLASS_WITH_NON_VERTEX_CONCRETE_SUBCLASS["name"],
        CONCRETE_NON_GRAPH_CLASS_WITH_ONLY_VERTEX_CONCRETE_SUBCLASSES["name"],
    ],
    "properties": [
        {
            "name": "arbitrary_property_6",
            "type": PROPERTY_TYPE_STRING_ID,
        }
    ],
}

ARBITRARY_CONCRETE_NON_GRAPH_CLASS = {
    "name": "ArbitraryConcreteNonGraphClass",
    "abstract": False,
    "superClasses": [
        ABSTRACT_NON_GRAPH_CLASS_WITH_NON_VERTEX_CONCRETE_SUBCLASS["name"],
        CONCRETE_NON_GRAPH_CLASS_WITH_NON_VERTEX_CONCRETE_SUBCLASS["name"],
    ],
    "properties": [
        {
            "name": "arbitrary_property_7",
            "type": PROPERTY_TYPE_STRING_ID,
        }
    ],
}


class GraphqlSchemaGenerationTests(unittest.TestCase):
    def test_parsed_vertex(self) -> None:
        schema_data = [
            BASE_VERTEX,
            ENTITY,
        ]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        self.assertTrue(schema_graph.get_element_by_class_name("Entity").is_vertex)

    def test_parsed_edge(self) -> None:
        schema_data = [
            BASE_EDGE,
            BASE_VERTEX,
            ENTITY,
            LOCATION,
            PERSON_LIVES_IN_EDGE,
            PERSON,
        ]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        self.assertTrue(schema_graph.get_element_by_class_name("Person_LivesIn").is_edge)

    def test_parsed_non_graph_class(self) -> None:
        schema_data = [EXTERNAL_SOURCE]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        self.assertTrue(schema_graph.get_element_by_class_name("ExternalSource").is_non_graph)

    def test_no_superclass(self) -> None:
        schema_data = [BASE_VERTEX]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        self.assertEqual(
            {ORIENTDB_BASE_VERTEX_CLASS_NAME},
            schema_graph.get_superclass_set(ORIENTDB_BASE_VERTEX_CLASS_NAME),
        )

    def test_parsed_superclass_field(self) -> None:
        schema_data = [
            BASE_EDGE,
            BASE_VERTEX,
            ENTITY,
            LOCATION,
            PERSON_LIVES_IN_EDGE,
            PERSON,
        ]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        self.assertEqual(
            {"Person_LivesIn", ORIENTDB_BASE_EDGE_CLASS_NAME},
            schema_graph.get_superclass_set("Person_LivesIn"),
        )

    def test_parsed_superclasses_field(self) -> None:
        schema_data = [
            BASE_VERTEX,
            ENTITY,
        ]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        self.assertEqual(
            {"Entity", ORIENTDB_BASE_VERTEX_CLASS_NAME}, schema_graph.get_superclass_set("Entity")
        )

    def test_parsed_property(self) -> None:
        schema_data = [
            BASE_VERTEX,
            ENTITY,
        ]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        name_property = schema_graph.get_element_by_class_name("Entity").properties["name"]
        self.assertTrue(is_same_type(name_property.type, GraphQLString))

    def test_native_orientdb_collection_property(self) -> None:
        schema_data = [
            BASE_VERTEX,
            ENTITY,
            PERSON,
        ]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        alias_property = schema_graph.get_element_by_class_name("Person").properties["alias"]
        self.assertTrue(is_same_type(alias_property.type, GraphQLList(GraphQLString)))
        self.assertEqual(alias_property.default, set())

    def test_class_collection_property(self) -> None:
        schema_data = [
            BASE_VERTEX,
            DATA_POINT,
            EXTERNAL_SOURCE,
        ]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        friends_property = schema_graph.get_element_by_class_name("DataPoint").properties[
            "data_source"
        ]
        self.assertTrue(
            is_same_type(
                friends_property.type, GraphQLList(GraphQLObjectType("ExternalSource", {}))
            )
        )
        self.assertEqual(friends_property.default, list())

    def test_link_parsing(self) -> None:
        schema_data = [
            BASE_EDGE,
            BASE_VERTEX,
            ENTITY,
            LOCATION,
            PERSON_LIVES_IN_EDGE,
            PERSON,
        ]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        person_lives_in_edge = schema_graph.get_element_by_class_name("Person_LivesIn")
        self.assertEqual(person_lives_in_edge.base_in_connection, "Person")
        self.assertEqual(person_lives_in_edge.base_out_connection, "Location")

    def test_parsed_class_fields(self) -> None:
        schema_data = [
            BASE_EDGE,
            BASE_VERTEX,
            ENTITY,
            LOCATION,
            PERSON_LIVES_IN_EDGE,
            PERSON,
        ]
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        person_lives_in_edge = schema_graph.get_element_by_class_name("Person_LivesIn")
        self.assertEqual(PERSON_LIVES_IN_EDGE["customFields"], person_lives_in_edge.class_fields)

    def test_type_equivalence_dicts(self) -> None:
        schema_data = [
            BASE_EDGE,
            BASE_VERTEX,
            BABY,
            ENTITY,
            LOCATION,
            PERSON_LIVES_IN_EDGE,
            PERSON,
        ]
        schema, type_equivalence_dicts = get_graphql_schema_from_orientdb_schema_data(schema_data)

        # Self-consistency check
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        person_subclass_set = schema_graph.get_subclass_set("Person")
        self.assertIsNotNone(schema.get_type(_get_union_type_name(person_subclass_set)))

        person, person_baby_union = next(six.iteritems(type_equivalence_dicts))
        baby = schema.get_type("Baby")
        location = schema.get_type("Location")

        # Assert that there is exactly 1 type equivalence
        self.assertEqual(1, len(type_equivalence_dicts))

        # Assert that the Person class is part of the schema.
        self.assertEqual(person, schema.get_type("Person"))

        # Assert that the union consists of the Baby and Person classes
        self.assertEqual(set(person_baby_union.types), {baby, person})

        # Assert that arbitrarily chosen inherited property is still correctly inherited
        self.assertTrue(is_same_type(baby.fields["name"].type, GraphQLString))

        # Assert that arbitrarily chosen edge is correctly represented on all ends
        location_list_type = GraphQLList(location)
        union_list_type = GraphQLList(person_baby_union)
        self.assertTrue(is_same_type(person.fields["out_Person_LivesIn"].type, location_list_type))
        self.assertTrue(is_same_type(baby.fields["out_Person_LivesIn"].type, location_list_type))
        self.assertTrue(is_same_type(location.fields["in_Person_LivesIn"].type, union_list_type))

    def test_filter_type_equivalences_with_no_edges(self) -> None:
        schema_data = [
            BASE_VERTEX,
            BABY,
            ENTITY,
            PERSON,
        ]
        schema, type_equivalence_dicts = get_graphql_schema_from_orientdb_schema_data(schema_data)
        # Since there is not ingoing edge to Person, we filter the Person_Baby union
        # from the type equivalence dict since it is not discoverable by the GraphQL Schema.
        self.assertEqual(0, len(type_equivalence_dicts))
        # Self-consistency check
        schema_graph = get_orientdb_schema_graph(schema_data, [])
        person_subclass_set = schema_graph.get_subclass_set("Person")
        self.assertIsNone(schema.get_type(_get_union_type_name(person_subclass_set)))

    def test_edge_inheritance(self) -> None:
        schema_data = [
            BASE_EDGE,
            BABY_LIVES_IN_EDGE,
            BASE_VERTEX,
            BABY,
            ENTITY,
            LOCATION,
            PERSON_LIVES_IN_EDGE,
            PERSON,
        ]

        schema_graph = get_orientdb_schema_graph(schema_data, [])
        baby_lives_in_edge = schema_graph.get_element_by_class_name("Baby_LivesIn")
        self.assertEqual("Baby", baby_lives_in_edge.base_in_connection)

    def test_ignore_properties_with_invalid_name_warning(self) -> None:
        schema_data = [
            BASE_VERTEX,
            CLASS_WITH_INVALID_PROPERTY_NAME,
        ]

        with pytest.warns(UserWarning):
            get_graphql_schema_from_orientdb_schema_data(schema_data)

    def test_include_non_graph_classes_in_graphql_schema(self) -> None:
        non_graph_classes_to_include = [
            ABSTRACT_NON_GRAPH_CLASS_WITH_ONLY_VERTEX_CONCRETE_SUBCLASSES,
        ]

        non_graph_classes_to_ignore = [
            ABSTRACT_NON_GRAPH_CLASS_WITH_NON_VERTEX_CONCRETE_SUBCLASS,
            ABSTRACT_NON_GRAPH_CLASS_WITH_NO_SUBCLASSES,
            CONCRETE_NON_GRAPH_CLASS_WITH_ONLY_VERTEX_CONCRETE_SUBCLASSES,
            CONCRETE_NON_GRAPH_CLASS_WITH_NON_VERTEX_CONCRETE_SUBCLASS,
            ARBITRARY_CONCRETE_NON_GRAPH_CLASS,
        ]

        vertex_clases = [
            ARBITRARY_CONCRETE_VERTEX_CLASS,
            BASE_VERTEX,
        ]

        schema_data = non_graph_classes_to_include + non_graph_classes_to_ignore + vertex_clases

        names_of_non_graph_classes_to_ignore = {
            non_graph_class["name"] for non_graph_class in non_graph_classes_to_ignore
        }

        graphql_schema, _ = get_graphql_schema_from_orientdb_schema_data(schema_data)
        for name in six.iterkeys(graphql_schema.type_map):
            self.assertNotIn(name, names_of_non_graph_classes_to_ignore)

        non_graph_class_type = graphql_schema.get_type(
            ABSTRACT_NON_GRAPH_CLASS_WITH_ONLY_VERTEX_CONCRETE_SUBCLASSES["name"]
        )
        self.assertTrue(isinstance(non_graph_class_type, GraphQLInterfaceType))
