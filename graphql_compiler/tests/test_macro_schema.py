# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from graphql.utils.schema_printer import print_schema
import pytest

from ..macros import get_schema_with_macros
from .test_helpers import get_test_macro_registry


class MacroSchemaTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.macro_registry = get_test_macro_registry()

    def test_get_schema_with_macros_original_schema_unchanged(self):
        original_printed_schema = print_schema(self.macro_registry.schema_without_macros)
        schema_with_macros = get_schema_with_macros(self.macro_registry)
        printed_schema_afterwards = print_schema(self.macro_registry.schema_without_macros)
        self.assertEqual(original_printed_schema, printed_schema_afterwards)

    # TODO(bojanserafimov): More tests
