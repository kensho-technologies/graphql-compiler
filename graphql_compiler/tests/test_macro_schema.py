# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.type import GraphQLList
from graphql.utils.schema_printer import print_schema
import pytest

from ..macros import get_schema_for_macro_definition, get_schema_with_macros
from ..macros.macro_edge.directives import (DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION,
                                            DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION)
from ..macros.macro_edge.validation import get_and_validate_macro_edge_info
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
            self.assertTrue(directive.name != '@output')
            self.assertTrue(directive.name != '@output_source')

    @pytest.mark.skip('unimplemented test')
    def test_get_schema_for_macro_definition_validation(self):
        return
        # partial_schema_with_macros = self.macro_registry.schema_without_macros
        # macro_definition_schema = get_schema_for_macro_definition(partial_schema_with_macros)
        # args = {}
        #
        # # TODO: validate macro edges using the generated schema
        #
        # for macro, partner in self.macro_registry.macro_edges.items():
        #     get_and_validate_macro_edge_info(macro_definition_schema, partner, macro[1],
        #                                      self.macro_registry.type_equivalence_hints)
