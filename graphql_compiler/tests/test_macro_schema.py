# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.type import GraphQLList
from graphql.utils.schema_printer import print_schema

from ..macros import get_schema_for_macro_definition, get_schema_with_macros
from ..macros.macro_edge.directives import MACRO_EDGE_DEFINITION_DIRECTIVES
from .test_helpers import get_empty_test_macro_registry, get_test_macro_registry


class MacroSchemaTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.macro_registry = get_test_macro_registry()

    def test_get_schema_with_macros_original_schema_unchanged(self):
        empty_macro_registry = get_empty_test_macro_registry()
        original_printed_schema = print_schema(self.macro_registry.schema_without_macros)
        printed_schema_with_0_macros = print_schema(get_schema_with_macros(empty_macro_registry))
        printed_schema_afterwards = print_schema(self.macro_registry.schema_without_macros)
        self.assertEqual(original_printed_schema, printed_schema_afterwards)
        self.assertEqual(original_printed_schema, printed_schema_with_0_macros)

    def test_get_schema_with_macros_basic(self):
        schema_with_macros = get_schema_with_macros(self.macro_registry)
        grandparent_target_type = schema_with_macros.get_type(
            'Animal').fields['out_Animal_GrandparentOf'].type
        self.assertTrue(isinstance(grandparent_target_type, GraphQLList))
        self.assertEqual('Animal', grandparent_target_type.of_type.name)
        related_food_target_type = schema_with_macros.get_type(
            'Animal').fields['out_Animal_RelatedFood'].type
        self.assertTrue(isinstance(related_food_target_type, GraphQLList))
        self.assertEqual('Food', related_food_target_type.of_type.name)

    def test_get_schema_for_macro_definition_unchanged(self):
        original_schema = self.macro_registry.schema_without_macros
        original_printed_schema = print_schema(original_schema)
        macro_definition_schema = get_schema_for_macro_definition(original_schema)
        macro_definition_printed_schema = print_schema(macro_definition_schema)
        for directive in MACRO_EDGE_DEFINITION_DIRECTIVES:
            self.assertTrue(directive in macro_definition_schema.get_directives())
        self.assertNotEqual(original_printed_schema, macro_definition_printed_schema)

    def test_get_schema_for_macro_definition_basic(self):
        schema_with_macros = get_schema_with_macros(self.macro_registry)
        printed_schema_with_macros = print_schema(schema_with_macros)
        macro_definition_schema = get_schema_for_macro_definition(schema_with_macros)
        macro_definition_printed_schema = print_schema(macro_definition_schema)
        for directive in MACRO_EDGE_DEFINITION_DIRECTIVES:
            self.assertTrue(directive in macro_definition_schema.get_directives())
        self.assertNotEqual(printed_schema_with_macros, macro_definition_printed_schema)
