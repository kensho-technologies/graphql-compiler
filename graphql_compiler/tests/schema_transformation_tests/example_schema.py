# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict

from graphql import build_ast_schema, parse
import six

from ...schema_transformation.merge_schemas import (
    CrossSchemaEdgeDescriptor,
    FieldReference,
    MergedSchemaDescriptor,
    merge_schemas,
)
from ...schema_transformation.rename_schema import rename_schema
from ..test_helpers import SCHEMA_TEXT


basic_schema = parse(SCHEMA_TEXT)


basic_renamed_schema = rename_schema(
    basic_schema, {"Animal": "NewAnimal", "Entity": "NewEntity", "BirthEvent": "NewBirthEvent"}, {}
)


basic_additional_schema = """
schema {
  query: SchemaQuery
}

type Creature {
  age: Int
  id: String
  friend: [Creature]
}

type SchemaQuery {
  Creature: Creature
}
"""


basic_merged_schema = merge_schemas(
    OrderedDict(
        [
            ("first", basic_schema),
            ("second", parse(basic_additional_schema)),
        ]
    ),
    [
        CrossSchemaEdgeDescriptor(
            edge_name="Animal_Creature",
            outbound_field_reference=FieldReference(
                schema_id="first",
                type_name="Animal",
                field_name="uuid",
            ),
            inbound_field_reference=FieldReference(
                schema_id="second", type_name="Creature", field_name="id"
            ),
            out_edge_only=False,
        ),
    ],
)


interface_additional_schema = """
schema {
  query: SchemaQuery
}

interface Creature {
  id: String
  age: Int
}

type Cat implements Creature {
  id: String
  age: Int
  meow: String
}

type Dog implements Creature {
  id: String
  age: Int
  bark: String
}

type SchemaQuery {
  Creature: Creature
  Cat: Cat
  Dog: Dog
}
"""


interface_merged_schema = merge_schemas(
    OrderedDict(
        [
            ("first", basic_schema),
            ("second", parse(interface_additional_schema)),
        ]
    ),
    [
        CrossSchemaEdgeDescriptor(
            edge_name="Animal_Creature",
            outbound_field_reference=FieldReference(
                schema_id="first",
                type_name="Animal",
                field_name="uuid",
            ),
            inbound_field_reference=FieldReference(
                schema_id="second", type_name="Creature", field_name="id"
            ),
            out_edge_only=False,
        ),
    ],
)


def _get_type_equivalence_hints(schema_id_to_ast, type_equivalence_hints_names):
    """Get type_equivalence_hints for input into merge_schemas.

    Args:
        schema_id_to_ast: Dict[str, Document]
        type_equivalence_hints_names: Dict[str, str]

    Returns:
        Dict[GraphQLObjectType, GraphQLUnionType]
    """
    name_to_type = {}
    for ast in six.itervalues(schema_id_to_ast):
        schema = build_ast_schema(ast)
        name_to_type.update(schema.type_map)
    type_equivalence_hints = {}
    for object_type_name, union_type_name in six.iteritems(type_equivalence_hints_names):
        object_type = name_to_type[object_type_name]
        union_type = name_to_type[union_type_name]
        type_equivalence_hints[object_type] = union_type
    return type_equivalence_hints


union_additional_schema = """
schema {
  query: SchemaQuery
}

type Creature {
  id: String
  age: Int
}

type Cat {
  id: String
  age: Int
}

union CreatureOrCat = Creature | Cat

type SchemaQuery {
  Creature: Creature
  Cat: Cat
}
"""


union_schema_id_to_ast = OrderedDict(
    [
        ("first", basic_schema),
        ("second", parse(union_additional_schema)),
    ]
)


union_merged_schema = merge_schemas(
    union_schema_id_to_ast,
    [
        CrossSchemaEdgeDescriptor(
            edge_name="Animal_Creature",
            outbound_field_reference=FieldReference(
                schema_id="first",
                type_name="Animal",
                field_name="uuid",
            ),
            inbound_field_reference=FieldReference(
                schema_id="second", type_name="Creature", field_name="id"
            ),
            out_edge_only=False,
        ),
    ],
    _get_type_equivalence_hints(union_schema_id_to_ast, {"Creature": "CreatureOrCat"}),
)


third_additional_schema = """
schema {
  query: SchemaQuery
}

type Critter {
  size: Int
  ID: String
}

type SchemaQuery {
  Critter: Critter
}
"""


three_merged_schema = merge_schemas(
    OrderedDict(
        [
            ("first", basic_schema),
            ("second", parse(basic_additional_schema)),
            ("third", parse(third_additional_schema)),
        ]
    ),
    [
        CrossSchemaEdgeDescriptor(
            edge_name="Animal_Creature",
            outbound_field_reference=FieldReference(
                schema_id="first",
                type_name="Animal",
                field_name="uuid",
            ),
            inbound_field_reference=FieldReference(
                schema_id="second", type_name="Creature", field_name="id"
            ),
            out_edge_only=False,
        ),
        CrossSchemaEdgeDescriptor(
            edge_name="Animal_Critter",
            outbound_field_reference=FieldReference(
                schema_id="first",
                type_name="Animal",
                field_name="uuid",
            ),
            inbound_field_reference=FieldReference(
                schema_id="third", type_name="Critter", field_name="ID"
            ),
            out_edge_only=False,
        ),
    ],
)


stitch_arguments_flipped_schema_str = """
schema {
  query: SchemaQuery
}

type Animal {
  uuid: String
  name: String
  out_Animal_Creature: Creature @stitch(sink_field: "id", source_field: "uuid")
}

type Creature {
  id: String
  age: Int
  in_Animal_Creature: Animal @stitch(sink_field: "uuid", source_field: "id")
}

type SchemaQuery {
  Animal: Animal
  Creature: Creature
}

directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

directive @output(out_name: String!) on FIELD
"""


stitch_arguments_flipped_schema = MergedSchemaDescriptor(
    schema_ast=parse(stitch_arguments_flipped_schema_str),
    schema=build_ast_schema(parse(stitch_arguments_flipped_schema_str)),
    type_name_to_schema_id={"Animal": "first", "Creature": "second"},
)
