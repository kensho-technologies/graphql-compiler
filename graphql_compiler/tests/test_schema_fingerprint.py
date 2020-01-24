# Copyright 2020-present Kensho Technologies, LLC.
import unittest

from graphql import build_ast_schema, parse, print_schema, GraphQLSchema
import pytest

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

def _compute_schema_text_fingerprint(schema: ):


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

    def test_different_field_type(self):
        schema_text1 = """
            type Object {
                field: String
            }
        """
        schema_text2 = """
            type Object {
                field: Int
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

    def test_field_argument_order(self):
        schema_text1 = """
            type Object {
                field(a: Int, b: String): String
            }
        """
        schema_text2 = """
            type Object {
                field(b: String, a: Int): String
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_different_field_arguments(self):
        schema_text1 = """
            type Object {
                field(a: Int, b: String): String
            }
        """
        schema_text2 = """
            type Object {
                field(a: Int): Int
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

    def test_enum_order(self):
        schema_text1 = """
            enum Enum{
                A
                B
            }
        """
        schema_text2 = """
            enum Enum{
                B
                A
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_different_enum(self):
        schema_text1 = """
            enum Enum{
                A
                B
            }
        """
        schema_text2 = """
            enum Enum{
                A
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

    def test_input_order(self):
        schema_text1 = """
            input Input {
                a: Int
                b: Int
            }
        """
        schema_text2 = """
            input Input {
                b: Int
                a: Int
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_different_input(self):
        schema_text1 = """
            input Input {
                a: Int
                b: Int
            }
        """
        schema_text2 = """
            input Input {
                a: Int
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Type extension information is lost when a schema is print and parsed. "
            "See https://github.com/graphql/graphql-js/issues/2386"
        ),
    )
    def test_field_equivalency_with_type_extension(self):
        schema_text1 = """
            type Object {
                a: Int
            }
            extend type Object {
                b: Int
            }
        """
        schema_text2 = """
            type Object {
                a: Int
                b: Int
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Type extension information is lost when a schema is print and parsed. "
            "See https://github.com/graphql/graphql-js/issues/2386"
        ),
    )
    def test_interface_equivalency_with_type_extension(self):
        schema_text1 = """
            type Object {
                a: Int
            }
            extend type Object {
                b: Int
            }
        """
        schema_text2 = """
            type Object {
                a: Int
                b: Int
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Type extension information is lost when a schema is print and parsed. "
            "See https://github.com/graphql/graphql-js/issues/2386"
        ),
    )
    def test_different_type_extensions(self):
        schema_text1 = """
            type Object {
                a: Int
            }
            extend type Object {
                b: Int
            }
        """
        schema_text2 = """
            type Object {
                a: Int
            }
            extend type Object {
                c: Int
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

    def test_interface_implementation_order(self):
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

    def test_different_interface_implementation(self):
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
            type Object implements Interface1 {
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
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

    def test_union_definition_order(self):
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

    def test_different_union_definitions(self):
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

            union UnionType = Object1
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

    def test_top_level_type_order(self):
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

    def test_different_top_level_types(self):
        schema_text1 = """
            scalar Date

            directive @output on FIELD

            type Object {
                field1: String
            }

            union UnionType = Object
        """
        schema_text2 = """
            scalar Date

            directive @output on FIELD

            type Object {
                field1: String
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

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

    def test_different_schema_operations(self):
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
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

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

    def test_different_deprecation_reason(self):
        schema_text1 = """
            type Object {
                field: String @deprecated(reason: "Reason 1")
            }
        """
        schema_text2 = """
            type Object {
                field: String @deprecated(reason: "Reason 2")
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

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

    def test_different_directive_arguments(self):
        schema_text1 = """
            directive @filter(
                op_name: String!
                value: [String!]
            ) repeatable on FIELD | INLINE_FRAGMENT
        """
        schema_text2 = """
            directive @filter(
                op_name: String!
            ) repeatable on FIELD | INLINE_FRAGMENT
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

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

    def test_different_directive_locations(self):
        schema_text1 = """
            directive @filter(
                op_name: String!
                value: [String!]
            ) repeatable on FIELD | INLINE_FRAGMENT
        """
        schema_text2 = """
            directive @filter(
                op_name: String!
                value: [String!]
            ) repeatable on FIELD
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)

    def test_argument_order_of_directives_at_field_definitions(self):
        schema_text1 = """
            directive @custom_directive(a: Int, b: String) on FIELD_DEFINITION

            type Object {
                field: String @custom_directive(b: "a", a: 1)
            }
        """
        schema_text2 = """
            directive @custom_directive(a: Int, b: String) on FIELD_DEFINITION

            type Object {
                field: String @custom_directive(a: 1, b: "a")
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_reordered_directives_at_field_definition(self):
        schema_text1 = """
            directive @custom_directive1(a: Int, b: String) on FIELD_DEFINITION
            directive @custom_directive2(c: Int, d: String) on FIELD_DEFINITION

            type Object {
                field: String @custom_directive1(a: 1, b: "a") @custom_directive2(c: 1, d: "a")
            }
        """
        schema_text2 = """
            directive @custom_directive1(a: Int, b: String) on FIELD_DEFINITION
            directive @custom_directive2(c: Int, d: String) on FIELD_DEFINITION

            type Object {
                field: String @custom_directive2(d: "a", c: 1) @custom_directive1(b: "a", a: 1)
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    def test_reordered_repeatable_directives_at_field_definition(self):
        schema_text1 = """
            directive @custom_directive1(a: Int, b: String) repeatable on FIELD_DEFINITION

            type Object {
                field: String @custom_directive1(a: 1, b: "a") @custom_directive1(b: 0, a: "b")
            }
        """
        schema_text2 = """
            directive @custom_directive1(a: Int, b: String) repeatable on FIELD_DEFINITION

            type Object {
                field: String @custom_directive1(a: "b", b: 0) @custom_directive1(b: "a", a: 1)
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Directives at field definitions are lost when a schema is printed and parsed."
            "See https://github.com/graphql/graphql-js/issues/2389."
        ),
    )
    def test_different_directives_at_field_definitions(self):
        schema_text1 = """
            directive @custom_directive(a: Int) on FIELD_DEFINITION

            type Object {
                field: String @custom_directive(a: 1)
            }
        """
        schema_text2 = """
            directive @custom_directive(a: Int) on FIELD_DEFINITION

            type Object {
                field: String @custom_directive(a: 2)
            }
        """
        _compare_schema_fingerprints(self, schema_text1, schema_text2, expect_equality=False)
