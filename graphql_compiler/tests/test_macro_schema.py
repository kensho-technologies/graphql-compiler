# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.type import GraphQLList
from graphql.utils.schema_printer import print_schema
from graphql.validation import validate

from ..ast_manipulation import safe_parse_graphql
from ..macros import get_schema_for_macro_definition, get_schema_with_macros
from ..macros.macro_edge.directives import (
    DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION, DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION
)
from ..schema import OutputDirective, OutputSourceDirective
from .test_helpers import VALID_MACROS_TEXT, get_empty_test_macro_registry, get_test_macro_registry


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

    def test_get_schema_for_macro_definition_addition(self):
        original_schema = self.macro_registry.schema_without_macros
        macro_definition_schema = get_schema_for_macro_definition(original_schema)
        for directive in DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION:
            self.assertTrue(directive in macro_definition_schema.get_directives())

    def test_get_schema_for_macro_definition_retain(self):
        original_schema = self.macro_registry.schema_without_macros
        macro_definition_schema = get_schema_for_macro_definition(original_schema)
        for directive in original_schema.get_directives():
            if directive in DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION:
                self.assertTrue(directive in macro_definition_schema.get_directives())

    def test_get_schema_for_macro_definition_removal(self):
        schema_with_macros = get_schema_with_macros(self.macro_registry)
        macro_definition_schema = get_schema_for_macro_definition(schema_with_macros)
        for directive in macro_definition_schema.get_directives():
            self.assertTrue(directive.name != OutputDirective.name)
            self.assertTrue(directive.name != OutputSourceDirective.name)

    def test_get_schema_for_macro_definition_validation(self):
        macro_definition_schema = get_schema_for_macro_definition(
            self.macro_registry.schema_without_macros)

        for macro, _ in VALID_MACROS_TEXT:
            macro_edge_definition_ast = safe_parse_graphql(macro)
            validate(macro_definition_schema, macro_edge_definition_ast)
