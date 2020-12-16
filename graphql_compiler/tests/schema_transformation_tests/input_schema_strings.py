# Copyright 2019-present Kensho Technologies, LLC.
from textwrap import dedent


class InputSchemaStrings(object):
    basic_schema = dedent(
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

    type_field_directive_same_name_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

        type stitch {
          stitch: String
        }

        type SchemaQuery {
          stitch: stitch
        }
    """
    )

    multiple_objects_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Human {
          name: String
        }

        type Droid {
          id: String
        }

        type Dog {
          nickname: String
        }

        type SchemaQuery {
          Human: Human
          Droid: Droid
          Dog: Dog
        }
    """
    )

    enum_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Droid {
          height: Height
        }

        type SchemaQuery {
          Droid: Droid
        }

        enum Height {
          TALL
          SHORT
        }
    """
    )

    multiple_enums_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Droid {
          height: Height
        }

        type SchemaQuery {
          Droid: Droid
        }

        enum Height {
          TALL
          SHORT
        }

        enum Size {
          BIG
          SMALL
        }
    """
    )

    interface_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        interface Character {
          id: String
        }

        type Kid implements Character {
          id: String
        }

        type SchemaQuery {
          Character: Character
          Kid: Kid
        }
    """
    )

    multiple_interfaces_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        interface Character {
          id: String
        }

        interface Creature {
          age: Int
        }

        type Human implements Character & Creature {
          id: String
          age: Int
        }

        type SchemaQuery {
          Character: Character
          Creature: Creature
          Human: Human
        }
    """
    )

    scalar_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

        type Human {
          id: String
          birthday: Date
        }

        scalar Date

        type SchemaQuery {
          Human: Human
        }
    """
    )

    union_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Human {
          id: String
        }

        type Droid {
          id: String
        }

        union HumanOrDroid = Human | Droid

        type SchemaQuery {
          Human: Human
          Droid: Droid
        }
    """
    )

    extended_union_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Human {
          id: String
        }

        type Droid {
          id: String
        }

        type Dog {
          nickname: String
        }

        union HumanOrDroid = Human | Droid

        type SchemaQuery {
          Human: Human
          Droid: Droid
          Dog: Dog
        }
    """
    )

    list_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Droid implements Character {
          id: String
          heights: [Height]
          dates: [Date]
          friends: [Droid]
          enemies: [Character]
        }

        type SchemaQuery {
          Droid: [Droid]
        }

        scalar Date

        interface Character {
          id: String
        }

        enum Height {
          TALL
          SHORT
        }
    """
    )

    non_null_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Dog {
          id: String!
          friend: Dog!
        }

        type Cat {
            id: String
        }

        type SchemaQuery {
          Dog: Dog!
          Cat: Cat
        }
    """
    )

    directive_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Human {
          id: String
        }

        type Droid {
          id: String
          friend: Human @stitch(source_field: "id", sink_field: "id")
        }

        directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

        type SchemaQuery {
          Human: Human
          Droid: Droid
        }
    """
    )

    various_types_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        scalar Date

        enum Height {
          TALL
          SHORT
        }

        interface Character {
          id: String
        }

        type Human implements Character {
          id: String
          name: String
          birthday: Date
        }

        type Giraffe implements Character {
          id: String
          height: Height
        }

        type Dog {
          nickname: String
        }

        directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

        type SchemaQuery {
          Human: Human
          Giraffe: Giraffe
          Dog: Dog
        }
    """
    )

    same_field_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Person {
          identifier: String
        }

        type SchemaQuery {
          Person: Person
        }
    """
    )

    interface_with_subclasses_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

        interface Individual {
          ID: String
        }

        type President implements Individual {
          ID: String
          year: Int
        }

        type SchemaQuery {
          Individual: Individual
          President: President
        }
    """
    )

    union_with_subclasses_schema = dedent(
        """\
        schema {
         query: SchemaQuery
        }

        type Person {
          identifier: String
        }

        type Kid {
          identifier: String
          age: Int
        }

        union PersonOrKid = Person | Kid

        type SchemaQuery {
          Person: Person
          Kid: Kid
        }
    """
    )

    multiple_fields_schema = dedent(
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

    recursive_field_schema = dedent(
        """\
        schema {
          query: SchemaQuery
        }

        type Human  {
          friend: Human
          name: String
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
