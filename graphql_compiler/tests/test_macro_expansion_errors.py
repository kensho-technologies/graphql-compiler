# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ..exceptions import GraphQLCompilationError, GraphQLValidationError
from ..macros import perform_macro_expansion
from .test_helpers import get_test_macro_registry


class MacroExpansionTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.macro_registry = get_test_macro_registry()

    def test_macro_edge_duplicate_edge_traversal(self):
        query = '''{
            Animal {
                out_Animal_BornAt {
                    name @output(out_name: "name")
                }
                out_Animal_RichYoungerSiblings {
                    uuid
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.macro_registry, query, args)

    def test_macro_edge_duplicate_macro_traversal(self):
        query = '''{
            Animal {
                out_Animal_RichYoungerSiblings {
                    name @output(out_name: "name")
                }
                out_Animal_RichYoungerSiblings {
                    uuid
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.macro_registry, query, args)

    def test_macro_edge_target_coercion_invalid_1(self):
        query = '''{
            Animal {
                out_Animal_RelatedFood {
                   ... on Species {
                       name @output(out_name: "species")
                   }
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLValidationError):
            perform_macro_expansion(self.macro_registry, query, args)

    def test_macro_edge_invalid_coercion_2(self):
        query = '''{
            Animal {
                out_Animal_RelatedEvent {
                   ... on Entity {
                       name @output(out_name: "event")
                   }
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLValidationError):
            perform_macro_expansion(self.macro_registry, query, args)

    def test_macro_edge_nonexistent(self):
        query = '''{
            Animal {
                out_Garbage_ThisMacroIsNotInTheRegistry {
                    name @output(out_name: "grandkid")
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLValidationError):
            perform_macro_expansion(self.macro_registry, query, args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_target_on_union_type(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_RelatedEvent") {
                in_Entity_Related @macro_edge_target {
                    ... on Event {
                        uuid
                    }
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.macro_registry, query, args)

    def test_incorrect_schema_usage(self):
        # Test with fields that don't exist in the schema
        query = '''{
            Animal {
                out_Animal_GrandparentOf {
                    field_not_in_schema @output(out_name: "grandkid")
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLValidationError):
            perform_macro_expansion(self.macro_registry, query, args)
