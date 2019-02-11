# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ..exceptions import GraphQLCompilationError
from ..macros import create_macro_registry, perform_macro_expansion, register_macro_edge
from .test_helpers import compare_graphql, get_schema


def get_test_macro_registry():
    schema = get_schema()
    macro_registry = create_macro_registry()
    type_equivalence_hints = {
        schema.get_type('Event'): schema.get_type('EventOrBirthEvent'),
    }

    valid_macros = [
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }''', {}),
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_RichSiblings") {
                in_Animal_ParentOf {
                    net_worth @tag(tag_name: "parent_net_worth")
                    out_Animal_ParentOf @macro_edge_target {
                        net_worth @filter(op_name: ">", value: ["parent_net_worth"])
                        out_Animal_BornAt {
                            event_date @filter(op_name: "<", value: ["%birthday"])
                        }
                    }
                }
            }
        }''', {}),
        ('''{
            Location @macro_edge_definition(name: "out_Location_Orphans") {
                in_Animal_LivesIn @macro_edge_target {
                    in_Animal_ParentOf @filter(op_name: "has_edge_degree", value: ["$num_parents"])
                                       @optional {
                        uuid
                    }
                }
            }
        }''', {
            'num_parents': 0,
        }),
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_RichYoungerSiblings") {
                net_worth @tag(tag_name: "net_worth")
                out_Animal_BornAt {
                    event_date @tag(tag_name: "birthday")
                }
                in_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        net_worth @filter(op_name: ">", value: ["net_worth"])
                        out_Animal_BornAt {
                            event_date @filter(op_name: "<", value: ["%birthday"])
                        }
                    }
                }
            }
        }''', {}),
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_AvailableFood") {
                out_Animal_LivesIn {
                    in_Entity_Related {
                        ... on Food @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }''', {}),
        ('''{
            Animal @macro_edge_definition(name: "invalid_out_Animal_AvailableFood") {
                out_Animal_LivesIn {
                    in_Entity_Related @macro_edge_target {
                        ... on Food {
                            uuid
                        }
                    }
                }
            }
        }''', {}),
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_NearbyEvents") {
                out_Animal_LivesIn {
                    in_Entity_Related @macro_edge_target {
                        ... on Event {
                            uuid
                        }
                    }
                }
            }
        }''', {}),
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_NearbyEntities") {
                out_Animal_LivesIn {
                    in_Entity_Related {
                        ... on Entity @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }''', {}),
    ]

    for graphql, args in valid_macros:
        register_macro_edge(macro_registry, schema, graphql, args, type_equivalence_hints)
    return macro_registry


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

    # TODO(bojanserafimov): Move test_macro_expansion_errors.py to test_macro_validation.py
    # Move this function and all the others to test_macro_expansion_errors.py
    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_duplicate_edge_traversal(self):
        query = '''{
            Animal {
                out_Animal_BornAt {
                    uuid
                }
                out_Animal_RichYoungerSiblings {
                    uuid
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.schema, self.macro_registry, query, args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_target_coercion_invalid_1(self):
        query = '''{
            Animal {
                out_Animal_AvailableFood {
                   ... on Species {
                       @output(out_name: "species")
                   }
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.schema, self.macro_registry, query, args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_invalid_coercion_2(self):
        query = '''{
            Animal {
                out_Animal_NearbyEvents {
                   ... on Entity {
                       @output(out_name: "event")
                   }
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.schema, self.macro_registry, query, args)

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

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_nonexistent(self):
        query = '''{
            Animal {
                out_Animal_GrandparentOf {
                    @output(out_name: "grandkid")
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.schema, self.macro_registry, query, args)
