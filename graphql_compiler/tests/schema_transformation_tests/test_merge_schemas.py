# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict
from textwrap import dedent
import unittest

from graphql import parse
from graphql.language.printer import print_ast

from graphql_compiler.schema_transformation.merge_schemas import merge_schemas
from graphql_compiler.schema_transformation.utils import SchemaNameConflictError

from .input_schema_strings import InputSchemaStrings as ISS


class TestMergeSchemas(unittest.TestCase):
    def test_basic_merge(self):
        merged_schema = merge_schemas(
            OrderedDict({
                'basic': parse(ISS.basic_schema),
                'enum': parse(ISS.enum_schema),
            })
        )
        merged_schema_string = dedent('''\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Droid: Droid
            }

            type Human {
              id: String
            }

            type Droid {
              height: Height
            }

            enum Height {
              TALL
              SHORT
            }
        ''')
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))
        self.assertEqual({'Droid': 'enum', 'Height': 'enum', 'Human': 'basic'},
                         merged_schema.name_to_schema_id)

    def test_originals_unmodified(self):
        basic_ast = parse(ISS.basic_schema)
        enum_ast = parse(ISS.enum_schema)
        merge_schemas(
            OrderedDict({
                'basic': basic_ast,
                'enum': enum_ast
            })
        )
        self.assertEqual(basic_ast, parse(ISS.basic_schema))
        self.assertEqual(enum_ast, parse(ISS.enum_schema))

    def test_multiple_merge(self):
        merged_schema = merge_schemas(
            OrderedDict({
                'first': parse(ISS.basic_schema),
                'second': parse(ISS.enum_schema),
                'third': parse(ISS.interface_schema),
                'fourth': parse(ISS.non_null_schema),
            })
        )
        merged_schema_string = dedent('''\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Droid: Droid
              Character: Character
              Kid: Kid
              Dog: Dog!
            }

            type Human {
              id: String
            }

            type Droid {
              height: Height
            }

            enum Height {
              TALL
              SHORT
            }

            interface Character {
              id: String
            }

            type Kid implements Character {
              id: String
            }

            type Dog {
              id: String!
              friend: Dog!
            }
        ''')
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_diff_query_type_name_merge(self):
        diff_query_type_schema = dedent('''\
            schema {
              query: RandomRootSchemaQueryName
            }

            type Droid {
              id: String
            }

            type RandomRootSchemaQueryName {
              Droid: Droid
            }
        ''')
        merged_schema = merge_schemas(
            OrderedDict({
                'first': parse(ISS.basic_schema),
                'second': parse(diff_query_type_schema),
            })
        )
        merged_schema_string = dedent('''\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Droid: Droid
            }

            type Human {
              id: String
            }

            type Droid {
              id: String
            }
        ''')
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_type_conflict_merge(self):
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'first': parse(ISS.basic_schema),
                    'second': parse(ISS.basic_schema),
                })
            )

    def test_interface_type_conflict_merge(self):
        interface_conflict_schema = dedent('''\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            interface Human {
              id: String
            }
        ''')
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'basic': parse(ISS.basic_schema),
                    'bad': parse(interface_conflict_schema),
                })
            )
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'bad': parse(interface_conflict_schema),
                    'basic': parse(ISS.basic_schema),
                })
            )

    def test_enum_type_conflict_merge(self):
        enum_conflict_schema = dedent('''\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            enum Human {
              CHILD
              ADULT
            }
        ''')
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'basic': parse(ISS.basic_schema),
                    'bad': parse(enum_conflict_schema),
                })
            )
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'bad': parse(enum_conflict_schema),
                    'basic': parse(ISS.basic_schema),
                })
            )

    def test_enum_interface_conflict_merge(self):
        enum_conflict_schema = dedent('''\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            enum Character {
              FICTIONAL
              REAL
            }
        ''')
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'interface': parse(ISS.interface_schema),
                    'bad': parse(enum_conflict_schema),
                })
            )
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'bad': parse(enum_conflict_schema),
                    'interface': parse(ISS.interface_schema),
                })
            )

    def test_type_scalar_conflict_merge(self):
        scalar_conflict_schema = dedent('''\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            scalar Human
        ''')
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'basic': parse(ISS.basic_schema),
                    'bad': parse(scalar_conflict_schema),
                })
            )
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'bad': parse(scalar_conflict_schema),
                    'basic': parse(ISS.basic_schema),
                })
            )

    def test_interface_scalar_conflict_merge(self):
        scalar_conflict_schema = dedent('''\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            scalar Character
        ''')
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'interface': parse(ISS.interface_schema),
                    'bad': parse(scalar_conflict_schema),
                })
            )
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'bad': parse(scalar_conflict_schema),
                    'interface': parse(ISS.interface_schema),
                })
            )

    def test_enum_scalar_conflict_merge(self):
        scalar_conflict_schema = dedent('''\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            scalar Height
        ''')
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'enum': parse(ISS.enum_schema),
                    'bad': parse(scalar_conflict_schema),
                })
            )
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'bad': parse(scalar_conflict_schema),
                    'enum': parse(ISS.enum_schema),
                })
            )

    def test_dedup_scalars(self):
        extra_scalar_schema = dedent('''\
            schema {
              query: SchemaQuery
            }

            scalar Date

            scalar Decimal

            type Kid {
              height: Decimal
            }

            type SchemaQuery {
              Kid: Kid
            }
        ''')
        merged_schema = merge_schemas(
            OrderedDict({
                'first': parse(ISS.scalar_schema),
                'second': parse(extra_scalar_schema),
            })
        )
        merged_schema_string = dedent('''\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Kid: Kid
            }

            type Human {
              id: String
              birthday: Date
            }

            scalar Date

            scalar Decimal

            type Kid {
              height: Decimal
            }
        ''')
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))
        self.assertEqual({'Human': 'first', 'Kid': 'second'},
                         merged_schema.name_to_schema_id)

    def test_dedup_same_directives(self):
        extra_directive_schema = dedent('''\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            directive @output(out_name: String!) on FIELD

            type Kid {
              id: String
            }

            type SchemaQuery {
              Kid: Kid
            }
        ''')
        merged_schema = merge_schemas(
            OrderedDict({
                'first': parse(ISS.directive_schema),
                'second': parse(extra_directive_schema),
            })
        )
        merged_schema_string = dedent('''\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Droid: Droid
              Kid: Kid
            }

            type Human {
              id: String
            }

            type Droid {
              id: String
              friend: Human @stitch(source_field: "id", sink_field: "id")
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            directive @output(out_name: String!) on FIELD

            type Kid {
              id: String
            }
        ''')
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))
        self.assertEqual({'Human': 'first', 'Droid': 'first', 'Kid': 'second'},
                         merged_schema.name_to_schema_id)

    def test_dedup_clashing_directives(self):
        extra_directive_schema = dedent('''\
            schema {
              query: SchemaQuery
            }

            directive @stitch(out_name: String!) on FIELD

            type Kid {
              id: String
            }

            type SchemaQuery {
              Kid: Kid
            }
        ''')
        with self.assertRaises(SchemaNameConflictError):
            merge_schemas(
                OrderedDict({
                    'first': parse(ISS.directive_schema),
                    'second': parse(extra_directive_schema),
                })
            )
