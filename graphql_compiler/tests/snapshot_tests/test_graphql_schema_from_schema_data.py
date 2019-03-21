# Copyright 2018-present Kensho Technologies, LLC.
from graphql.utils.schema_printer import print_schema
from snapshottest import TestCase

from ... import get_graphql_schema_from_orientdb_schema_data
from ... schema_generation.schema_properties import (ORIENTDB_BASE_EDGE_CLASS_NAME,
                                                     ORIENTDB_BASE_VERTEX_CLASS_NAME,
                                                     PROPERTY_TYPE_DECIMAL_ID,
                                                     PROPERTY_TYPE_EMBEDDED_SET_ID,
                                                     PROPERTY_TYPE_LINK_ID,
                                                     PROPERTY_TYPE_STRING_ID)



class GraphQLSchemaGenerationTests(TestCase):

    def test_graphql_schema_generation_from_schema_data_api(self):
        orientdb_schema_data = [
            {
                'name': ORIENTDB_BASE_VERTEX_CLASS_NAME,
                'abstract': False,
                'properties': []
            },
            {
                'name': ORIENTDB_BASE_EDGE_CLASS_NAME,
                'abstract': False,
                'properties': []
            },
            {
                'name': 'Entity',
                'abstract': True,
                'superClasses': [ORIENTDB_BASE_VERTEX_CLASS_NAME],
                'properties': [
                    {
                        'name': 'name',
                        'type': PROPERTY_TYPE_STRING_ID,
                    }
                ]
            },
            {
                'name': 'Person',
                'abstract': False,
                'superClasses': ['Entity'],
                'properties': [
                    {
                        'name': 'net_worth',
                        'type': PROPERTY_TYPE_DECIMAL_ID,
                    },
                    {
                        'name': 'alias',
                        'type': PROPERTY_TYPE_EMBEDDED_SET_ID,
                        'linkedType': PROPERTY_TYPE_STRING_ID,
                        'customFields': "Alias describes the different names a person can have.",
                        'defaultValue': '{}'
                    }
                ],
            },
            {
                'name': 'Person_LivesIn',
                'abstract': False,
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
            },
            {
                'name': 'Location',
                'abstract': False,
                'superClasses': ['Entity'],
                'properties': [
                    {
                        'name': 'description',
                        'type': PROPERTY_TYPE_STRING_ID,
                    }
                ]
            },
        ]
        schema, _ = get_graphql_schema_from_orientdb_schema_data(orientdb_schema_data)
        self.assertMatchSnapshot(print_schema(schema))
