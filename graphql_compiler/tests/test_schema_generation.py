# Copyright 2018-present Kensho Technologies, LLC.
import unittest

from frozendict import frozendict
from graphql.type import GraphQLList, GraphQLString
import six

from graphql_compiler import get_graphql_schema_from_orientdb_schema_data

from ..schema_generation.schema_graph import SchemaGraph
from ..schema_generation.schema_properties import (
    ORIENTDB_BASE_EDGE_CLASS_NAME, ORIENTDB_BASE_VERTEX_CLASS_NAME, PROPERTY_TYPE_EMBEDDED_LIST_ID,
    PROPERTY_TYPE_EMBEDDED_SET_ID, PROPERTY_TYPE_LINK_ID, PROPERTY_TYPE_STRING_ID
)


BASE_VERTEX_SCHEMA_DATA = frozendict({
    'name': ORIENTDB_BASE_VERTEX_CLASS_NAME,
    'abstract': False,
    'properties': []
})

BASE_EDGE_SCHEMA_DATA = frozendict({
    'name': ORIENTDB_BASE_EDGE_CLASS_NAME,
    'abstract': False,
    'properties': []
})

EXTERNAL_SOURCE_SCHEMA_DATA = frozendict({
    'name': 'ExternalSource',
    'abstract': False,
    'properties': []
})

ENTITY_SCHEMA_DATA = frozendict({
    'name': 'Entity',
    'abstract': True,
    'superClasses': [ORIENTDB_BASE_VERTEX_CLASS_NAME],
    'properties': [
        {
            'name': 'name',
            'type': PROPERTY_TYPE_STRING_ID,
        }
    ]
})

PERSON_SCHEMA_DATA = frozendict({
    'name': 'Person',
    'abstract': False,
    'superClass': 'Entity',
    'properties': [
        {
            'name': 'alias',
            'type': PROPERTY_TYPE_EMBEDDED_SET_ID,
            'linkedType': PROPERTY_TYPE_STRING_ID,
            'defaultValue': '{}'
        },
    ],
})

BABY_SCHEMA_DATA = frozendict({
    'name': 'Baby',
    'abstract': False,
    'superClass': 'Person',
    'properties': [],
})


DATA_POINT_SCHEMA_DATA = frozendict({
    'name': 'DataPoint',
    'abstract': True,
    'properties': [
        {
            'name': 'data_source',
            'type': PROPERTY_TYPE_EMBEDDED_LIST_ID,
            'linkedClass': 'ExternalSource',
            'defaultValue': '[]'
        }

    ]
})

PERSON_LIVES_IN_EDGE_SCHEMA_DATA = frozendict({
    'name': 'Person_LivesIn',
    'abstract': False,
    'customFields': {
        'human_name_in': 'Location where person lives',
        'human_name_out': 'Person',
    },
    'properties': [
        {
            'name': 'in',
            'type': PROPERTY_TYPE_LINK_ID,
            'linkedClass': 'Location',
        },
        {
            'name': 'out',
            'type': PROPERTY_TYPE_LINK_ID,
            'linkedClass': 'Person',
        }
    ],
    'superClass': ORIENTDB_BASE_EDGE_CLASS_NAME
})

LOCATION_SCHEMA_DATA = frozendict({
    'name': 'Location',
    'abstract': False,
    'superClasses': ['Entity'],
    'properties': [
        {
            'name': 'description',
            'type': PROPERTY_TYPE_STRING_ID,
        }
    ]
})


class GraphqlSchemaGenerationTests(unittest.TestCase):
    def test_parsed_vertex(self):
        schema_data = [
            BASE_VERTEX_SCHEMA_DATA,
            ENTITY_SCHEMA_DATA,
        ]
        schema_graph = SchemaGraph(schema_data)
        self.assertTrue(schema_graph.get_element_by_class_name('Entity').is_vertex)

    def test_parsed_edge(self):
        schema_data = [
            BASE_EDGE_SCHEMA_DATA,
            BASE_VERTEX_SCHEMA_DATA,
            ENTITY_SCHEMA_DATA,
            LOCATION_SCHEMA_DATA,
            PERSON_LIVES_IN_EDGE_SCHEMA_DATA,
            PERSON_SCHEMA_DATA,
        ]
        schema_graph = SchemaGraph(schema_data)
        self.assertTrue(schema_graph.get_element_by_class_name('Person_LivesIn').is_edge)

    def test_parsed_non_graph_class(self):
        schema_data = [EXTERNAL_SOURCE_SCHEMA_DATA]
        schema_graph = SchemaGraph(schema_data)
        self.assertTrue(schema_graph.get_element_by_class_name('ExternalSource').is_non_graph)

    def test_no_superclass(self):
        schema_data = [BASE_VERTEX_SCHEMA_DATA]
        schema_graph = SchemaGraph(schema_data)
        self.assertEqual({ORIENTDB_BASE_VERTEX_CLASS_NAME},
                         schema_graph.get_inheritance_set(ORIENTDB_BASE_VERTEX_CLASS_NAME))

    def test_parsed_superclass_field(self):
        schema_data = [
            BASE_EDGE_SCHEMA_DATA,
            BASE_VERTEX_SCHEMA_DATA,
            ENTITY_SCHEMA_DATA,
            LOCATION_SCHEMA_DATA,
            PERSON_LIVES_IN_EDGE_SCHEMA_DATA,
            PERSON_SCHEMA_DATA,
        ]
        schema_graph = SchemaGraph(schema_data)
        self.assertEqual({'Person_LivesIn', ORIENTDB_BASE_EDGE_CLASS_NAME},
                         schema_graph.get_inheritance_set('Person_LivesIn'))

    def test_parsed_superclasses_field(self):
        schema_data = [
            BASE_VERTEX_SCHEMA_DATA,
            ENTITY_SCHEMA_DATA,
        ]
        schema_graph = SchemaGraph(schema_data)
        self.assertEqual({'Entity', ORIENTDB_BASE_VERTEX_CLASS_NAME},
                         schema_graph.get_inheritance_set('Entity'))

    def test_parse_property(self):
        schema_data = [
            BASE_VERTEX_SCHEMA_DATA,
            ENTITY_SCHEMA_DATA,
        ]
        schema_graph = SchemaGraph(schema_data)
        name_property = schema_graph.get_element_by_class_name('Entity').properties['name']
        self.assertEqual(name_property.type_id, PROPERTY_TYPE_STRING_ID)

    def test_native_orientdb_collection_property(self):
        schema_data = [
            BASE_VERTEX_SCHEMA_DATA,
            ENTITY_SCHEMA_DATA,
            PERSON_SCHEMA_DATA,
        ]
        schema_graph = SchemaGraph(schema_data)
        alias_property = schema_graph.get_element_by_class_name('Person').properties['alias']
        self.assertEqual(alias_property.type_id, PROPERTY_TYPE_EMBEDDED_SET_ID)
        self.assertEqual(alias_property.qualifier, PROPERTY_TYPE_STRING_ID)
        self.assertEqual(alias_property.default, set())

    def test_class_collection_property(self):
        schema_data = [
            DATA_POINT_SCHEMA_DATA,
            EXTERNAL_SOURCE_SCHEMA_DATA,
        ]
        schema_graph = SchemaGraph(schema_data)
        friends_property = schema_graph.get_element_by_class_name('DataPoint').properties[
            'data_source']
        self.assertEqual(friends_property.type_id, PROPERTY_TYPE_EMBEDDED_LIST_ID)
        self.assertEqual(friends_property.qualifier, 'ExternalSource')
        self.assertEqual(friends_property.default, list())

    def test_link_property(self):
        schema_data = [
            BASE_EDGE_SCHEMA_DATA,
            BASE_VERTEX_SCHEMA_DATA,
            ENTITY_SCHEMA_DATA,
            LOCATION_SCHEMA_DATA,
            PERSON_LIVES_IN_EDGE_SCHEMA_DATA,
            PERSON_SCHEMA_DATA,
        ]
        schema_graph = SchemaGraph(schema_data)
        person_lives_in_edge = schema_graph.get_element_by_class_name('Person_LivesIn')
        in_property = person_lives_in_edge.properties['in']
        self.assertEqual(in_property.type_id, PROPERTY_TYPE_LINK_ID)
        self.assertEqual(in_property.qualifier, 'Location')
        out_property = person_lives_in_edge.properties['out']
        self.assertEqual(out_property.type_id, PROPERTY_TYPE_LINK_ID)
        self.assertEqual(out_property.qualifier, 'Person')

    def test_parsed_class_fields(self):
        schema_data = [
            BASE_EDGE_SCHEMA_DATA,
            BASE_VERTEX_SCHEMA_DATA,
            ENTITY_SCHEMA_DATA,
            LOCATION_SCHEMA_DATA,
            PERSON_LIVES_IN_EDGE_SCHEMA_DATA,
            PERSON_SCHEMA_DATA,
        ]
        schema_graph = SchemaGraph(schema_data)
        person_lives_in_edge = schema_graph.get_element_by_class_name('Person_LivesIn')
        self.assertEqual(PERSON_LIVES_IN_EDGE_SCHEMA_DATA['customFields'],
                         person_lives_in_edge.class_fields)

    def test_type_equivalence_dicts(self):
        schema_data = [
            BASE_EDGE_SCHEMA_DATA,
            BASE_VERTEX_SCHEMA_DATA,
            BABY_SCHEMA_DATA,
            ENTITY_SCHEMA_DATA,
            LOCATION_SCHEMA_DATA,
            PERSON_LIVES_IN_EDGE_SCHEMA_DATA,
            PERSON_SCHEMA_DATA,
        ]
        schema, type_equivalence_dicts = get_graphql_schema_from_orientdb_schema_data(schema_data)
        person, person_baby_union = next(six.iteritems(type_equivalence_dicts))
        baby = schema.get_type('Baby')
        location = schema.get_type('Location')

        # Assert that there is exactly 1 type equivalence
        self.assertEqual(1, len(type_equivalence_dicts))

        # Assert that the Person class is part of the schema.
        self.assertEqual(person, schema.get_type('Person'))

        # Assert that the union consists of the Baby and Person classes
        self.assertEqual(set(person_baby_union.types), {baby, person})

        # Assert that arbitrarily chosen inherited property is still correctly inherited
        self.assertTrue(baby.fields['name'].type.is_same_type(GraphQLString))

        # Assert that arbitrarily chosen edge is correctly represented on all ends
        location_list_type = GraphQLList(location)
        union_list_type = GraphQLList(person_baby_union)
        self.assertTrue(person.fields['out_Person_LivesIn'].type.is_same_type(location_list_type))
        self.assertTrue(baby.fields['out_Person_LivesIn'].type.is_same_type(location_list_type))
        self.assertTrue(location.fields['in_Person_LivesIn'].type.is_same_type(union_list_type))
