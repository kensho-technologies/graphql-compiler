from textwrap import dedent
import unittest

from graphql import parse, print_ast

from ...schema_transformation.restrict_schema_types import restrict_schema_types
from ...schema_transformation.utils import SchemaStructureError


class TestRestrictSchema(unittest.TestCase):
    def test_basic_restrict(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              name: String
              pet: Pet
              friend: Person
            }

            type Pet {
              name: String
              owner: Person
              friend: Pet
            }

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }
        ''')
        restricted_schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              name: String
              friend: Person
            }

            type SchemaQuery {
              Person: Person
            }
        ''')
        schema_ast = parse(schema_str)
        restricted_schema_ast = restrict_schema_types(schema_ast, {'Person'})
        self.assertEqual(print_ast(restricted_schema_ast), restricted_schema_str)

    def test_original_unmodified(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              name: String
              pet: Pet
              friend: Person
            }

            type Pet {
              name: String
              owner: Person
              friend: Pet
            }

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }
        ''')
        schema_ast = parse(schema_str)
        restrict_schema_types(schema_ast, {'Person'})
        self.assertEqual(schema_ast, parse(schema_str))

    def test_interface_kept(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            interface Entity {
              id: String
            }

            type Person implements Entity {
              id: String
              name: String
              pet: Pet
              friend: Person
              related: Entity
            }

            type Pet implements Entity {
              id: String
              owner: Person
              name: String
              friend: Pet
            }

            type SchemaQuery {
              Entity: Entity
              Person: Person
              Pet: Pet
            }
        ''')
        restricted_schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            interface Entity {
              id: String
            }

            type Person implements Entity {
              id: String
              name: String
              friend: Person
              related: Entity
            }

            type SchemaQuery {
              Entity: Entity
              Person: Person
            }
        ''')
        schema_ast = parse(schema_str)
        restricted_schema_ast = restrict_schema_types(schema_ast, {'Entity', 'Person'})
        self.assertEqual(print_ast(restricted_schema_ast), restricted_schema_str)

    def test_interface_removed(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            interface Entity {
              id: String
            }

            type Person implements Entity {
              id: String
              name: String
              pet: Pet
              friend: Person
              related: Entity
            }

            type Pet implements Entity {
              id: String
              owner: Person
              name: String
              friend: Pet
            }

            type SchemaQuery {
              Entity: Entity
              Person: Person
              Pet: Pet
            }
        ''')
        restricted_schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              id: String
              name: String
              pet: Pet
              friend: Person
            }

            type Pet {
              id: String
              owner: Person
              name: String
              friend: Pet
            }

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }
        ''')
        schema_ast = parse(schema_str)
        restricted_schema_ast = restrict_schema_types(schema_ast, {'Person', 'Pet'})
        self.assertEqual(print_ast(restricted_schema_ast), restricted_schema_str)

    def test_union_kept(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              id: String
              name: String
              pet: Pet
              friend: Person
            }

            type Pet {
              id: String
              owner: Person
              name: String
              friend: Pet
            }

            union PersonOrPet = Person | Pet

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }
        ''')
        restricted_schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              id: String
              name: String
              pet: Pet
              friend: Person
            }

            type Pet {
              id: String
              owner: Person
              name: String
              friend: Pet
            }

            union PersonOrPet = Person | Pet

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }
        ''')
        schema_ast = parse(schema_str)
        restricted_schema_ast = restrict_schema_types(schema_ast, {'Person', 'Pet', 'PersonOrPet'})
        self.assertEqual(print_ast(restricted_schema_ast), restricted_schema_str)

    def test_union_removed(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              id: String
              name: String
              pet: Pet
              friend: Person
            }

            type Pet {
              id: String
              owner: Person
              name: String
              friend: Pet
            }

            union PersonOrPet = Person | Pet

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }
        ''')
        restricted_schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              id: String
              name: String
              friend: Person
            }

            type SchemaQuery {
              Person: Person
            }
        ''')
        schema_ast = parse(schema_str)
        restricted_schema_ast = restrict_schema_types(schema_ast, {'Person'})
        self.assertEqual(print_ast(restricted_schema_ast), restricted_schema_str)

    def test_invalid_union(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              id: String
              name: String
              pet: Pet
              friend: Person
            }

            type Pet {
              id: String
              owner: Person
              name: String
              friend: Pet
            }

            union PersonOrPet = Person | Pet

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }
        ''')
        schema_ast = parse(schema_str)
        with self.assertRaises(SchemaStructureError):
            restrict_schema_types(schema_ast, {'PersonOrPet', 'Pet'})

    def test_invalid_all_fields_removed(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              name: String
              pet: Pet
              friend: Person
            }

            type Pet {
              owner: Person
            }

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }
        ''')
        schema_ast = parse(schema_str)
        with self.assertRaises(SchemaStructureError):
            restrict_schema_types(schema_ast, {'Pet'})

    def test_user_defined_scalar(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              name: String
              pet: Pet
              friend: Person
              bday: Date
            }

            type Pet {
              name: String
              owner: Person
              friend: Pet
            }

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }

            scalar Date
        ''')
        restricted_schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              name: String
              friend: Person
              bday: Date
            }

            type SchemaQuery {
              Person: Person
            }

            scalar Date
        ''')
        schema_ast = parse(schema_str)
        restricted_schema_ast = restrict_schema_types(schema_ast, {'Person'})
        self.assertEqual(print_ast(restricted_schema_ast), restricted_schema_str)

    def test_unreachable_type(self):
        schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              name: String
              pet: Pet
              friend: Person
            }

            type Pet {
              name: String
              breed: Breed
            }

            type Breed {
              name: String
            }

            type SchemaQuery {
              Person: Person
              Pet: Pet
            }
        ''')
        restricted_schema_str = dedent('''\
            schema {
              query: SchemaQuery
            }

            type Person {
              name: String
              friend: Person
            }

            type Breed {
              name: String
            }

            type SchemaQuery {
              Person: Person
            }
        ''')
        schema_ast = parse(schema_str)
        restricted_schema_ast = restrict_schema_types(schema_ast, {'Person', 'Breed'})
        self.assertEqual(print_ast(restricted_schema_ast), restricted_schema_str)
