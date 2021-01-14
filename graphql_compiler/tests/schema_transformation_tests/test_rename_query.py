# Copyright 2019-present Kensho Technologies, LLC.
from textwrap import dedent
import unittest

from graphql import parse
from graphql.language.printer import print_ast

from ...exceptions import GraphQLValidationError
from ...schema_transformation.rename_query import rename_query
from ...schema_transformation.rename_schema import rename_schema
from .example_schema import basic_renamed_schema, basic_schema
from .input_schema_strings import InputSchemaStrings as ISS


class TestRenameQuery(unittest.TestCase):
    def test_no_rename(self):
        query_string = dedent(
            """\
            {
              Animal {
                color @output(out_name: "color")
              }
            }
        """
        )
        renamed_query = rename_query(parse(query_string), rename_schema(basic_schema, {}, {}))
        self.assertEqual(query_string, print_ast(renamed_query))

    def test_original_unmodified(self):
        query_string = dedent(
            """\
            {
              NewAnimal {
                color @output(out_name: "color")
              }
            }
        """
        )
        ast = parse(query_string)
        rename_query(parse(query_string), basic_renamed_schema)
        self.assertEqual(ast, parse(query_string))

    def test_rename_unnamed_query(self):
        query_string = dedent(
            """\
            {
              NewAnimal {
                color @output(out_name: "color")
              }
            }
        """
        )
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent(
            """\
            {
              Animal {
                color @output(out_name: "color")
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_rename_named_query(self):
        query_string = dedent(
            """\
            query AnimalQuery {
              NewAnimal {
                color @output(out_name: "color")
              }
            }
        """
        )
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent(
            """\
            query AnimalQuery {
              Animal {
                color @output(out_name: "color")
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_rename_nested_query(self):
        query_string = dedent(
            """\
            {
              NewAnimal {
                name @output(out_name: "name")
                out_Animal_ParentOf {
                  name @output(out_name: "parent_name")
                  description @output(out_name: "parent_description")
                  out_Animal_LivesIn {
                    description @output(out_name: "parent_location")
                  }
                }
              }
            }
        """
        )
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent(
            """\
            {
              Animal {
                name @output(out_name: "name")
                out_Animal_ParentOf {
                  name @output(out_name: "parent_name")
                  description @output(out_name: "parent_description")
                  out_Animal_LivesIn {
                    description @output(out_name: "parent_location")
                  }
                }
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_inline_fragment(self):
        query_string = dedent(
            """\
            {
              NewEntity {
                out_Entity_Related {
                  ... on NewAnimal {
                    color @output(out_name: "color")
                  }
                }
              }
            }
        """
        )
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent(
            """\
            {
              Entity {
                out_Entity_Related {
                  ... on Animal {
                    color @output(out_name: "color")
                  }
                }
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_nested_inline_fragment(self):
        query_string = dedent(
            """\
            {
              NewEntity {
                out_Entity_Related {
                  ... on NewAnimal {
                    out_Animal_ImportantEvent {
                      ... on NewBirthEvent {
                        event_date @output(out_name: "date")
                      }
                    }
                  }
                }
              }
            }
        """
        )
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent(
            """\
            {
              Entity {
                out_Entity_Related {
                  ... on Animal {
                    out_Animal_ImportantEvent {
                      ... on BirthEvent {
                        event_date @output(out_name: "date")
                      }
                    }
                  }
                }
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_directive(self):
        query_string = dedent(
            """\
            {
              NewEntity {
                out_Entity_Related {
                  ... on NewAnimal {
                    color @output(out_name: "color")
                    out_Animal_ParentOf @optional {
                      name @filter(op_name: "=", value: ["$species_name"])
                    }
                  }
                }
              }
            }
        """
        )
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent(
            """\
            {
              Entity {
                out_Entity_Related {
                  ... on Animal {
                    color @output(out_name: "color")
                    out_Animal_ParentOf @optional {
                      name @filter(op_name: "=", value: ["$species_name"])
                    }
                  }
                }
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_rename_field_one_to_one(self):
        query_string = dedent(
            """\
            {
              Human {
                new_name @output(out_name: "name")
              }
            }
        """
        )
        renamed_query = rename_query(
            parse(query_string),
            rename_schema(parse(ISS.multiple_fields_schema), {}, {"Human": {"name": {"new_name"}}}),
        )
        renamed_query_string = dedent(
            """\
            {
              Human {
                name @output(out_name: "name")
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_rename_field_one_to_many(self):
        query_string = dedent(
            """\
            {
              Human {
                new_name @output(out_name: "name")
              }
            }
        """
        )
        alternative_query_string = dedent(
            """\
            {
              Human {
                name @output(out_name: "name")
              }
            }
        """
        )
        renamed_schema = rename_schema(
            parse(ISS.multiple_fields_schema), {}, {"Human": {"name": {"name", "new_name"}}}
        )
        renamed_query = rename_query(parse(query_string), renamed_schema)
        renamed_alternative_query = rename_query(parse(alternative_query_string), renamed_schema)
        renamed_query_string = dedent(
            """\
            {
              Human {
                name @output(out_name: "name")
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))
        self.assertEqual(renamed_query_string, print_ast(renamed_alternative_query))

    def test_rename_to_field_in_original_schema(self):
        query_string = dedent(
            """\
            {
              Human {
                id @output(out_name: "name")
              }
            }
        """
        )
        renamed_schema = rename_schema(
            parse(ISS.multiple_fields_schema),
            {},
            {"Human": {"name": {"name", "id"}, "id": {"new_id", "unique_id"}}},
        )
        renamed_query = rename_query(parse(query_string), renamed_schema)
        renamed_query_string = dedent(
            """\
            {
              Human {
                name @output(out_name: "name")
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_rename_to_field_suppressed_in_original_schema(self):
        query_string = dedent(
            """\
            {
              Human {
                id @output(out_name: "name")
              }
            }
        """
        )
        renamed_schema = rename_schema(
            parse(ISS.multiple_fields_schema), {}, {"Human": {"name": {"name", "id"}, "id": set()}}
        )
        renamed_query = rename_query(parse(query_string), renamed_schema)
        renamed_query_string = dedent(
            """\
            {
              Human {
                name @output(out_name: "name")
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_same_field_different_types(self):
        query_string = dedent(
            """\
            {
              Human {
                new_id @output(out_name: "human_id")
                pet {
                  id @output(out_name: "pet_id")
                }
              }
            }
        """
        )
        renamed_schema = rename_schema(
            parse(ISS.multiple_fields_schema), {}, {"Human": {"id": {"new_id"}}}
        )
        renamed_query = rename_query(parse(query_string), renamed_schema)
        renamed_query_string = dedent(
            """\
            {
              Human {
                id @output(out_name: "human_id")
                pet {
                  id @output(out_name: "pet_id")
                }
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_rename_type_and_field(self):
        query_string = dedent(
            """\
            {
              NewHuman {
                new_name @output(out_name: "name")
              }
            }
        """
        )
        renamed_query = rename_query(
            parse(query_string),
            rename_schema(
                parse(ISS.multiple_fields_schema),
                {"Human": "NewHuman"},
                {"Human": {"name": {"new_name"}}},
            ),
        )
        renamed_query_string = dedent(
            """\
            {
              Human {
                name @output(out_name: "name")
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_rename_field_multiple_query_branches(self):
        query_string = dedent(
            """\
            {
              Human {
                new_pet {
                  id @output(out_name: "pet_id")
                }
                new_droid {
                  new_droid_id @output(out_name: "droid_id")
                }
              }
            }
        """
        )
        renamed_query = rename_query(
            parse(query_string),
            rename_schema(
                parse(ISS.multiple_fields_schema),
                {},
                {
                    "Human": {"pet": {"new_pet"}, "droid": {"new_droid"}},
                    "Droid": {"id": {"new_droid_id"}},
                },
            ),
        )
        renamed_query_string = dedent(
            """\
            {
              Human {
                pet {
                  id @output(out_name: "pet_id")
                }
                droid {
                  id @output(out_name: "droid_id")
                }
              }
            }
        """
        )
        self.assertEqual(renamed_query_string, print_ast(renamed_query))


class TestRenameQueryInvalidQuery(unittest.TestCase):
    def test_invalid_query_type_not_in_schema(self):
        query_string = dedent(
            """\
           {
              RandomType {
                name @output(out_name: "name")
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}, {}))

    def test_invalid_field_not_in_schema(self):
        query_string = dedent(
            """\
           {
              Animal {
                age @output(out_name: "age")
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}, {}))

    def test_invalid_ends_in_vertex_field(self):
        query_string = dedent(
            """\
           {
              Animal {
                out_Animal_ParentOf
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}, {}))

    def test_invalid_start_with_inline(self):
        query_string = dedent(
            """\
            {
              ... on RootSchemaQuery {
                Animal {
                  color @output(out_name: "color")
                }
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}, {}))

    def test_invalid_fragment(self):
        query_string = dedent(
            """\
            {
              Animal {
                ...AnimalFragment
              }
            }

            fragment AnimalFragment on Animal {
              color @output(out_name: "color")
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}, {}))

    def test_query_for_suppressed_type(self):
        query_string = dedent(
            """\
            {
              Human {
                id @output(out_name: "id")
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            rename_query(
                parse(query_string),
                rename_schema(parse(ISS.multiple_fields_schema), {"Human": None}, {}),
            )

    def test_query_for_suppressed_field(self):
        query_string = dedent(
            """\
            {
              Human {
                id @output(out_name: "id")
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            rename_query(
                parse(query_string),
                rename_schema(parse(ISS.multiple_fields_schema), {}, {"Human": {"id": set()}}),
            )

    def test_query_for_field_in_original_schema_after_rename(self):
        query_string = dedent(
            """\
            {
              Human {
                id @output(out_name: "id")
              }
            }
        """
        )
        with self.assertRaises(GraphQLValidationError):
            rename_query(
                parse(query_string),
                rename_schema(parse(ISS.multiple_fields_schema), {}, {"Human": {"id": {"new_id"}}}),
            )
