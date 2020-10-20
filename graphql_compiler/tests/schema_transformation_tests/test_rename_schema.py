# Copyright 2019-present Kensho Technologies, LLC.
from textwrap import dedent
from typing import Optional, Set
import unittest

from graphql import GraphQLSchema, build_ast_schema, parse
from graphql.language.printer import print_ast
from graphql.language.visitor import QUERY_DOCUMENT_KEYS
from graphql.pyutils import snake_to_camel

from ...schema_transformation.rename_schema import (
    FieldRenamingMapping,
    FieldRenamingsForParticularType,
    RenameSchemaTypesVisitor,
    TypeRenamingMapping,
    rename_schema,
)
from ...schema_transformation.utils import (
    CascadingSuppressionError,
    NoOpRenamingError,
    SchemaRenameInvalidNameError,
    SchemaRenameNameConflictError,
    SchemaTransformError,
    builtin_scalar_type_names,
    get_custom_scalar_names,
)
from ...typedefs import Protocol
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
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(parse(ISS.basic_schema), {"Dinosaur": "NewDinosaur"}, {})
        self.assertEqual(
            "type_renamings is iterable, so it cannot have no-op renamings. However, the following "
            "entries exist in the type_renamings argument, which either rename a type to itself or "
            "would rename a type that doesn't exist in the schema, both of which are invalid: "
            "['Dinosaur']",
            str(e.exception),
        )

    def test_rename_legal_noop_unused_renaming(self) -> None:
        # Unlike with test_rename_illegal_noop_unused_renaming, here type_renamings is not
        # iterable. As a result, this renaming is technically legal but it is inadvisable to
        # write a renaming like this since the intended "Dinosaur" -> "NewDinosaur" mapping is
        # unused and will silently do nothing when applied to the given schema.
        class RenameMapping:
            def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
                """Define mapping for renaming object."""
                if key == "Dinosaur":
                    return "NewDinosaur"
                return key

        renamed_schema = rename_schema(parse(ISS.basic_schema), RenameMapping(), {})
        compare_schema_texts_order_independently(
            self, ISS.basic_schema, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_rename_illegal_noop_renamed_to_self(self) -> None:
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(parse(ISS.basic_schema), {"Human": "Human"}, {})
        self.assertEqual(
            "type_renamings is iterable, so it cannot have no-op renamings. However, the following "
            "entries exist in the type_renamings argument, which either rename a type to itself or "
            "would rename a type that doesn't exist in the schema, both of which are invalid: "
            "['Human']",
            str(e.exception),
        )

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
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(parse(ISS.multiple_objects_schema), {"Dinosaur": None}, {})
        self.assertEqual(
            "type_renamings is iterable, so it cannot have no-op renamings. However, the following "
            "entries exist in the type_renamings argument, which either rename a type to itself or "
            "would rename a type that doesn't exist in the schema, both of which are invalid: "
            "['Dinosaur']",
            str(e.exception),
        )

    def test_suppress_legal_noop_unused_suppression(self) -> None:
        # Unlike with test_suppress_illegal_noop_unused_suppression, here type_renamings is not
        # iterable. As a result, this renaming is technically legal but it is inadvisable to
        # write a renaming like this since the intended "Dinosaur" -> None mapping is unused and
        # will silently do nothing when applied to the given schema.
        class SuppressMapping:
            def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
                """Define mapping for renaming object."""
                if key == "Dinosaur":
                    return None
                return key

        renamed_schema = rename_schema(parse(ISS.multiple_objects_schema), SuppressMapping(), {})
        compare_schema_texts_order_independently(
            self, ISS.multiple_objects_schema, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_various_illegal_noop_type_renamings(self) -> None:
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(
                parse(ISS.basic_schema), {"Dinosaur": None, "Human": "Human", "Bird": "Birdie"}, {}
            )
        self.assertEqual(
            "type_renamings is iterable, so it cannot have no-op renamings. However, the following "
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
            parse(ISS.many_fields_schema), {}, {"Human": {"id": {"age", "id"}, "age": {"new_age"}}}
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              name: String
              age: String
              new_age: Int
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
        self.assertEqual(
            {"Human": {"age": "id", "new_age": "age"}}, renamed_schema.reverse_field_name_map
        )

    def test_field_renaming_illegal_noop_unused_renaming(self) -> None:
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(parse(ISS.many_fields_schema), {}, {"Human": {"pet": {"new_pet"}}})
        self.assertEqual(
            f"The field renamings for the following types in field_renamings are iterable, so they "
            f"cannot cannot have no-op renamings. However, some of these renamings would either rename a field to itself or "
            f"would rename a field that doesn't exist in the schema, both of which are invalid. "
            f"The following is a list of tuples that describes what needs to be fixed for "
            f"field renamings. Each tuple is of the form (type_name, field_renamings) "
            f"where type_name is the name of the type in the original schema and "
            f"field_renamings is a list of the fields that would be no-op renamed: [('Human', ['pet'])]",
            str(e.exception),
        )

    def test_field_renaming_legal_noop_unused_renaming(self) -> None:
        # Unlike with test_field_renaming_illegal_noop_unused_renaming, here field_renamings is not iterable.
        # As a result, this renaming is technically legal but it is inadvisable to write a
        # renaming like this since the intended "pet" -> "new_pet" mapping is unused and will
        # silently do nothing when applied to ISS.many_fields_schema.

        # Unfortunately this can't be a nested class because mypy has a bug and it's safer to make
        # the classes slightly less organized in exchange for being able to use mypy for here.
        # https://github.com/python/mypy/issues/6393
        class FieldNoOpRenamings:
            def get(self, field_name: str, default: Set[str]) -> Set[str]:
                """Define field renaming to use."""
                if field_name == "pet":
                    return {"new_pet"}
                return {field_name}

        class FieldRenamingNoOpMapping:
            def get(
                self,
                type_name: str,
                default_field_renamings: Optional[FieldRenamingsForParticularType],
            ) -> Optional[FieldRenamingsForParticularType]:
                if type_name == "Human":
                    return FieldNoOpRenamings()
                return None

        renamed_schema = rename_schema(
            parse(ISS.many_fields_schema), {}, FieldRenamingNoOpMapping()
        )
        compare_schema_texts_order_independently(
            self, ISS.many_fields_schema, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_field_renaming_illegal_noop_renamed_to_self(self) -> None:
        # This would be legal if the field named "id" were 1-many renamed to something else as well
        # (e.g. renaming to "id" and "new_id" so that both fields in the renamed schema correspond
        # to the field named "id" in the original schema). However, since this is a 1-1 renaming,
        # this renaming would have no effect.
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(parse(ISS.many_fields_schema), {}, {"Human": {"id": {"id"}}})
        self.assertEqual(
            f"The field renamings for the following types in field_renamings are iterable, so they "
            f"cannot cannot have no-op renamings. However, some of these renamings would either rename a field to itself or "
            f"would rename a field that doesn't exist in the schema, both of which are invalid. "
            f"The following is a list of tuples that describes what needs to be fixed for "
            f"field renamings. Each tuple is of the form (type_name, field_renamings) "
            f"where type_name is the name of the type in the original schema and "
            f"field_renamings is a list of the fields that would be no-op renamed: [('Human', ['id'])]",
            str(e.exception),
        )

    def test_field_renaming_illegal_noop_rename_fields_of_nonexistent_type(self) -> None:
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(parse(ISS.basic_schema), {}, {"Television": {"id": {"new_id"}}})
        self.assertEqual(
            "field_renamings is iterable, so it cannot have no-op renamings. However, the following entries exist in the field_renamings argument that correspond to names of object types that either don't exist in the original schema or would get suppressed. In other words, the field renamings for each of these types would be no-ops: ['Television']",
            str(e.exception),
        )

    def test_field_renaming_illegal_noop_rename_fields_of_suppressed_type(self) -> None:
        # Like field renamings for a type that doesn't exist in the schema, this is illegal because the field renamings will have no effect because the type itself gets suppressed.
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(
                parse(ISS.multiple_objects_schema), {"Human": None}, {"Human": {"id": {"new_id"}}}
            )
        self.assertEqual(
            f"field_renamings is iterable, so it cannot have no-op renamings. However, the following entries exist in the field_renamings argument that correspond to names of object types that either don't exist in the original schema or would get suppressed. In other words, the field renamings for each of these types would be no-ops: ['Human']",
            str(e.exception),
        )

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
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.scalar_schema), {"Date": "NewDate"}, {})

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
        # "stitch" -> "NewStitch" mapping is a no-op which is not allowed for iterable type_renamings.
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(
                parse(ISS.directive_schema),
                {
                    "stitch": "NewStitch",
                },
                {},
            )
        self.assertEqual(
            "type_renamings is iterable, so it cannot have no-op renamings. However, the following "
            "entries exist in the type_renamings argument, which either rename a type to itself or "
            "would rename a type that doesn't exist in the schema, both of which are invalid: "
            "['stitch']",
            str(e.exception),
        )

    def test_directive_renaming_legal_noop(self) -> None:
        # Unlike with test_directive_renaming_illegal_noop, here type_renamings is not iterable.
        # As a result, this renaming is technically legal but it is inadvisable to write a
        # renaming like this since directives cannot be renamed so the intended
        # "stitch" -> "NewStitch" mapping is unused and will silently do nothing when applied to
        #  ISS.directive_schema.
        class DirectiveRenamingMapping:
            def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
                """Define mapping for renaming object."""
                if key == "stitch":
                    return "NewStitch"
                return key

        renamed_schema = rename_schema(parse(ISS.directive_schema), DirectiveRenamingMapping(), {})
        compare_schema_texts_order_independently(
            self, ISS.directive_schema, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

    def test_query_type_field_argument_illegal_noop(self) -> None:
        # This renaming is illegal because query type field arguments can't be renamed, so the
        # "id" -> "Id" mapping is a no-op which is not allowed for iterable type_renamings.
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
        with self.assertRaises(NoOpRenamingError) as e:
            rename_schema(parse(schema_string), {"id": "Id"}, {})
        self.assertEqual(
            "type_renamings is iterable, so it cannot have no-op renamings. However, the following "
            "entries exist in the type_renamings argument, which either rename a type to itself or "
            "would rename a type that doesn't exist in the schema, both of which are invalid: "
            "['id']",
            str(e.exception),
        )

    def test_query_type_field_argument_legal_noop(self) -> None:
        # Unlike with test_query_type_field_argument_illegal_noop, here type_renamings is not
        # iterable. As a result, this renaming is technically legal but it is inadvisable to
        # write a renaming like this since the intended "id" -> "Id" mapping is unused and will
        # silently do nothing when applied to the given schema.
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

        class QueryTypeFieldArgumentMapping:
            def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
                """Define mapping for renaming object."""
                if key == "id":
                    return "Id"
                return key

        renamed_schema = rename_schema(parse(schema_string), QueryTypeFieldArgumentMapping(), {})
        compare_schema_texts_order_independently(
            self, schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual({}, renamed_schema.reverse_name_map)
        self.assertEqual({}, renamed_schema.reverse_field_name_map)

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

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(parse(schema_string), {"Human1": "Human", "Human2": "Human"}, {})
        self.assertEqual(
            "Applying the renaming would produce a schema in which multiple types have the "
            "same name, which is an illegal schema state. To fix this, modify the type_renamings "
            "argument of rename_schema to ensure that no two types in the renamed schema have "
            "the same name. The following is a list of tuples that describes what needs to be "
            "fixed. Each tuple is of the form (new_type_name, original_schema_type_names) "
            "where new_type_name is the type name that would appear in the new schema and "
            "original_schema_type_names is a list of types in the original schema that get "
            "mapped to new_type_name: [('Human', ['Human1', 'Human2'])]",
            str(e.exception),
        )

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

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(parse(schema_string), {"Human2": "Human"}, {})
        self.assertEqual(
            "Applying the renaming would produce a schema in which multiple types have the "
            "same name, which is an illegal schema state. To fix this, modify the type_renamings "
            "argument of rename_schema to ensure that no two types in the renamed schema have "
            "the same name. The following is a list of tuples that describes what needs to be "
            "fixed. Each tuple is of the form (new_type_name, original_schema_type_names) "
            "where new_type_name is the type name that would appear in the new schema and "
            "original_schema_type_names is a list of types in the original schema that get "
            "mapped to new_type_name: [('Human', ['Human', 'Human2'])]",
            str(e.exception),
        )

    def test_clashing_type_one_unchanged_rename(self) -> None:
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

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(parse(schema_string), {"Human": "Human3", "Human2": "Human3"}, {})
        self.assertEqual(
            "Applying the renaming would produce a schema in which multiple types have the "
            "same name, which is an illegal schema state. To fix this, modify the type_renamings "
            "argument of rename_schema to ensure that no two types in the renamed schema have "
            "the same name. The following is a list of tuples that describes what needs to be "
            "fixed. Each tuple is of the form (new_type_name, original_schema_type_names) "
            "where new_type_name is the type name that would appear in the new schema and "
            "original_schema_type_names is a list of types in the original schema that get "
            "mapped to new_type_name: [('Human3', ['Human', 'Human2'])]",
            str(e.exception),
        )

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

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(parse(schema_string), {"Human": "SCALAR"}, {})
        self.assertEqual(
            "Applying the renaming would produce a schema in which multiple types have the "
            "same name, which is an illegal schema state. To fix this, modify the type_renamings "
            "argument of rename_schema to ensure that no two types in the renamed schema have "
            "the same name. The following is a list of tuples that describes what needs to be "
            "fixed. Each tuple is of the form (new_type_name, original_schema_type_names) "
            "where new_type_name is the type name that would appear in the new schema and "
            "original_schema_type_names is a list of types in the original schema that get "
            "mapped to new_type_name: [('SCALAR', ['Human', 'SCALAR'])]",
            str(e.exception),
        )

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

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(parse(schema_string), {"Human": "String"}, {})
        self.assertEqual(
            "Applying the renaming would rename type(s) to a name already used by a built-in "
            "GraphQL scalar type. To fix this, ensure that no type name is mapped to a "
            "scalar's name. The following is a list of tuples that describes what needs to be "
            "fixed. Each tuple is of the form (type_name, scalar_name) where type_name is the "
            "original name of the type and scalar_name is the name of the scalar that the "
            "type would be renamed to: [('Human', 'String')]",
            str(e.exception),
        )

    def test_multiple_naming_conflicts(self) -> None:
        schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Cat {
              nickname: String
            }

            type Dog {
              nickname: String
            }

            type Human {
              id: String
            }

            type SchemaQuery {
              Human: Human
            }
        """
        )

        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(parse(schema_string), {"Human": "String", "Dog": "Cat"}, {})
        self.assertEqual(
            "Applying the renaming would produce a schema in which multiple types have the "
            "same name, which is an illegal schema state. To fix this, modify the type_renamings "
            "argument of rename_schema to ensure that no two types in the renamed schema have "
            "the same name. The following is a list of tuples that describes what needs to be "
            "fixed. Each tuple is of the form (new_type_name, original_schema_type_names) "
            "where new_type_name is the type name that would appear in the new schema and "
            "original_schema_type_names is a list of types in the original schema that get "
            "mapped to new_type_name: [('Cat', ['Cat', 'Dog'])]\n"
            "Applying the renaming would rename type(s) to a name already used by a built-in "
            "GraphQL scalar type. To fix this, ensure that no type name is mapped to a "
            "scalar's name. The following is a list of tuples that describes what needs to be "
            "fixed. Each tuple is of the form (type_name, scalar_name) where type_name is the "
            "original name of the type and scalar_name is the name of the scalar that the "
            "type would be renamed to: [('Human', 'String')]",
            str(e.exception),
        )

    def test_clashing_field_rename(self) -> None:
        with self.assertRaises(SchemaRenameNameConflictError) as e:
            rename_schema(parse(ISS.many_fields_schema), {}, {"Human": {"name": {"name", "id"}}})
        self.assertEqual(
            "Applying the renaming would produce a schema in which multiple fields belonging to the same type have the same name, which is an illegal schema state. To fix this, modify the field_renamings argument of rename_schema to ensure that within each type in the renamed schema, no two fields have the same name. The following is a list of tuples that describes what needs to be fixed. Each tuple is of the form (type_name, field_conflicts) where type_name is the type name that would appear in the original schema and field_conflicts is a list of tuples of the form (desired_field_name, original_field_names) where desired_field_name is the name of the field in the new schema and original_field_names is a list of the names of all the fields in the original schema that would be renamed to desired_field_name: [('Human', [('id', ['id', 'name'])])]",
            str(e.exception),
        )

    def test_illegal_rename_type_start_with_number(self) -> None:
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {"Human": "0Human"}, {})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for type "
            "renamings. Each tuple is of the form (original_name, invalid_new_name) where "
            "original_name is the name in the original schema and invalid_new_name is what "
            "original_name would be renamed to: [('Human', '0Human')]",
            str(e.exception),
        )

    def test_illegal_rename_field_start_with_number(self) -> None:
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"0id"}}})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for "
            "field renamings. Each tuple is of the form (type_name, field_renamings) "
            "where type_name is the name of the type in the original schema and "
            "field_renamings is a list of tuples mapping the original field name to the "
            "invalid GraphQL name it would be renamed to: [('Human', [('id', '0id')])]",
            str(e.exception),
        )

    def test_illegal_rename_type_contains_illegal_char(self) -> None:
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {"Human": "Human!"}, {})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for type "
            "renamings. Each tuple is of the form (original_name, invalid_new_name) where "
            "original_name is the name in the original schema and invalid_new_name is what "
            "original_name would be renamed to: [('Human', 'Human!')]",
            str(e.exception),
        )
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {"Human": "H-uman"}, {})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for type "
            "renamings. Each tuple is of the form (original_name, invalid_new_name) where "
            "original_name is the name in the original schema and invalid_new_name is what "
            "original_name would be renamed to: [('Human', 'H-uman')]",
            str(e.exception),
        )
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {"Human": "H.uman"}, {})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for type "
            "renamings. Each tuple is of the form (original_name, invalid_new_name) where "
            "original_name is the name in the original schema and invalid_new_name is what "
            "original_name would be renamed to: [('Human', 'H.uman')]",
            str(e.exception),
        )

    def test_illegal_rename_field_contains_illegal_char(self) -> None:
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"Human!"}}})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for "
            "field renamings. Each tuple is of the form (type_name, field_renamings) "
            "where type_name is the name of the type in the original schema and "
            "field_renamings is a list of tuples mapping the original field name to the "
            "invalid GraphQL name it would be renamed to: [('Human', [('id', 'Human!')])]",
            str(e.exception),
        )
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"H-uman"}}})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for "
            "field renamings. Each tuple is of the form (type_name, field_renamings) "
            "where type_name is the name of the type in the original schema and "
            "field_renamings is a list of tuples mapping the original field name to the "
            "invalid GraphQL name it would be renamed to: [('Human', [('id', 'H-uman')])]",
            str(e.exception),
        )
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"H.uman"}}})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for "
            "field renamings. Each tuple is of the form (type_name, field_renamings) "
            "where type_name is the name of the type in the original schema and "
            "field_renamings is a list of tuples mapping the original field name to the "
            "invalid GraphQL name it would be renamed to: [('Human', [('id', 'H.uman')])]",
            str(e.exception),
        )

    def test_illegal_rename_type_to_double_underscore(self) -> None:
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {"Human": "__Human"}, {})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for type "
            "renamings. Each tuple is of the form (original_name, invalid_new_name) where "
            "original_name is the name in the original schema and invalid_new_name is what "
            "original_name would be renamed to: [('Human', '__Human')]",
            str(e.exception),
        )

    def test_illegal_rename_field_to_double_underscore(self) -> None:
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"__id"}}})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for "
            "field renamings. Each tuple is of the form (type_name, field_renamings) "
            "where type_name is the name of the type in the original schema and "
            "field_renamings is a list of tuples mapping the original field name to the "
            "invalid GraphQL name it would be renamed to: [('Human', [('id', '__id')])]",
            str(e.exception),
        )

    def test_illegal_rename_type_to_reserved_name_type(self) -> None:
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {"Human": "__Type"}, {})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for type "
            "renamings. Each tuple is of the form (original_name, invalid_new_name) where "
            "original_name is the name in the original schema and invalid_new_name is what "
            "original_name would be renamed to: [('Human', '__Type')]",
            str(e.exception),
        )

    def test_illegal_rename_field_to_reserved_name_type(self) -> None:
        with self.assertRaises(SchemaRenameInvalidNameError) as e:
            rename_schema(parse(ISS.basic_schema), {}, {"Human": {"id": {"__Type"}}})
        self.assertEqual(
            "Applying the type renaming would rename types with names that are not valid, unreserved "
            "GraphQL names. Valid, unreserved GraphQL names must consist of only alphanumeric "
            "characters and underscores, must not start with a numeric character, and must not "
            "start with double underscores.\n"
            "The following is a list of tuples that describes what needs to be fixed for "
            "field renamings. Each tuple is of the form (type_name, field_renamings) "
            "where type_name is the name of the type in the original schema and "
            "field_renamings is a list of tuples mapping the original field name to the "
            "invalid GraphQL name it would be renamed to: [('Human', [('id', '__Type')])]",
            str(e.exception),
        )

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

    def test_rename_using_dict_like_prefixer_class(self) -> None:
        class PrefixNewDict:
            def __init__(self, schema: GraphQLSchema):
                self.schema = schema
                super().__init__()

            def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
                """Define mapping for renaming object."""
                if key in get_custom_scalar_names(self.schema) or key in builtin_scalar_type_names:
                    # Making an exception for scalar types because renaming and suppressing them
                    # hasn't been implemented yet
                    return key
                return "New" + key

        schema = parse(ISS.various_types_schema)
        renamed_schema = rename_schema(schema, PrefixNewDict(build_ast_schema(schema)), {})
        renamed_schema_string = dedent(
            """\
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

            type NewDog {
              nickname: String
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type SchemaQuery {
              NewHuman: NewHuman
              NewGiraffe: NewGiraffe
              NewDog: NewDog
            }
        """
        )
        compare_schema_texts_order_independently(
            self, renamed_schema_string, print_ast(renamed_schema.schema_ast)
        )
        self.assertEqual(
            {
                "NewCharacter": "Character",
                "NewGiraffe": "Giraffe",
                "NewHeight": "Height",
                "NewHuman": "Human",
                "NewDog": "Dog",
            },
            renamed_schema.reverse_name_map,
        )
        self.assertEqual({}, renamed_schema.reverse_field_name_map)
