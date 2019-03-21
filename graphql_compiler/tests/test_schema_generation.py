# Copyright 2018-present Kensho Technologies, LLC.
import unittest

from ..schema_generation.schema_graph import SchemaGraph
from ..schema_generation.schema_properties import (
    ORIENTDB_BASE_EDGE_CLASS_NAME, ORIENTDB_BASE_VERTEX_CLASS_NAME, PROPERTY_TYPE_EMBEDDED_LIST_ID,
    PROPERTY_TYPE_EMBEDDED_SET_ID, PROPERTY_TYPE_LINK_ID, PROPERTY_TYPE_STRING_ID
)


def get_base_vertex_schema_data():
    return {
        'name': ORIENTDB_BASE_VERTEX_CLASS_NAME,
        'abstract': False,
        'properties': []
    }


def get_base_edge_schema_data():
    return {
        'name': ORIENTDB_BASE_EDGE_CLASS_NAME,
        'abstract': False,
        'properties': []
    }


def get_external_source():
    return {
        'name': 'ExternalSource',
        'abstract': False,
        'properties': []
    }


def get_entity_schema_data():
    return {
        'name': 'Entity',
        'abstract': True,
        'superClasses': [ORIENTDB_BASE_VERTEX_CLASS_NAME],
        'properties': [
            {
                'name': 'name',
                'type': PROPERTY_TYPE_STRING_ID,
            }
        ]
    }


def get_person_schema_data():
    return {
        'name': 'Person',
        'abstract': False,
        'superClasses': ['Entity'],
        'properties': [
            {
                'name': 'alias',
                'type': PROPERTY_TYPE_EMBEDDED_SET_ID,
                'linkedType': PROPERTY_TYPE_STRING_ID,
                'defaultValue': '{}'
            },
        ],
    }


def get_data_point():
    return {
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
    }


def get_person_lives_in_edge_data():
    return {
        'name': 'Person_LivesIn',
        'abstract': False,
        'customFields': {
            'human_name_in': 'Person',
            'human_name_out': 'Location where person lives',
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
    }


def get_location_schema_data():
    return {
        'name': 'Location',
        'abstract': False,
        'superClasses': ['Entity'],
        'properties': [
            {
                'name': 'description',
                'type': PROPERTY_TYPE_STRING_ID,
            }
        ]
    }


class GraphqlSchemaGenerationTests(unittest.TestCase):
    def test_no_superclass(self):
        entity = get_entity_schema_data()
        del entity['superClasses']
        schema_data = [get_base_vertex_schema_data(), entity]
        schema_graph = SchemaGraph(schema_data)
        self.assertEqual({'Entity'}, schema_graph.get_inheritance_set('Entity'))

    def test_parsed_vertex(self):
        schema_data = [get_base_vertex_schema_data(), get_entity_schema_data()]
        schema_graph = SchemaGraph(schema_data)
        self.assertTrue(schema_graph.get_element_by_class_name('Entity').is_vertex)

    def test_parsed_edge(self):
        schema_data = [get_base_vertex_schema_data(), get_entity_schema_data(),
                       get_base_edge_schema_data(), get_person_schema_data(),
                       get_location_schema_data(), get_person_lives_in_edge_data()]
        schema_graph = SchemaGraph(schema_data)
        self.assertTrue(schema_graph.get_element_by_class_name('Person_LivesIn').is_edge)

    def test_parsed_superclasses(self):
        schema_data = [get_external_source()]
        schema_graph = SchemaGraph(schema_data)
        self.assertTrue(schema_graph.get_element_by_class_name('ExternalSource').is_non_graph)

    def test_parsed_superclass(self):
        entity = get_entity_schema_data()
        del entity['superClasses']
        entity['superClass'] = ORIENTDB_BASE_VERTEX_CLASS_NAME
        schema_data = [get_base_vertex_schema_data(), entity]
        schema_graph = SchemaGraph(schema_data)
        self.assertEqual({'Entity', ORIENTDB_BASE_VERTEX_CLASS_NAME},
                         schema_graph.get_inheritance_set('Entity'))

    def test_parse_property(self):
        entity = get_entity_schema_data()
        schema_data = [get_base_vertex_schema_data(), entity]
        schema_graph = SchemaGraph(schema_data)
        name_property = schema_graph.get_element_by_class_name('Entity').properties['name']
        self.assertEqual(name_property.type_id, PROPERTY_TYPE_STRING_ID)

    def test_native_orientdb_collection_property(self):
        schema_data = [get_base_vertex_schema_data(), get_entity_schema_data(),
                       get_person_schema_data()]
        schema_graph = SchemaGraph(schema_data)
        alias_property = schema_graph.get_element_by_class_name('Person').properties['alias']
        self.assertEqual(alias_property.type_id, PROPERTY_TYPE_EMBEDDED_SET_ID)
        self.assertEqual(alias_property.qualifier, PROPERTY_TYPE_STRING_ID)
        self.assertEqual(alias_property.default, set())

    def test_class_collection_property(self):
        schema_data = [get_data_point(), get_external_source()]
        schema_graph = SchemaGraph(schema_data)
        friends_property = schema_graph.get_element_by_class_name('DataPoint').properties[
            'data_source']
        self.assertEqual(friends_property.type_id, PROPERTY_TYPE_EMBEDDED_LIST_ID)
        self.assertEqual(friends_property.qualifier, 'ExternalSource')
        self.assertEqual(friends_property.default, list())

    def test_link_property(self):
        schema_data = [get_base_vertex_schema_data(), get_entity_schema_data(),
                       get_base_edge_schema_data(), get_person_schema_data(),
                       get_location_schema_data(), get_person_lives_in_edge_data()]
        schema_graph = SchemaGraph(schema_data)
        person_lives_in_edge = schema_graph.get_element_by_class_name('Person_LivesIn')
        out_property = person_lives_in_edge.properties['out']
        self.assertEqual(out_property.type_id, PROPERTY_TYPE_LINK_ID)
        self.assertEqual(out_property.qualifier, 'Person')
        in_property = person_lives_in_edge.properties['in']
        self.assertEqual(in_property.type_id, PROPERTY_TYPE_LINK_ID)
        self.assertEqual(in_property.qualifier, 'Location')

    def test_parsed_class_fields(self):
        schema_data = [get_base_vertex_schema_data(), get_entity_schema_data(),
                       get_base_edge_schema_data(), get_person_schema_data(),
                       get_location_schema_data(), get_person_lives_in_edge_data()]
        schema_graph = SchemaGraph(schema_data)
        person_lives_in_edge = schema_graph.get_element_by_class_name('Person_LivesIn')
        self.assertEqual({
            'human_name_in': 'Person',
            'human_name_out': 'Location where person lives'
        }, person_lives_in_edge.class_fields)
