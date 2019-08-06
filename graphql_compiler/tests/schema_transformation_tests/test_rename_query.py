# Copyright 2019-present Kensho Technologies, LLC.
from textwrap import dedent
import unittest

from graphql import parse
from graphql.language.printer import print_ast
from graphql_compiler.exceptions import GraphQLValidationError
from graphql_compiler.schema_transformation.rename_query import rename_query
from graphql_compiler.schema_transformation.rename_schema import rename_schema

from .example_schema import basic_renamed_schema, basic_schema


class TestRenameQuery(unittest.TestCase):
    def test_no_rename(self):
        query_string = dedent('''\
            {
              Animal {
                color
              }
            }
        ''')
        renamed_query = rename_query(parse(query_string), rename_schema(basic_schema, {}))
        self.assertEqual(query_string, print_ast(renamed_query))

    def test_original_unmodified(self):
        query_string = dedent('''\
            {
              NewAnimal {
                color
              }
            }
        ''')
        ast = parse(query_string)
        rename_query(parse(query_string), basic_renamed_schema)
        self.assertEqual(ast, parse(query_string))

    def test_rename_unnamed_query(self):
        query_string = dedent('''\
            {
              NewAnimal {
                color
              }
            }
        ''')
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent('''\
            {
              Animal {
                color
              }
            }
        ''')
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_rename_named_query(self):
        query_string = dedent('''\
            query AnimalQuery {
              NewAnimal {
                color
              }
            }
        ''')
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent('''\
            query AnimalQuery {
              Animal {
                color
              }
            }
        ''')
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_rename_nested_query(self):
        query_string = dedent('''\
            {
              NewAnimal {
                name
                out_Animal_ParentOf {
                  name
                  description
                  out_Animal_LivesIn {
                    description
                  }
                }
              }
            }
        ''')
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent('''\
            {
              Animal {
                name
                out_Animal_ParentOf {
                  name
                  description
                  out_Animal_LivesIn {
                    description
                  }
                }
              }
            }
        ''')
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_inline_fragment(self):
        query_string = dedent('''\
            {
              NewEntity {
                out_Entity_Related {
                  ... on NewAnimal {
                    color
                  }
                }
              }
            }
        ''')
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent('''\
            {
              Entity {
                out_Entity_Related {
                  ... on Animal {
                    color
                  }
                }
              }
            }
        ''')
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_nested_inline_fragment(self):
        query_string = dedent('''\
            {
              NewEntity {
                out_Entity_Related {
                  ... on NewAnimal {
                    out_Animal_ImportantEvent {
                      ... on NewBirthEvent {
                        event_date
                      }
                    }
                  }
                }
              }
            }
        ''')
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent('''\
            {
              Entity {
                out_Entity_Related {
                  ... on Animal {
                    out_Animal_ImportantEvent {
                      ... on BirthEvent {
                        event_date
                      }
                    }
                  }
                }
              }
            }
        ''')
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_directive(self):
        query_string = dedent('''\
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
        ''')
        renamed_query = rename_query(parse(query_string), basic_renamed_schema)
        renamed_query_string = dedent('''\
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
        ''')
        self.assertEqual(renamed_query_string, print_ast(renamed_query))

    def test_invalid_query_type_not_in_schema(self):
        query_string = dedent('''\
           {
              RandomType {
                name
              }
            }
        ''')
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}))

    def test_invalid_field_not_in_schema(self):
        query_string = dedent('''\
           {
              Animal {
                age
              }
            }
        ''')
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}))

    def test_invalid_ends_in_vertex_field(self):
        query_string = dedent('''\
           {
              Animal {
                out_Animal_ParentOf
              }
            }
        ''')
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}))

    def test_invalid_start_with_inline(self):
        query_string = dedent('''\
            {
              ... on RootSchemaQuery {
                Animal {
                  name
                }
              }
            }
        ''')
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}))

    def test_invalid_fragment(self):
        query_string = dedent('''\
            {
              Animal {
                ...AnimalFragment
              }
            }

            fragment AnimalFragment on Animal {
              name
            }
        ''')
        with self.assertRaises(GraphQLValidationError):
            rename_query(parse(query_string), rename_schema(basic_schema, {}))
