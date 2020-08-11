# Copyright 2019-present Kensho Technologies, LLC.
from ast import literal_eval
from textwrap import dedent
from typing import Dict, Set
import unittest

from graphql import GraphQLSchema, build_ast_schema, parse
from graphql.language.printer import print_ast
from graphql.language.visitor import QUERY_DOCUMENT_KEYS
from graphql.pyutils import snake_to_camel

from ...schema_transformation.rename_schema import RenameSchemaTypesVisitor, rename_schema
from ...schema_transformation.utils import (
    CascadingSuppressionError,
    InvalidTypeNameError,
    SchemaRenameNameConflictError,
    SchemaTransformError,
    builtin_scalar_types,
    get_custom_scalar_names,
)
from .input_schema_strings import InputSchemaStrings as ISS


def check_rename_conflict_error_message(
    expected_name_conflicts: Dict[str, Set[str]],
    expected_renamed_to_builtin_scalar_conflicts: Dict[str, str],
    error: SchemaRenameNameConflictError,
) -> bool:
    """Check SchemaRenameNameConflictError's error message contains the expected data structures.

    Since there are no guarantees for the order in which GraphQL-core's visit function visits nodes
    at the same depth in the schema AST, SchemaRenameNameConflictError's __str__ method is not
    fully deterministic. This function checks that the __str__ method contains valid string
    representations of SchemaRenameNameConflictError's name_conflicts and
    renamed_to_builtin_scalar_conflicts fields.

    Args:
        expected_name_conflicts: expected name conflicts from renaming
        expected_renamed_to_builtin_scalar_conflicts: expected conflicts from renaming to built-in
                                                      scalar types
        error: exception object raised during schema renaming due to name conflict

    Returns:
        true iff the expected error message and actual error message are equivalent.
    """
    name_conflicts_prefix = (
        "Applying the renaming would produce a schema in which multiple types have the "
        "same name, which is an illegal schema state. The name_conflicts dict describes "
        "these problems. For each key k in name_conflicts, name_conflicts[k] is the set "
        "of types in the original schema that get mapped to k in the new schema. To fix "
        "this, modify the renamings argument of rename_schema to ensure that no two types "
        "in the renamed schema have the same name. name_conflicts: "
    )
    renamed_to_builtin_scalar_conflicts_prefix = (
        "Applying the renaming would rename type(s) to a name already used by a built-in "
        "GraphQL scalar type. To fix this, ensure that no type name is mapped to a "
        "scalar's name. The following dict maps each to-be-renamed type to the scalar "
        "name it was mapped to: "
    )
    actual_error_message = str(error)
    name_conflicts_part = None
    renamed_to_builtin_scalar_conflicts_part = None
    if expected_name_conflicts and expected_renamed_to_builtin_scalar_conflicts:
        name_conflicts_part, renamed_to_builtin_scalar_conflicts_part = actual_error_message.split(
            "\n"
        )
    elif expected_name_conflicts:
        name_conflicts_part = actual_error_message
    elif expected_renamed_to_builtin_scalar_conflicts:
        renamed_to_builtin_scalar_conflicts_part = actual_error_message
    else:
        raise AssertionError(
            "Illegal for SchemaRenameNameConflictError to have all arguments as empty dicts"
        )

    if name_conflicts_part:
        if not name_conflicts_part.startswith(name_conflicts_prefix):
            return False
        # Then check the string representation of name_conflicts
        name_conflicts_representation = name_conflicts_part[len(name_conflicts_prefix) :]
        try:
            if literal_eval(name_conflicts_representation) != expected_name_conflicts:
                return False
        except SyntaxError:
            # in case it's syntactically invalid
            return False
    if renamed_to_builtin_scalar_conflicts_part:
        if not renamed_to_builtin_scalar_conflicts_part.startswith(
            renamed_to_builtin_scalar_conflicts_prefix
        ):
            return False
        # Then check the string representation of renamed_to_builtin_scalar_conflicts
        renamed_to_builtin_scalar_conflicts_representation = renamed_to_builtin_scalar_conflicts_part[
            len(renamed_to_builtin_scalar_conflicts_prefix) :
        ]
        if (
            literal_eval(renamed_to_builtin_scalar_conflicts_representation)
            != expected_renamed_to_builtin_scalar_conflicts
        ):
            return False
    return True


class TestRenameSchema(unittest.TestCase):
    def test_rename_visitor_type_coverage(self):
        """Check that all types are covered without overlap."""
        type_sets = [
            RenameSchemaTypesVisitor.noop_types,
            RenameSchemaTypesVisitor.rename_types,
        ]
        all_types = {snake_to_camel(node_type) + "Node" for node_type in QUERY_DOCUMENT_KEYS}
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
        renamed_schema = rename_schema(parse(ISS.basic_schema), {"Human": "NewHuman"})
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({"NewHuman": "Human"}, renamed_schema.reverse_name_map)

    def test_original_unmodified_rename(self):
        original_ast = parse(ISS.basic_schema)
        rename_schema(original_ast, {"Human": "NewHuman"})
        self.assertEqual(original_ast, parse(ISS.basic_schema))

    def test_original_unmodified_suppress(self):
        original_ast = parse(ISS.multiple_objects_schema)
        rename_schema(original_ast, {"Human": None})
        self.assertEqual(original_ast, parse(ISS.multiple_objects_schema))

    def test_basic_suppress(self):
        renamed_schema = rename_schema(parse(ISS.multiple_objects_schema), {"Human": None})
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({}, renamed_schema.reverse_name_map)

    def test_multiple_type_suppress(self):
        renamed_schema = rename_schema(
            parse(ISS.multiple_objects_schema), {"Human": None, "Droid": None}
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({}, renamed_schema.reverse_name_map)

    def test_swap_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.multiple_objects_schema), {"Human": "Droid", "Droid": "Human"}
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({"Human": "Droid", "Droid": "Human"}, renamed_schema.reverse_name_map)

    def test_rename_into_suppressed(self):
        renamed_schema = rename_schema(
            parse(ISS.multiple_objects_schema), {"Human": None, "Droid": "Human"}
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({"Human": "Droid"}, renamed_schema.reverse_name_map)

    def test_cyclic_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.multiple_objects_schema), {"Human": "Droid", "Droid": "Dog", "Dog": "Human"}
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {"Dog": "Droid", "Human": "Dog", "Droid": "Human"}, renamed_schema.reverse_name_map
        )

    def test_enum_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.enum_schema), {"Droid": "NewDroid", "Height": "NewHeight"}
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {"NewDroid": "Droid", "NewHeight": "Height"}, renamed_schema.reverse_name_map
        )

    def test_enum_suppression(self):
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.multiple_enums_schema), {"Size": None})

    def test_interface_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.interface_schema), {"Kid": "NewKid", "Character": "NewCharacter"}
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {"NewKid": "Kid", "NewCharacter": "Character"}, renamed_schema.reverse_name_map
        )

    def test_suppress_interface_implementation(self):
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.various_types_schema), {"Giraffe": None})

    def test_suppress_all_implementations_but_not_interface(self):
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.various_types_schema), {"Giraffe": None, "Human": None})

    def test_suppress_interface_but_not_implementations(self):
        with self.assertRaises(NotImplementedError):
            rename_schema(parse(ISS.various_types_schema), {"Character": None})

    def test_suppress_interface_and_all_implementations(self):
        with self.assertRaises(NotImplementedError):
            rename_schema(
                parse(ISS.various_types_schema), {"Giraffe": None, "Character": None, "Human": None}
            )

    def test_multiple_interfaces_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.multiple_interfaces_schema),
            {"Human": "NewHuman", "Character": "NewCharacter", "Creature": "Creature"},
        )
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            interface NewCharacter {
              id: String
            }

            interface Creature {
              age: Int
            }

            type NewHuman implements NewCharacter & Creature {
              id: String
              age: Int
            }

            type SchemaQuery {
              NewCharacter: NewCharacter
              Creature: Creature
              NewHuman: NewHuman
            }
        """
        )
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {"NewHuman": "Human", "NewCharacter": "Character"}, renamed_schema.reverse_name_map
        )

    def test_scalar_rename(self):
        with self.assertRaises(NotImplementedError):
            rename_schema(
                parse(ISS.scalar_schema), {"Date": "NewDate"},
            )

    def test_builtin_rename(self):
        with self.assertRaises(NotImplementedError):
            rename_schema(
                parse(ISS.list_schema), {"String": "NewString"},
            )

    def test_union_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.union_schema), {"HumanOrDroid": "NewHumanOrDroid", "Droid": "NewDroid"}
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {"NewDroid": "Droid", "NewHumanOrDroid": "HumanOrDroid"},
            renamed_schema.reverse_name_map,
        )

    def test_entire_union_suppress(self):
        renamed_schema = rename_schema(
            parse(ISS.union_schema), {"HumanOrDroid": None, "Droid": "NewDroid"}
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {"NewDroid": "Droid"}, renamed_schema.reverse_name_map,
        )

    def test_union_member_suppress(self):
        renamed_schema = rename_schema(parse(ISS.union_schema), {"Droid": None})
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {}, renamed_schema.reverse_name_map,
        )

    def test_list_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.list_schema),
            {
                "Droid": "NewDroid",
                "Character": "NewCharacter",
                "Height": "NewHeight",
                "id": "NewId",
            },
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {"NewCharacter": "Character", "NewDroid": "Droid", "NewHeight": "Height",},
            renamed_schema.reverse_name_map,
        )

    def test_non_null_rename(self):
        renamed_schema = rename_schema(parse(ISS.non_null_schema), {"Dog": "NewDog"})
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({"NewDog": "Dog"}, renamed_schema.reverse_name_map)

    def test_non_null_suppress(self):
        renamed_schema = rename_schema(parse(ISS.non_null_schema), {"Dog": None})
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({}, renamed_schema.reverse_name_map)

    def test_directive_rename(self):
        renamed_schema = rename_schema(
            parse(ISS.directive_schema),
            {"Human": "NewHuman", "Droid": "NewDroid", "stitch": "NewStitch",},
        )
        renamed_schema_string = dedent(
            """\
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
        """
        )
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual(
            {"NewHuman": "Human", "NewDroid": "Droid"}, renamed_schema.reverse_name_map
        )

    def test_query_type_field_argument(self):
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
        renamed_schema = rename_schema(parse(schema_string), {"Human": "NewHuman", "id": "Id"})
        renamed_schema_string = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              NewHuman(id: String!): NewHuman
            }

            type NewHuman {
              name: String
            }
        """
        )
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({"NewHuman": "Human"}, renamed_schema.reverse_name_map)

    def test_clashing_type_rename(self):
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
            rename_schema(parse(schema_string), {"Human1": "Human", "Human2": "Human"})
        self.assertTrue(
            check_rename_conflict_error_message({"Human": {"Human1", "Human2"}}, {}, e.exception)
        )

    def test_clashing_type_single_rename(self):
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
            rename_schema(parse(schema_string), {"Human2": "Human"})
        self.assertTrue(
            check_rename_conflict_error_message({"Human": {"Human", "Human2"}}, {}, e.exception)
        )

    def test_clashing_type_one_unchanged_rename(self):
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
            rename_schema(parse(schema_string), {"Human": "Human", "Human2": "Human"})
        self.assertTrue(
            check_rename_conflict_error_message({"Human": {"Human", "Human2"}}, {}, e.exception)
        )

    def test_clashing_scalar_type_rename(self):
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
            rename_schema(parse(schema_string), {"Human": "SCALAR"})
        self.assertTrue(
            check_rename_conflict_error_message({"SCALAR": {"SCALAR", "Human"}}, {}, e.exception)
        )

    def test_builtin_type_conflict_rename(self):
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
            rename_schema(parse(schema_string), {"Human": "String"})
        self.assertTrue(check_rename_conflict_error_message({}, {"Human": "String"}, e.exception))

    def test_multiple_naming_conflicts(self):
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
            rename_schema(parse(schema_string), {"Human": "String", "Dog": "Cat"})
        self.assertTrue(
            check_rename_conflict_error_message(
                {"Cat": {"Dog", "Cat"}}, {"Human": "String"}, e.exception
            )
        )

    def test_illegal_rename_start_with_number(self):
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "0Human"})

    def test_illegal_rename_contains_illegal_char(self):
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "Human!"})
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "H-uman"})
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "H.uman"})

    def test_illegal_rename_to_double_underscore(self):
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "__Human"})

    def test_illegal_rename_to_reserved_name_type(self):
        with self.assertRaises(InvalidTypeNameError):
            rename_schema(parse(ISS.basic_schema), {"Human": "__Type"})

    def test_suppress_every_type(self):
        with self.assertRaises(SchemaTransformError):
            rename_schema(parse(ISS.basic_schema), {"Human": None})

    def test_suppress_all_union_members(self):
        with self.assertRaises(CascadingSuppressionError):
            # Can't use ISS.union_schema here because suppressing all the members of the union would
            # mean suppressing every type in general, which means we couldn't be sure that
            # suppressing every member of a union specifically was raising the
            # CascadingSuppressionError.
            rename_schema(parse(ISS.extended_union_schema), {"Human": None, "Droid": None})

    def test_field_still_depends_on_suppressed_type(self):
        with self.assertRaises(CascadingSuppressionError):
            rename_schema(
                parse(ISS.multiple_fields_schema), {"Dog": None}
            )  # The type named Human contains a field of type Dog.

    def test_field_of_suppressed_type_in_suppressed_type(self):
        # The schema contains an object type that contains a field of the type Human. Normally,
        # suppressing the type named Human would cause a CascadingSuppressionError because the
        # resulting schema would still have fields of the type Human. Here, however, only the type
        # named Human contains such a field, so suppressing the type Human produces a legal schema.
        renamed_schema = rename_schema(parse(ISS.recursive_field_schema), {"Human": None})
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
        self.assertEqual({}, renamed_schema.reverse_name_map)

    def test_field_in_list_still_depends_on_suppressed_type(self):
        with self.assertRaises(CascadingSuppressionError):
            rename_schema(parse(ISS.list_schema), {"Height": None})

    def test_rename_using_dict_like_prefixer_class(self):
        class PrefixNewDict(object):
            def __init__(self, schema: GraphQLSchema):
                self.schema = schema

            def get(self, key, default=None):
                if key in get_custom_scalar_names(self.schema) or key in builtin_scalar_types:
                    # Making an exception for scalar types because renaming and suppressing them
                    # hasn't been implemented yet
                    return key
                return "New" + key

        schema = parse(ISS.various_types_schema)
        renamed_schema = rename_schema(schema, PrefixNewDict(build_ast_schema(schema)))
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
        self.assertEqual(renamed_schema_string, print_ast(renamed_schema.schema_ast))
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
