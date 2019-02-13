# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ..exceptions import GraphQLCompilationError
from ..macros import perform_macro_expansion
from .test_helpers import get_schema, get_test_macro_registry


class MacroExpansionTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema = get_schema()
        self.macro_registry = get_test_macro_registry()
        self.type_equivalence_hints = {
            self.schema.get_type('Event'): self.schema.get_type('EventOrBirthEvent'),
        }

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
            perform_macro_expansion(self.schema, self.macro_registry, query, args)

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
            perform_macro_expansion(self.schema, self.macro_registry, query, args)

    @pytest.mark.skip(reason='not implemented')
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

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.schema, self.macro_registry, query, args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_invalid_coercion_2(self):
        query = '''{
            Animal {
                out_Animal_NearbyEvents {
                   ... on Entity {
                       name @output(out_name: "event")
                   }
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.schema, self.macro_registry, query, args)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_nonexistent(self):
        query = '''{
            Animal {
                out_Garbage_ThisMacroIsNotInTheRegistry {
                    name @output(out_name: "grandkid")
                }
            }
        }'''
        args = {}

        with self.assertRaises(GraphQLCompilationError):
            perform_macro_expansion(self.schema, self.macro_registry, query, args)
