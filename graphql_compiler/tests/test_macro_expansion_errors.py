# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from ..exceptions import GraphQLInvalidMacroError
from ..macros import create_macro_registry, register_macro_edge
from .test_helpers import get_schema


class MacroExpansionErrorsTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema = get_schema()
        self.macro_registry = create_macro_registry()
        self.type_equivalence_hints = {
            self.schema.get_type('Event'): self.schema.get_type('EventOrBirthEvent'),
        }

    def test_edge_macro_missing_target(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        uuid
                    }
                }
            }
        }'''
        args = {}
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_edge_macro_multiple_targets(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf @macro_edge_target {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_edge_macro_multiple_targets_2(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_edge_macro_missing_definition(self):
        query = '''{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_edge_macro_invalid_definition(self):
        query = '''{
            Animal @macro_edge_definition {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_edge_macro_invalid_target_directive(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_AvailableFood_Invalid") {
                out_Animal_LivesIn {
                    in_Entity_Related @macro_edge_target {
                        ... on Food {
                            uuid
                        }
                    }
                }
            }
        }'''
        args = {}
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_edge_macro_invalid_no_op_1(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_Self") @macro_edge_target {
                uuid
            }
        }'''
        args = {}
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_edge_macro_invalid_no_op_2(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_Filter") @macro_edge_target {
                net_worth @filter(op_name: "=", value: ["$net_worth"])
                color @filter(op_name: "=", value: ["$color"])
            }
        }'''
        args = {
            'net_worth': 4,
            'color': 'green',
        }
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_edge_macro_missing_args(self):
        query = '''{
            Animal @macro_edge_definition {
                net_worth @filter(op_name: "=", value: ["$net_worth"])
                color @filter(op_name: "=", value: ["$color"])
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {
            'net_worth': 4,
        }
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_edge_macro_extra_args(self):
        query = '''{
            Animal @macro_edge_definition {
                net_worth @filter(op_name: "=", value: ["$net_worth"])
                color @filter(op_name: "=", value: ["$color"])
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {
            'net_worth': 4,
            'color': 'green',
            'asdf': 5
        }
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(self.macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)
