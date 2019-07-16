# Copyright 2019-present Kensho Technologies, LLC.
from textwrap import dedent
import unittest

from graphql import parse
from graphql.language.printer import print_ast
from graphql.language.visitor_meta import QUERY_DOCUMENT_KEYS

from ...schema_transformation.rename_schema import RenameSchemaTypesVisitor, rename_schema
from ...schema_transformation.utils import InvalidTypeNameError, SchemaNameConflictError
from .input_schema_strings import InputSchemaStrings as ISS


class TestRenameSchema(unittest.TestCase):
    def test_rename_visitor_type_coverage(self):
        """Check that all types are covered without overlap."""
        all_types = set(ast_type.__name__ for ast_type in QUERY_DOCUMENT_KEYS)
        type_sets = [
            RenameSchemaTypesVisitor.noop_types,
            RenameSchemaTypesVisitor.rename_types,
        ]
        type_sets_union = set()
        for type_set in type_sets:
            self.assertTrue(type_sets_union.isdisjoint(type_set))
            type_sets_union.update(type_set)
        self.assertEqual(all_types, type_sets_union)

    def test_no_rename(self):
        renamed_schema = rename_schema(parse(ISS.basic_schema), {})

        self.assertEqual(ISS.basic_schema, print_ast(renamed_schema.schema_ast))
        self.assertEqual({}, renamed_schema.reverse_name_map)

    def test_basic_rename(self):
        renamed_schema = rename_schema(parse(ISS.basic_schema), {'Human': 'NewHuman'})
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type NewHuman {
              id: String
            }

            type SchemaQuery {
              NewHuman: NewHuman
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'NewHuman': 'Human'}, renamed_schema.reverse_name_map)

    def test_original_unmodified(self):
        original_ast = parse(ISS.basic_schema)
        rename_schema(original_ast, {'Human': 'NewHuman'})
        self.assertEqual(original_ast, parse(ISS.basic_schema))

    def test_swap_rename(self):
        renamed_schema = rename_schema(parse(ISS.multiple_objects_schema),
                                       {'Human': 'Droid', 'Droid': 'Human'})
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Droid {
              name: String
            }

            type Human {
              id: String
            }

            type Dog {
              nickname: String
            }

            type SchemaQuery {
              Droid: Droid
              Human: Human
              Dog: Dog
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'Human': 'Droid', 'Droid': 'Human'},
                         renamed_schema.reverse_name_map)

    def test_cyclic_rename(self):
        renamed_schema = rename_schema(parse(ISS.multiple_objects_schema),
                                       {'Human': 'Droid', 'Droid': 'Dog', 'Dog': 'Human'})
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Droid {
              name: String
            }

            type Dog {
              id: String
            }

            type Human {
              nickname: String
            }

            type SchemaQuery {
              Droid: Droid
              Dog: Dog
              Human: Human
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'Dog': 'Droid', 'Human': 'Dog', 'Droid': 'Human'},
                         renamed_schema.reverse_name_map)

    def test_enum_rename(self):
        renamed_schema = rename_schema(parse(ISS.enum_schema),
                                       {'Droid': 'NewDroid', 'Height': 'NewHeight'})
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type NewDroid {
              height: NewHeight
            }

            type SchemaQuery {
              NewDroid: NewDroid
            }

            enum NewHeight {
              TALL
              SHORT
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'NewDroid': 'Droid', 'NewHeight': 'Height'},
                         renamed_schema.reverse_name_map)

    def test_interface_rename(self):
        renamed_schema = rename_schema(parse(ISS.interface_schema),
                                       {'Kid': 'NewKid', 'Character': 'NewCharacter'})
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            interface NewCharacter {
              id: String
            }

            type NewKid implements NewCharacter {
              id: String
            }

            type SchemaQuery {
              NewCharacter: NewCharacter
              NewKid: NewKid
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'NewKid': 'Kid', 'NewCharacter': 'Character'},
                         renamed_schema.reverse_name_map)

    def test_multiple_interfaces_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.multiple_interfaces_schema), {
                'Human': 'NewHuman', 'Character': 'NewCharacter', 'Creature': 'Creature'
            }
        )
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            interface NewCharacter {
              id: String
            }

            interface Creature {
              age: Int
            }

            type NewHuman implements NewCharacter, Creature {
              id: String
              age: Int
            }

            type SchemaQuery {
              NewCharacter: NewCharacter
              Creature: Creature
              NewHuman: NewHuman
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'NewHuman': 'Human', 'NewCharacter': 'Character'},
                         renamed_schema.reverse_name_map)

    def test_scalar_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.scalar_schema), {
                'Human': 'NewHuman', 'Date': 'NewDate', 'String': 'NewString'
            }
        )
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type NewHuman {
              id: String
              birthday: Date
            }

            scalar Date

            type SchemaQuery {
              NewHuman: NewHuman
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'NewHuman': 'Human'}, renamed_schema.reverse_name_map)

    def test_union_rename(self):
        renamed_schema = rename_schema(parse(ISS.union_schema),
                                       {'HumanOrDroid': 'NewHumanOrDroid', 'Droid': 'NewDroid'})
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: String
            }

            type NewDroid {
              id: String
            }

            union NewHumanOrDroid = Human | NewDroid

            type SchemaQuery {
              Human: Human
              NewDroid: NewDroid
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'NewDroid': 'Droid', 'NewHumanOrDroid': 'HumanOrDroid'},
                         renamed_schema.reverse_name_map)

    def test_list_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.list_schema), {
                'Droid': 'NewDroid',
                'Character': 'NewCharacter',
                'Height': 'NewHeight',
                'Date': 'NewDate',
                'id': 'NewId',
                'String': 'NewString',
            }
        )
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type NewDroid implements NewCharacter {
              id: String
              heights: [NewHeight]
              dates: [Date]
              friends: [NewDroid]
              enemies: [NewCharacter]
            }

            type SchemaQuery {
              NewDroid: [NewDroid]
            }

            scalar Date

            interface NewCharacter {
              id: String
            }

            enum NewHeight {
              TALL
              SHORT
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {
                'NewCharacter': 'Character',
                'NewDroid': 'Droid',
                'NewHeight': 'Height',
            },
            renamed_schema.reverse_name_map
        )

    def test_non_null_rename(self):
        renamed_schema = rename_schema(parse(ISS.non_null_schema), {'Dog': 'NewDog'})
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type NewDog {
              id: String!
              friend: NewDog!
            }

            type SchemaQuery {
              NewDog: NewDog!
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'NewDog': 'Dog'}, renamed_schema.reverse_name_map)

    def test_directive_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.directive_schema),
            {
                'Human': 'NewHuman',
                'Droid': 'NewDroid',
                'stitch': 'NewStitch',
            }
        )
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type NewHuman {
              id: String
            }

            type NewDroid {
              id: String
              friend: NewHuman @stitch(source_field: "id", sink_field: "id")
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type SchemaQuery {
              NewHuman: NewHuman
              NewDroid: NewDroid
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'NewHuman': 'Human', 'NewDroid': 'Droid'},
                         renamed_schema.reverse_name_map)

    def test_query_type_field_argument(self):
        schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Human(id: String!): Human
            }

            type Human {
              name: String
            }
        ''')
        renamed_schema = rename_schema(parse(schema_string), {'Human': 'NewHuman', 'id': 'Id'})
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              NewHuman(id: String!): NewHuman
            }

            type NewHuman {
              name: String
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({'NewHuman': 'Human'}, renamed_schema.reverse_name_map)

    def test_clashing_type_rename(self):
        schema_string = dedent('''\
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
              Human1: Human1
              Human2: Human2
            }
        ''')

        with self.assertRaises(SchemaNameConflictError):
            rename_schema(parse(schema_string), {'Human1': 'Human', 'Human2': 'Human'})

    def test_clashing_type_single_rename(self):
        schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: String
            }

            type Human2 {
              id: String
            }

            type SchemaQuery {
              Human: Human
              Human2: Human2
            }
        ''')

        with self.assertRaises(SchemaNameConflictError):
            rename_schema(parse(schema_string), {'Human2': 'Human'})

    def test_clashing_type_one_unchanged_rename(self):
        schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: String
            }

            type Human2 {
              id: String
            }

            type SchemaQuery {
              Human: Human
              Human2: Human2
            }
        ''')

        with self.assertRaises(SchemaNameConflictError):
            rename_schema(parse(schema_string), {'Human': 'Human', 'Human2': 'Human'})

    def test_clashing_scalar_type_rename(self):
        schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: String
            }

            scalar SCALAR

            type SchemaQuery {
              Human: Human
            }
        ''')

        with self.assertRaises(SchemaNameConflictError):
            rename_schema(parse(schema_string), {'Human': 'SCALAR'})

    def test_builtin_type_conflict_rename(self):
        schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: String
            }

            type SchemaQuery {
              Human: Human
            }
        ''')

        with self.assertRaises(SchemaNameConflictError):
            rename_schema(parse(schema_string), {'Human': 'String'})

    def test_illegal_rename_start_with_number(self):
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {'Human': '0Human'})

    def test_illegal_rename_contains_illegal_char(self):
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {'Human': 'Human!'})
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {'Human': 'H-uman'})
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {'Human': 'H.uman'})

    def test_illegal_rename_to_double_underscore(self):
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {'Human': '__Human'})

    def test_illegal_rename_to_reserved_name_type(self):
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {'Human': '__Type'})

    def test_rename_using_dict_like_prefixer_class(self):
        class PrefixNewDict(object):
            def get(self, key, default=None):
                return 'New' + key

        renamed_schema = rename_schema(parse(ISS.various_types_schema), PrefixNewDict())
        renamed_schema_string = dedent('''\
            schema {
              query: SchemaQuery
            }

            scalar Date

            enum NewHeight {
              TALL
              SHORT
            }

            interface NewCharacter {
              id: String
            }

            type NewHuman implements NewCharacter {
              id: String
              name: String
              birthday: Date
            }

            type NewGiraffe implements NewCharacter {
              id: String
              height: NewHeight
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type SchemaQuery {
              NewHuman: NewHuman
              NewGiraffe: NewGiraffe
            }
        ''')
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {
                'NewCharacter': 'Character',
                'NewGiraffe': 'Giraffe',
                'NewHeight': 'Height',
                'NewHuman': 'Human'
            },
            renamed_schema.reverse_name_map
        )
