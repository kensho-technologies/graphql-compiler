# Copyright 2019-present Kensho Technologies, LLC.
from textwrap import dedent
from typing import Set
import unittest

from graphql import parse
from graphql.language.printer import print_ast
from graphql.language.visitor import QUERY_DOCUMENT_KEYS
from graphql.pyutils import snake_to_camel

from ...schema_transformation.rename_schema import RenameSchemaTypesVisitor, rename_schema
from ...schema_transformation.utils import (
    CascadingSuppressionError,
    InvalidNameError,
    NoOpRenamingError,
    SchemaRenameNameConflictError,
    SchemaTransformError,
)
from ..test_helpers import compare_schema_texts_order_independently
from .input_schema_strings import InputSchemaStrings as ISS


class TestRenameSchema(unittest.TestCase):
    def test_rename_visitor_type_coverage(self) -> None:
        """Check that all types are covered without overlap."""
        type_sets = [
            RenameSchemaTypesVisitor.noop_types,
            RenameSchemaTypesVisitor.rename_types,
        ]
        all_types = {snake_to_camel(node_type) + "Node" for node_type in QUERY_DOCUMENT_KEYS}
        type_sets_union: Set[str] = set()
        for type_set in type_sets:
            self.assertTrue(type_sets_union.isdisjoint(type_set))
            type_sets_union.update(type_set)
        self.assertEqual(all_types, type_sets_union)

    def test_no_rename(self) -> None:
        renamed_schema = rename_schema(parse(ISS.basic_schema), {}, {})

        compare_schema_texts_order_independently(
            self, ISS.basic_schema, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_basic_rename(self) -> None:
        renamed_schema = rename_schema(parse(ISS.basic_schema), {"Human": "NewHuman"}, {})
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type NewHuman {
              id: String
            }

            type SchemaQuery {
              NewHuman: NewHuman
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({"NewHuman": "Human"}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_type_directive_same_name(self) -> None:
        # Types, fields, and directives have different namespaces, so this schema and renaming are
        # both valid and the renaming only affects the object type.
        renamed_schema = rename_schema(
            parse(ISS.type_field_directive_same_name_schema), {"stitch": "NewStitch"}, {}
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type NewStitch {
              stitch: String
            }

            type SchemaQuery {
              NewStitch: NewStitch
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({"NewStitch": "stitch"}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_original_unmodified_rename(self) -> None:
        original_ast = parse(ISS.basic_schema)
        rename_schema(original_ast, {"Human": "NewHuman"}, {})
        self.assertEqual(original_ast, parse(ISS.basic_schema))

    def test_original_unmodified_suppress(self) -> None:
        original_ast = parse(ISS.multiple_objects_schema)
        rename_schema(original_ast, {"Human": None}, {})
        self.assertEqual(original_ast, parse(ISS.multiple_objects_schema))

    def test_rename_illegal_noop_unused_renaming(self) -> None:
        with self.assertRaises(NoOpRenamingError):
            rename_schema(parse(ISS.basic_schema), {"Dinosaur": "NewDinosaur"}, {})

    def test_rename_illegal_noop_renamed_to_self(self) -> None:
        with self.assertRaises(NoOpRenamingError):
            rename_schema(parse(ISS.basic_schema), {"Human": "Human"}, {})

    def test_basic_suppress(self) -> None:
        renamed_schema = rename_schema(parse(ISS.multiple_objects_schema), {"Human": None}, {})
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Droid {
              id: String
            }

            type Dog {
              nickname: String
            }

            type SchemaQuery {
              Droid: Droid
              Dog: Dog
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_multiple_type_suppress(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.multiple_objects_schema), {"Human": None, "Droid": None}, {}
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Dog {
              nickname: String
            }

            type SchemaQuery {
              Dog: Dog
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_suppress_illegal_noop_unused_suppression(self) -> None:
        with self.assertRaises(NoOpRenamingError):
            rename_schema(parse(ISS.multiple_objects_schema), {"Dinosaur": None}, {})

    def test_various_illegal_noop_type_renamings_error_message(self) -> None:
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(
                parse(ISS.basic_schema), {"Dinosaur": None, "Human": "Human", "Bird": "Birdie"}, {}
            )
        self.assertEqual(
            "type_renamings cannot have no-op renamings. However, the following "
            "entries exist in the type_renamings argument, which either rename a type to itself or "
            "would rename a type that doesn't exist in the schema, both of which are invalid: "
            "['Bird', 'Dinosaur', 'Human']",
            str(e.exception),
        )

    def test_swap_rename(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.multiple_objects_schema), {"Human": "Droid", "Droid": "Human"}, {}
        )
        renamed_schema_string = dedent(
            """\
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
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({"Human": "Droid", "Droid": "Human"}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_rename_into_suppressed(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.multiple_objects_schema), {"Human": None, "Droid": "Human"}, {}
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: String
            }

            type Dog {
              nickname: String
            }

            type SchemaQuery {
              Human: Human
              Dog: Dog
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({"Human": "Droid"}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_cyclic_rename(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.multiple_objects_schema),
            {"Human": "Droid", "Droid": "Dog", "Dog": "Human"},
            {},
        )
        renamed_schema_string = dedent(
            """\
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
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {"Dog": "Droid", "Human": "Dog", "Droid": "Human"}, renamed_schema.reverse_name_map
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_field_rename(self) -> None:
        renamed_schema = rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"new_id"}}})
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              new_id: String
            }

            type SchemaQuery {
              Human: Human
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({"Human": {"new_id": "id"}}, renamed_schema.reverse_field_name_map)

    def test_field_rename_includes_original_name(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.basic_schema), {}, {"Human": {"id": {"new_id", "id"}}}
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              new_id: String
            }

            type SchemaQuery {
              Human: Human
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({"Human": {"new_id": "id"}}, renamed_schema.reverse_field_name_map)

    def test_field_rename_only_affects_names_in_original_schema(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.multiple_fields_schema),
            {},
            {"Human": {"id": {"age", "id"}, "age": {"new_age"}}},
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @output(
                \"\"\"What to designate the output field generated from this property field.\"\"\"
                out_name: String!
            ) on FIELD

            type Human  {
              id: String
              name: String
              age: String
              new_age: Int
              pet: Dog
              droid: Droid
            }

            type Dog {
              id: String
              nickname: String
            }

            type Droid {
              id: String
              model: String
            }

            type SchemaQuery {
              Human: Human
              Dog: Dog
              Droid: Droid
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual(
            {"Human": {"age": "id", "new_age": "age"}}, renamed_schema.reverse_field_name_map
        )

    def test_field_renaming_illegal_noop_unused_renaming(self) -> None:
        expected_error_message = (
            "The field renamings for the following types would either rename a field to itself or "
            "would rename a field that doesn't exist in the schema, both of which are invalid. The "
            "following is a list of tuples that describes what needs to be fixed for field "
            "renamings. Each tuple is of the form (type_name, field_renamings) where type_name is "
            "the name of the type in the original schema and field_renamings is a list of the "
            "fields that would be no-op renamed: [('Human', ['nonexistent_field'])]"
        )
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(
                parse(ISS.multiple_fields_schema), {}, {"Human": {"nonexistent_field": {"foo"}}}
            )
        self.assertEqual(
            expected_error_message,
            str(e.exception),
        )

    def test_field_renaming_illegal_noop_renamed_to_self(self) -> None:
        # This would be legal if the field named "id" were 1-many renamed to something else as well
        # (e.g. renaming to "id" and "new_id" so that both fields in the renamed schema correspond
        # to the field named "id" in the original schema). However, since this is a 1-1 renaming,
        # this renaming would have no effect.
        expected_error_message = (
            "The field renamings for the following types would either rename a field to itself or "
            "would rename a field that doesn't exist in the schema, both of which are invalid. The "
            "following is a list of tuples that describes what needs to be fixed for field "
            "renamings. Each tuple is of the form (type_name, field_renamings) where type_name is "
            "the name of the type in the original schema and field_renamings is a list of the "
            "fields that would be no-op renamed: [('Human', ['id'])]"
        )
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(parse(ISS.multiple_fields_schema), {}, {"Human": {"id": {"id"}}})
        self.assertEqual(
            expected_error_message,
            str(e.exception),
        )

    def test_field_renaming_illegal_noop_rename_fields_of_nonexistent_type(self) -> None:
        expected_error_message = (
            "The following entries exist in the field_renamings argument that correspond to names "
            "of object types that either don't exist in the original schema or would get "
            "suppressed. In other words, the field renamings for each of these types would be "
            "no-ops: ['Television']"
        )
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(parse(ISS.basic_schema), {}, {"Television": {"id": {"new_id"}}})
        self.assertEqual(
            expected_error_message,
            str(e.exception),
        )

    def test_field_renaming_illegal_noop_rename_fields_of_suppressed_type(self) -> None:
        # Like field renamings for a type that doesn't exist in the schema, this is illegal because
        # the field renamings will have no effect because the type itself gets suppressed.
        expected_error_message = (
            "The following entries exist in the field_renamings argument that correspond to names "
            "of object types that either don't exist in the original schema or would get "
            "suppressed. In other words, the field renamings for each of these types would be "
            "no-ops: ['Human']"
        )
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(
                parse(ISS.multiple_objects_schema), {"Human": None}, {"Human": {"id": {"new_id"}}}
            )
        self.assertEqual(
            expected_error_message,
            str(e.exception),
        )

    def test_field_renaming_in_interfaces(self) -> None:
        with self.assertRaises(NotImplementedError):
            rename_schema(
                parse(ISS.multiple_interfaces_schema), {}, {"Character": {"id": {"new_id"}}}
            )
        with self.assertRaises(NotImplementedError):
            rename_schema(
                parse(ISS.multiple_interfaces_schema), {}, {"Character": {"id": {"id", "new_id"}}}
            )
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.multiple_interfaces_schema), {}, {"Character": {"id": set()}})
        with self.assertRaises(NotImplementedError):
            # Cannot rename Human's fields because Human implements an interface and field_renamings
            # for object types that implement interfaces isn't supported yet.
            rename_schema(parse(ISS.multiple_interfaces_schema), {}, {"Human": {"id": {"new_id"}}})
        with self.assertRaises(NotImplementedError):
            rename_schema(
                parse(ISS.multiple_interfaces_schema), {}, {"Human": {"id": {"id", "new_id"}}}
            )
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.multiple_interfaces_schema), {}, {"Human": {"id": set()}})

    def test_enum_rename(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.enum_schema), {"Droid": "NewDroid", "Height": "NewHeight"}, {}
        )
        renamed_schema_string = dedent(
            """\
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
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {"NewDroid": "Droid", "NewHeight": "Height"}, renamed_schema.reverse_name_map
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_enum_suppression(self) -> None:
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.multiple_enums_schema), {"Size": None}, {})

    def test_interface_rename(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.interface_schema), {"Kid": "NewKid", "Character": "NewCharacter"}, {}
        )
        renamed_schema_string = dedent(
            """\
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
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {"NewKid": "Kid", "NewCharacter": "Character"}, renamed_schema.reverse_name_map
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_suppress_interface_implementation(self) -> None:
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.various_types_schema), {"Giraffe": None}, {})

    def test_suppress_all_implementations_but_not_interface(self) -> None:
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.various_types_schema), {"Giraffe": None, "Human": None}, {})

    def test_suppress_interface_but_not_implementations(self) -> None:
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.various_types_schema), {"Character": None}, {})

    def test_suppress_interface_and_all_implementations(self) -> None:
        with self.assertRaises(NotImplementedError):
            rename_schema(
                parse(ISS.various_types_schema),
                {"Giraffe": None, "Character": None, "Human": None},
                {},
            )

    def test_multiple_interfaces_rename(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.multiple_interfaces_schema),
            {"Human": "NewHuman", "Character": "NewCharacter", "Creature": "NewCreature"},
            {},
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            interface NewCharacter {
              id: String
            }

            interface NewCreature {
              age: Int
            }

            type NewHuman implements NewCharacter & NewCreature {
              id: String
              age: Int
            }

            type SchemaQuery {
              NewCharacter: NewCharacter
              NewCreature: NewCreature
              NewHuman: NewHuman
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {"NewHuman": "Human", "NewCharacter": "Character", "NewCreature": "Creature"},
            renamed_schema.reverse_name_map,
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_scalar_rename(self) -> None:
        renamed_schema = rename_schema(parse(ISS.scalar_schema), {"Date": "NewDate"}, {})
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              birthday: NewDate
            }

            scalar NewDate

            type SchemaQuery {
              Human: Human
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {"NewDate": "Date"},
            renamed_schema.reverse_name_map,
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_scalar_suppress(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.scalar_schema), {"Date": None}, {"Human": {"birthday": set()}}
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
            }

            type SchemaQuery {
              Human: Human
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {},
            renamed_schema.reverse_name_map,
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_builtin_rename(self) -> None:
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.list_schema), {"String": "NewString"}, {})

    def test_union_rename(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.union_schema), {"HumanOrDroid": "NewHumanOrDroid", "Droid": "NewDroid"}, {}
        )
        renamed_schema_string = dedent(
            """\
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
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {"NewDroid": "Droid", "NewHumanOrDroid": "HumanOrDroid"},
            renamed_schema.reverse_name_map,
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_entire_union_suppress(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.union_schema), {"HumanOrDroid": None, "Droid": "NewDroid"}, {}
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: String
            }

            type NewDroid {
              id: String
            }

            type SchemaQuery {
              Human: Human
              NewDroid: NewDroid
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {"NewDroid": "Droid"},
            renamed_schema.reverse_name_map,
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_union_member_suppress(self) -> None:
        renamed_schema = rename_schema(parse(ISS.union_schema), {"Droid": None}, {})
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: String
            }

            union HumanOrDroid = Human

            type SchemaQuery {
              Human: Human
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {},
            renamed_schema.reverse_name_map,
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_list_rename(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.list_schema),
            {
                "Droid": "NewDroid",
                "Character": "NewCharacter",
                "Height": "NewHeight",
            },
            {},
        )
        renamed_schema_string = dedent(
            """\
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
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {
                "NewCharacter": "Character",
                "NewDroid": "Droid",
                "NewHeight": "Height",
            },
            renamed_schema.reverse_name_map,
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_non_null_rename(self) -> None:
        renamed_schema = rename_schema(parse(ISS.non_null_schema), {"Dog": "NewDog"}, {})
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type NewDog {
              id: String!
              friend: NewDog!
            }

            type Cat {
              id: String
            }

            type SchemaQuery {
              NewDog: NewDog!
              Cat: Cat
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({"NewDog": "Dog"}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_non_null_suppress(self) -> None:
        renamed_schema = rename_schema(parse(ISS.non_null_schema), {"Dog": None}, {})
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Cat {
              id: String
            }

            type SchemaQuery {
              Cat: Cat
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_directive_renaming_illegal_noop(self) -> None:
        # This renaming is illegal because directives can't be renamed, so the
        # "stitch" -> "NewStitch" mapping is a no-op
        with self.assertRaises(NoOpRenamingError):
            rename_schema(
                parse(ISS.directive_schema),
                {
                    "stitch": "NewStitch",
                },
                {},
            )

    def test_query_type_field_argument_illegal_noop(self) -> None:
        # This renaming is illegal because query type field arguments can't be renamed, so the
        # "id" -> "Id" mapping is a no-op
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Human(id: String!): Human
            }

            type Human {
              name: String
            }
        """
        )
        with self.assertRaises(NoOpRenamingError):
            rename_schema(parse(schema_string), {"id": "Id"}, {})

    def test_clashing_type_rename(self) -> None:
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
              Human1: Human1
              Human2: Human2
            }
        """
        )

        with self.assertRaises(SchemaRenameNameConflictError):
            rename_schema(parse(schema_string), {"Human1": "Human", "Human2": "Human"}, {})

    def test_clashing_type_single_rename(self) -> None:
        schema_string = dedent(
            """\
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
        """
        )

        with self.assertRaises(SchemaRenameNameConflictError):
            rename_schema(parse(schema_string), {"Human2": "Human"}, {})

    def test_clashing_scalar_type_rename(self) -> None:
        schema_string = dedent(
            """\
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
        """
        )

        with self.assertRaises(SchemaRenameNameConflictError):
            rename_schema(parse(schema_string), {"Human": "SCALAR"}, {})

    def test_builtin_type_conflict_rename(self) -> None:
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: String
            }

            type SchemaQuery {
              Human: Human
            }
        """
        )

        with self.assertRaises(SchemaRenameNameConflictError):
            rename_schema(parse(schema_string), {"Human": "String"}, {})

    def test_multiple_naming_conflicts(self) -> None:
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Dog {
              nickname: String
              age: Int
            }

            type Cat {
              nickname: String
              age: Int
            }

            type Droid {
              id: String
              friends: [Droid]
            }

            type Human {
              id: String
              name: String
              age: Int
            }

            type SchemaQuery {
              Dog: Dog
              Cat: Cat
              Droid: Droid
              Human: Human
            }
        """
        )

        clashing_type_rename_error_message = (
            "Applying the renaming would produce a schema in which multiple types have the "
            "same name, which is an illegal schema state. To fix this, modify the type_renamings "
            "argument of rename_schema to ensure that no two types in the renamed schema have "
            "the same name. The following is a list of tuples that describes what needs to be "
            "fixed. Each tuple is of the form (new_type_name, original_schema_type_names) "
            "where new_type_name is the type name that would appear in the new schema and "
            "original_schema_type_names is a list of types in the original schema that get "
            "mapped to new_type_name: [('Droid', ['Dog', 'Droid', 'Human'])]"
        )
        type_rename_to_builtin_error_message = (
            "Applying the renaming would rename type(s) to a name already used by a built-in "
            "GraphQL scalar type. To fix this, ensure that no type name is mapped to a "
            "scalar's name. The following is a list of tuples that describes what needs to be "
            "fixed. Each tuple is of the form (type_name, scalar_name) where type_name is the "
            "original name of the type and scalar_name is the name of the scalar that the "
            "type would be renamed to: [('Cat', 'String')]"
        )
        clashing_field_rename_error_message = (
            "Applying the renaming would produce a schema in which multiple fields belonging "
            "to the same type have the same name, which is an illegal schema state. To fix "
            "this, modify the field_renamings argument of rename_schema to ensure that within "
            "each type in the renamed schema, no two fields have the same name. The following "
            "is a list of tuples that describes what needs to be fixed. "
            "Each tuple is of the form "
            "(type_name, [(desired_field_name, original_field_names),...]) where type_name is "
            "the type name that would appear in the original schema, desired_field_name is "
            "the name of a field in the new schema, and original_field_names is a list of the "
            "names of all the fields in the original schema that would be renamed to "
            "desired_field_name: [('Human', [('name', ['id', 'name'])])]"
        )

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(parse(schema_string), {"Human": "Droid", "Dog": "Droid"}, {})
        self.assertEqual(
            clashing_type_rename_error_message,
            str(e.exception),
        )

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(
                parse(schema_string), {"Cat": "String"}, {"Human": {"id": {"id", "name"}}}
            )
        self.assertEqual(
            type_rename_to_builtin_error_message + "\n" + clashing_field_rename_error_message,
            str(e.exception),
        )

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(
                parse(schema_string),
                {},
                {"Human": {"id": {"id", "name"}, "name": {"name", "new_name"}}},
            )
        self.assertEqual(
            clashing_field_rename_error_message,
            str(e.exception),
        )

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(
                parse(schema_string),
                {"Cat": "String", "Human": "Droid", "Dog": "Droid"},
                {"Human": {"id": {"id", "name"}}},
            )
        self.assertEqual(
            clashing_type_rename_error_message
            + "\n"
            + type_rename_to_builtin_error_message
            + "\n"
            + clashing_field_rename_error_message,
            str(e.exception),
        )

    def test_invalid_name_error_message(self) -> None:
        with self.assertRaises(InvalidNameError) as e:
            rename_schema(
                parse(ISS.multiple_objects_schema),
                {"Human": "0Human", "Dog": "__Dog", "Droid": "NewDroid"},
                {
                    "Human": {"name": {"0name"}},
                    "Droid": {"id": {"id!"}},
                    "Dog": {"nickname": {"__nickname"}},
                },
            )
        self.assertEqual(
            "Applying the renaming would involve names that are not valid, non-reserved "
            "GraphQL names. Valid, non-reserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for type "
            "renamings. Each tuple is of the form (original_name, invalid_new_name) where "
            "original_name is the name in the original schema and invalid_new_name is what "
            "original_name would be renamed to: [('Dog', '__Dog'), ('Human', '0Human')]\n"
            "The following is a list of tuples that describes what needs to be fixed for "
            "field renamings. Each tuple is of the form (type_name, field_renamings) "
            "where type_name is the name of the type in the original schema and "
            "field_renamings is a list of tuples mapping the original field name to the "
            "invalid GraphQL name it would be renamed to: [('Dog', [('nickname', '__nickname')]), "
            "('Droid', [('id', 'id!')]), ('Human', [('name', '0name')])]",
            str(e.exception),
        )

    def test_illegal_rename_start_with_number(self) -> None:
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "0Human"}, {})
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"0id"}}})

    def test_illegal_rename_contains_illegal_char(self) -> None:
        # Test types
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "Human!"}, {})
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "H-uman"}, {})
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "H.uman"}, {})
        # Test fields
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"id!"}}})
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"i-d"}}})
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"i.d"}}})

    def test_illegal_rename_starts_with_double_underscore(self) -> None:
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "__Human"}, {})
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"__id"}}})

    def test_illegal_rename_to_reserved_name_type(self) -> None:
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "__Type"}, {})
        with self.assertRaises(InvalidNameError):
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"__Type"}}})

    def test_suppress_every_type(self) -> None:
        with self.assertRaises(SchemaTransformError):
            rename_schema(parse(ISS.basic_schema), {"Human": None}, {})

    def test_suppress_all_union_members(self) -> None:
        with self.assertRaises(CascadingSuppressionError):
            # Can't use ISS.union_schema here because suppressing all the members of the union would
            # mean suppressing every type in general, which means we couldn't be sure that
            # suppressing every member of a union specifically was raising the
            # CascadingSuppressionError.
            rename_schema(parse(ISS.extended_union_schema), {"Human": None, "Droid": None}, {})

    def test_field_still_depends_on_suppressed_type(self) -> None:
        with self.assertRaises(CascadingSuppressionError):
            rename_schema(
                parse(ISS.multiple_fields_schema), {"Dog": None}, {}
            )  # The type named Human contains a field of type Dog.

    def test_suppress_field_prevent_cascading_suppression_error(self) -> None:
        renamed_schema = rename_schema(
            parse(ISS.multiple_fields_schema), {"Dog": None}, {"Human": {"pet": set()}}
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @output(
                \"\"\"What to designate the output field generated from this property field.\"\"\"
                out_name: String!
            ) on FIELD

            type Human  {
              id: String
              name: String
              age: Int
              droid: Droid
            }

            type Droid {
              id: String
              model: String
            }

            type SchemaQuery {
              Human: Human
              Droid: Droid
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_field_of_suppressed_type_in_suppressed_type(self) -> None:
        # The schema contains an object type that contains a field of the type Human. Normally,
        # suppressing the type named Human would cause a CascadingSuppressionError because the
        # resulting schema would still have fields of the type Human. Here, however, only the type
        # named Human contains such a field, so suppressing the type Human produces a legal schema.
        renamed_schema = rename_schema(parse(ISS.recursive_field_schema), {"Human": None}, {})
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Dog {
              nickname: String
            }

            type SchemaQuery {
              Dog: Dog
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_field_in_list_still_depends_on_suppressed_type(self) -> None:
        with self.assertRaises(CascadingSuppressionError):
            rename_schema(parse(ISS.list_schema), {"Height": None}, {})

    def test_suppress_every_field_in_type(self) -> None:
        with self.assertRaises(CascadingSuppressionError):
            rename_schema(
                parse(ISS.multiple_fields_schema), {}, {"Droid": {"id": set(), "model": set()}}
            )
