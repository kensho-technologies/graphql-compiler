# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ..exceptions import GraphQLInvalidArgumentError, GraphQLInvalidMacroError
from ..macros import create_macro_registry, register_macro_edge
from .test_helpers import get_schema


class MacroValidationTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema = get_schema()
        self.type_equivalence_hints = {
            self.schema.get_type('Event'): self.schema.get_type('EventOrBirthEvent'),
        }

    def test_bad_operation_type(self):
        query = '''mutation {
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_with_output_directive(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_with_output_source_directive(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf @output_source {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_with_target_inside_fold(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf @fold {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_with_target_outside_fold(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
                out_Animal_LivesIn @fold {
                    _x_count @filter(op_name: "=", value: ["$num_locations"])
                }
            }
        }'''
        args = {
            'num_locations': 1,
        }

        # It should compile successfully
        macro_registry = create_macro_registry()
        register_macro_edge(macro_registry, self.schema, query,
                            args, self.type_equivalence_hints)

    def test_macro_edge_missing_target(self):
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

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_multiple_targets(self):
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

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_multiple_targets_2(self):
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

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_missing_definition(self):
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

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_invalid_definition(self):
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

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_invalid_target_directive(self):
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

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_invalid_no_op_1(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_Self") @macro_edge_target {
                uuid
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_invalid_no_op_2(self):
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

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_missing_args(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
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

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidArgumentError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_extra_args(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
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

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidArgumentError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_incorrect_arg_types(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
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
            'net_worth': 'five_cows',
            'color': 'green',
        }

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidArgumentError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_multiple_definitions(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Copy") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_duplicate_definition(self):
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        register_macro_edge(macro_registry, self.schema, query,
                            args, self.type_equivalence_hints)
        with self.assertRaises(AssertionError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_duplicating_real_edge_name(self):
        query = '''{
            Species @macro_edge_definition(name: "out_Species_Eats") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_duplicating_real_edge_name_at_target(self):
        query = '''{
            Species @macro_edge_definition(name: "out_Animal_ParentOf") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    def test_macro_edge_duplicating_field_name(self):
        query = '''{
            Species @macro_edge_definition(name: "net_worth") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_duplicate_definition_on_target(self):
        # Future-proofing, so that we can reverse macro edges
        query = '''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''

        # Meaningless query that has the same target and name
        duplicate_query = '''{
            Location @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }'''
        args = {}

        macro_registry = create_macro_registry()
        register_macro_edge(macro_registry, self.schema, query,
                            args, self.type_equivalence_hints)
        with self.assertRaises(AssertionError):
            register_macro_edge(macro_registry, self.schema, duplicate_query,
                                args, self.type_equivalence_hints)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_dulpicate_definition_on_subclass(self):
        query = '''{
            Entity @macro_edge_definition(name: "out__RelatedOfRelated") {
                out_Entity_Related {
                    out_Entity_Related @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        query_on_subclass = '''{
            Event @macro_edge_definition(name: "out__RelatedOfRelated") {
                out_Entity_Related {
                    out_Entity_Related @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        args = {}

        # Try registering on the superclass first
        macro_registry = create_macro_registry()
        register_macro_edge(macro_registry, self.schema, query,
                            args, self.type_equivalence_hints)
        with self.assertRaises(AssertionError):
            register_macro_edge(macro_registry, self.schema, query_on_subclass,
                                args, self.type_equivalence_hints)

        # Try registering on the subclass first
        macro_registry = create_macro_registry()
        register_macro_edge(macro_registry, self.schema, query_on_subclass,
                            args, self.type_equivalence_hints)
        with self.assertRaises(AssertionError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)

    @pytest.mark.skip(reason='not implemented')
    def test_macro_edge_duplicate_definition_on_target_subclass(self):
        query = '''{
            Entity @macro_edge_definition(name: "out__RelatedOfRelated") {
                out_Entity_Related {
                    out_Entity_Related @macro_edge_target {
                        uuid
                    }
                }
            }
        }'''
        query_on_subclass = '''{
            Entity @macro_edge_definition(name: "out__RelatedOfRelated") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Event @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }'''
        args = {}

        # Try registering on the superclass first
        macro_registry = create_macro_registry()
        register_macro_edge(macro_registry, self.schema, query,
                            args, self.type_equivalence_hints)
        with self.assertRaises(AssertionError):
            register_macro_edge(macro_registry, self.schema, query_on_subclass,
                                args, self.type_equivalence_hints)

        # Try registering on the subclass first
        macro_registry = create_macro_registry()
        register_macro_edge(macro_registry, self.schema, query_on_subclass,
                            args, self.type_equivalence_hints)
        with self.assertRaises(AssertionError):
            register_macro_edge(macro_registry, self.schema, query,
                                args, self.type_equivalence_hints)
