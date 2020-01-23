# Copyright 2020-present Kensho Technologies, LLC.
import unittest

from graphql import build_ast_schema, parse, print_schema

from ..schema import compute_schema_fingerprint
from .test_helpers import compare_graphql


def _compare_schema_fingerprints(
    test_case: unittest.TestCase, schema_text1: str, schema_text2: str, expect_equality: bool = True
) -> None:
    """Build the schemas from the schema texts and compare their fingerprints for equality."""
    fingerprint1 = compute_schema_fingerprint(build_ast_schema(parse(schema_text1)))
    fingerprint2 = compute_schema_fingerprint(build_ast_schema(parse(schema_text2)))
    if expect_equality:
        test_case.assertEqual(fingerprint1, fingerprint2)
    else:
        test_case.assertNotEqual(fingerprint1, fingerprint2)


class SchemaFingerprintTests(unittest.TestCase):
    def test_schema_fingerprint_basic(self):
        schema_text = """
            type Object{
                field2: String
                field1: String
                field4: String
                field3: String
            }
        """
        schema = build_ast_schema(parse(schema_text))
        fingerprint = compute_schema_fingerprint(build_ast_schema(parse(schema_text)))

        # Assert that compute_schema_fingerprint does not modify the original schema.
        compare_graphql(self, schema_text, print_schema(schema))

        # Assert that compute_schema_fingerprint disregards field order.
        reordered_schema_text = """
            type Object{
                field1: String
                field3: String
                field4: String
                field2: String
            }
        """
        reordered_schema_fingerprint = compute_schema_fingerprint(
            build_ast_schema(parse(reordered_schema_text))
        )
        self.assertEqual(reordered_schema_fingerprint, fingerprint)

        # Assert that the computed fingerprint is not the same if we add a new field.
        schema_text_with_added_field = """
            type Object{
                field1: String
                field3: String
                field4: String
                field2: String
                field5: String
            }
        """
        schema_with_added_field_fingerprint = compute_schema_fingerprint(
            build_ast_schema(parse(schema_text_with_added_field))
        )
        self.assertNotEqual(schema_with_added_field_fingerprint, fingerprint)

    def test_interface_order(self):
        schema_text1 = """
            type Object implements Interface1 & Interface2 {
                field1: String
                field2: String
            }

            interface Interface1 {
                field1: String
            }

            interface Interface2 {
                field1: String
            }
        """
        schema_text2 = """
            type Object implements Interface2 & Interface1 {
                field1: String
                field2: String
            }

            interface Interface1 {
                field1: String
            }

            interface Interface2 {
                field1: String
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_union_order(self):
        schema_text1 = """
            type Object1 {
                field1: String
            }

            type Object2 {
                field2: String
            }

            union UnionType = Object1 | Object2
        """
        schema_text2 = """
            type Object1 {
                field1: String
            }

            type Object2 {
                field2: String
            }

            union UnionType = Object2 | Object1
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_top_level_order(self):
        schema_text1 = """
            scalar Date

            directive @output on FIELD

            type Object {
                field1: String
            }

            union UnionType = Object
        """
        schema_text2 = """
            directive @output on FIELD

            scalar Date

            union UnionType = Object

            type Object {
                field1: String
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_directive_definition_argument_order(self):
        schema_text1 = """
            directive @filter(
                op_name: String!
                value: [String!]
            ) repeatable on FIELD | INLINE_FRAGMENT
        """
        schema_text2 = """
            directive @filter(
                value: [String!]
                op_name: String!
            ) repeatable on FIELD | INLINE_FRAGMENT
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_directive_definition_location_order(self):
        schema_text1 = """
            directive @filter(
                op_name: String!
                value: [String!]
            ) repeatable on FIELD | INLINE_FRAGMENT
        """
        schema_text2 = """
            directive @filter(
                value: [String!]
                op_name: String!
            ) repeatable on INLINE_FRAGMENT | FIELD
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_argument_order_of_field_definition_directive(self):
        schema_text1 = """
            directive @custom_directive(b: String, a: Int) on FIELD_DEFINITION

            type Foo {
                my_field: Int @custom_directive(b: "123", a: 1)
            }
        """
        schema_text2 = """
            directive @custom_directive(b: String, a: Int) on FIELD_DEFINITION

            type Foo {
                my_field: Int @custom_directive(a: 1, b: "123")
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_schema_operation_order(self):
        schema_text1 = """
            schema {
               query: RootSchemaQuery
               mutation: RootSchemaMutation
            }
            type Object1 {
                field1: String
            }

            type RootSchemaQuery {
                Object1: [Object1]
            }

            type RootSchemaMutation {
                Object1: [Object1]
            }
        """
        schema_text2 = """
            schema {
               mutation: RootSchemaMutation
               query: RootSchemaQuery
            }
            type Object1 {
                field1: String
            }

            type RootSchemaQuery {
                Object1: [Object1]
            }

            type RootSchemaMutation {
                Object1: [Object1]
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_description_change(self):
        schema_text1 = """
            \"\"\"
            Description 1
            \"\"\"
            scalar Date
        """
        schema_text2 = """
            \"\"\"
            Description 2
            \"\"\"
            scalar Date
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)
