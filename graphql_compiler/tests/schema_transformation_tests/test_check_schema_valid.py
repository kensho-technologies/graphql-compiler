# Copyright 2019-present Kensho Technologies, LLC.
from textwrap import dedent
import unittest

from graphql import parse

from ...schema_transformation.utils import (
    InvalidNameError,
    SchemaStructureError,
    check_ast_schema_is_valid,
)


class TestCheckSchemaValid(unittest.TestCase):
    def test_missing_type_schema(self):
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Human: Human
            }
        """
        )
        with self.assertRaises(TypeError):
            check_ast_schema_is_valid(parse(schema_string))

    def test_schema_extension(self):
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Human: Human
            }

            type Human {
              id: String
            }

            extend type Human {
              age: Int
            }
        """
        )
        with self.assertRaises(SchemaStructureError):
            check_ast_schema_is_valid(parse(schema_string))

    def test_input_type_definition(self):
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              id: String
            }

            input MessageInput {
              content: String
            }
        """
        )
        with self.assertRaises(SchemaStructureError):
            check_ast_schema_is_valid(parse(schema_string))

    def test_mutation_definition(self):
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
              mutation: SchemaMutation
            }

            type SchemaQuery {
              id: String
            }

            type SchemaMutation {
              addId(id: String): String
            }
        """
        )
        with self.assertRaises(SchemaStructureError):
            check_ast_schema_is_valid(parse(schema_string))

    def test_subscription_definition(self):
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
              subscription: SchemaSubscription
            }

            type SchemaQuery {
              id: String
            }

            type SchemaSubscription {
              getId: String
            }
        """
        )
        with self.assertRaises(SchemaStructureError):
            check_ast_schema_is_valid(parse(schema_string))

    def test_inconsistent_root_field_name(self):
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Human1 {
              id: String
            }

            type Human2 {
              id: String
            }

            type SchemaQuery {
              human1: Human1
              human2: Human2
            }
        """
        )

        with self.assertRaises(SchemaStructureError):
            check_ast_schema_is_valid(parse(schema_string))

    def test_illegal_double_underscore_name(self):
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              __Human: __Human
            }

            type __Human {
              id: String
            }
        """
        )
        with self.assertRaises(InvalidNameError):
            check_ast_schema_is_valid(parse(schema_string))

    def test_illegal_reserved_name_type(self):
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Human: Human
            }

            type Human {
              id: String
            }

            type __Type {
              id: String
            }
        """
        )
        with self.assertRaises(InvalidNameError):
            check_ast_schema_is_valid(parse(schema_string))

    def test_illegal_reserved_name_enum(self):
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Human: Human
            }

            type Human {
              id: String
            }

            enum __Type {
              ENUM1
              ENUM2
            }
        """
        )
        with self.assertRaises(InvalidNameError):
            check_ast_schema_is_valid(parse(schema_string))

    def test_illegal_reserved_name_scalar(self):
        # NOTE: such scalars will not appear in typemap!
        # See graphql/type/introspection for all reserved types
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Human: Human
            }

            type Human {
              id: String
            }

            scalar __Type
        """
        )
        with self.assertRaises(InvalidNameError):
            check_ast_schema_is_valid(parse(schema_string))
