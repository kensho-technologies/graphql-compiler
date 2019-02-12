# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ..macros import perform_macro_expansion
from .test_helpers import compare_graphql, get_schema, get_test_macro_registry


class MacroExpansionTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema = get_schema()
        self.macro_registry = get_test_macro_registry()
        self.type_equivalence_hints = {
            self.schema.get_type('Event'): self.schema.get_type('EventOrBirthEvent'),
        }

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_basic(self):
        query = '''{
            Animal {
                out_Animal_GrandparentOf {
                    name @output(out_name: "grandkid")
                }
            }
        }'''
        args = {}

        expected_query = '''{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        name @output(out_name: "grandkid")
                    }
                }
            }
        }'''
        expected_args = {}

        expanded_query, new_args = perform_macro_expansion(
            self.schema, self.macro_registry, query, args)
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_non_leaf_target_and_field_merging(self):
        query = '''{
            Animal {
                out_Animal_RichYoungerSiblings {
                    net_worth @filter(op_name: "<", value ["net_worth_upper_bound"])
                              @output(out_name: "sibling_net_worth")
                }
            }
        }'''
        args = {}

        expected_query = '''{
            TODO(bojanserafimov): Add correct answer
        }'''
        expected_args = {}

        expanded_query, new_args = perform_macro_expansion(
            self.schema, self.macro_registry, query, args)
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_source_merging(self):
        query = '''{
            Animal {
                net_worth @filter(op_name: "<", value ["net_worth_upper_bound"])
                          @output(out_name: "net_worth")
                out_Animal_RichYoungerSiblings {
                    uuid
                }
            }
        }'''
        args = {}

        expected_query = '''{
            TODO(bojanserafimov): Add correct answer
        }'''
        expected_args = {}

        expanded_query, new_args = perform_macro_expansion(
            self.schema, self.macro_registry, query, args)
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_target_coercion_1(self):
        query = '''{
            Animal {
                out_Animal_AvailableFood {
                   ... on Food {
                       @output(out_name: "food")
                   }
                }
            }
        }'''
        args = {}

        expected_query = '''{
            TODO(bojanserafimov): Add correct answer
        }'''
        expected_args = {}

        expanded_query, new_args = perform_macro_expansion(
            self.schema, self.macro_registry, query, args)
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_target_coercion_2(self):
        query = '''{
            Animal {
                out_Animal_NearbyEvents {
                   ... on Event {
                       @output(out_name: "event")
                   }
                }
            }
        }'''
        args = {}

        expected_query = '''{
            TODO(bojanserafimov): Add correct answer
        }'''
        expected_args = {}

        expanded_query, new_args = perform_macro_expansion(
            self.schema, self.macro_registry, query, args)
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_target_coercion_3(self):
        query = '''{
            Animal {
                out_Animal_NearbyEvents {
                   ... on BirthEvent {
                       @output(out_name: "event")
                   }
                }
            }
        }'''
        args = {}

        expected_query = '''{
            TODO(bojanserafimov): Add correct answer
        }'''
        expected_args = {}

        expanded_query, new_args = perform_macro_expansion(
            self.schema, self.macro_registry, query, args)
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_target_coercion_4(self):
        query = '''{
            Animal {
                out_Animal_NearbyEntities {
                   ... on Event {
                       @output(out_name: "event")
                   }
                }
            }
        }'''
        args = {}

        expected_query = '''{
            TODO(bojanserafimov): Add correct answer
        }'''
        expected_args = {}

        expanded_query, new_args = perform_macro_expansion(
            self.schema, self.macro_registry, query, args)
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_target_coercion_5(self):
        query = '''{
            Animal {
                out_Animal_NearbyEntities {
                   ... on Animal {
                       @output(out_name: "animal")
                   }
                }
            }
        }'''
        args = {}

        expected_query = '''{
            TODO(bojanserafimov): Add correct answer
        }'''
        expected_args = {}

        expanded_query, new_args = perform_macro_expansion(
            self.schema, self.macro_registry, query, args)
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_arguments(self):
        query = '''{
            Location {
                @filter(op_name: "=", value: ["$location"])
                out_Location_Orpans {
                    @output(out_name: "name")
                }
            }
        }'''
        args = {
            'location': 'Europe',
        }

        expected_query = '''{
            TODO(bojanserafimov): Add correct answer
        }'''
        expected_args = {}  # TODO(bojanserafimov): Add correct answer

        expanded_query, new_args = perform_macro_expansion(
            self.schema, self.macro_registry, query, args)
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)
