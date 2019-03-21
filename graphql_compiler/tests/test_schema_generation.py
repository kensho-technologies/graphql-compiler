# Copyright 2018-present Kensho Technologies, LLC.
from graphql.utils.schema_printer import print_schema
import unittest

from ..schema_generation.schema_graph import SchemaGraph
from ..schema_generation.schema_properties import (
    ORIENTDB_BASE_EDGE_CLASS_NAME, ORIENTDB_BASE_VERTEX_CLASS_NAME,
)

class GraphqlSchemaGenerationTests(unittest.TestCase):

    def setUp(self):
        self.base_schema_data = [
            {
                'name': ORIENTDB_BASE_VERTEX_CLASS_NAME,
                'abstract': False,
                'properties': []
            },
            {
                'name': ORIENTDB_BASE_EDGE_CLASS_NAME,
                'abstract': False,
                'properties': []
            }
        ]
        self.entity_name = 'Entity'

    def test_no_superclass(self):
        schema_data = self.base_schema_data+[{
            'name': self.entity_name,
            'abstract': True,
            'properties': []
        }]
        schema_graph = SchemaGraph(schema_data)
        self.assertEquals(set(),
                          schema_graph.get_inheritance_set(self.entity_name))

    def test_parsed_superclasses(self):
        schema_data = self.base_schema_data+[{
            'name': self.entity_name,
            'abstract': True,
            'superClasses': [ORIENTDB_BASE_VERTEX_CLASS_NAME],
            'properties': []
        }]
        schema_graph = SchemaGraph(schema_data)
        self.assertEquals(set(ORIENTDB_BASE_EDGE_CLASS_NAME),
                          schema_graph.get_inheritance_set(self.entity_name))

    def test_parsed_superclass(self):
        schema_data = self.base_schema_data+[{
            'name': self.entity_name,
            'abstract': True,
            'superClasses': [ORIENTDB_BASE_VERTEX_CLASS_NAME],
            'properties': []
        }]
        schema_graph = SchemaGraph(schema_data)
        self.assertEquals(set(ORIENTDB_BASE_EDGE_CLASS_NAME),
                          schema_graph.get_inheritance_set(self.entity_name))
