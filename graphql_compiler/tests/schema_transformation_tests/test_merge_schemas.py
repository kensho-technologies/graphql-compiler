# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict
from textwrap import dedent
import unittest

from graphql import build_ast_schema, parse
from graphql.language.printer import print_ast
import six

from ...schema_transformation.merge_schemas import (
    CrossSchemaEdgeDescriptor,
    FieldReference,
    merge_schemas,
)
from ...schema_transformation.utils import InvalidCrossSchemaEdgeError, SchemaMergeNameConflictError
from .input_schema_strings import InputSchemaStrings as ISS


class TestMergeSchemasNoCrossSchemaEdges(unittest.TestCase):
    def test_basic_merge(self):
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("basic", parse(ISS.basic_schema)),
                    ("enum", parse(ISS.enum_schema)),
                ]
            ),
            [],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Droid: Droid
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

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
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))
        self.assertEqual(
            {"Droid": "enum", "Height": "enum", "Human": "basic"},
            merged_schema.type_name_to_schema_id,
        )

    def test_original_unmodified(self):
        basic_ast = parse(ISS.basic_schema)
        enum_ast = parse(ISS.enum_schema)
        merge_schemas(
            OrderedDict(
                [
                    ("basic", basic_ast),
                    ("enum", enum_ast),
                ]
            ),
            [],
        )
        self.assertEqual(basic_ast, parse(ISS.basic_schema))
        self.assertEqual(enum_ast, parse(ISS.enum_schema))

    def test_multiple_merge(self):
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.basic_schema)),
                    ("second", parse(ISS.enum_schema)),
                    ("third", parse(ISS.interface_schema)),
                    ("fourth", parse(ISS.non_null_schema)),
                ]
            ),
            [],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Droid: Droid
              Character: Character
              Kid: Kid
              Dog: Dog!
              Cat: Cat
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

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

            type Cat {
              id: String
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_different_query_type_name_merge(self):
        different_query_type_schema = dedent(
            """\
            schema {
              query: RandomRootSchemaQueryName
            }

            type Droid {
              id: String
            }

            type RandomRootSchemaQueryName {
              Droid: Droid
            }
        """
        )
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.basic_schema)),
                    ("second", parse(different_query_type_schema)),
                ]
            ),
            [],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Droid: Droid
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
            }

            type Droid {
              id: String
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_objects_merge_conflict(self):
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(ISS.basic_schema)),
                    ]
                ),
                [],
            )

    def test_interface_object_merge_conflict(self):
        interface_conflict_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            interface Human {
              id: String
            }
        """
        )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("basic", parse(ISS.basic_schema)),
                        ("bad", parse(interface_conflict_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("bad", parse(interface_conflict_schema)),
                        ("basic", parse(ISS.basic_schema)),
                    ]
                ),
                [],
            )

    def test_enum_object_merge_conflict(self):
        enum_conflict_schema = dedent(
            """\
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
        """
        )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("basic", parse(ISS.basic_schema)),
                        ("bad", parse(enum_conflict_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("bad", parse(enum_conflict_schema)),
                        ("basic", parse(ISS.basic_schema)),
                    ]
                ),
                [],
            )

    def test_enum_interface_merge_conflict(self):
        enum_conflict_schema = dedent(
            """\
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
        """
        )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("interface", parse(ISS.interface_schema)),
                        ("bad", parse(enum_conflict_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("bad", parse(enum_conflict_schema)),
                        ("interface", parse(ISS.interface_schema)),
                    ]
                ),
                [],
            )

    def test_object_scalar_merge_conflict(self):
        scalar_conflict_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            scalar Human
        """
        )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("basic", parse(ISS.basic_schema)),
                        ("bad", parse(scalar_conflict_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("bad", parse(scalar_conflict_schema)),
                        ("basic", parse(ISS.basic_schema)),
                    ]
                ),
                [],
            )

    def test_interface_scalar_merge_conflict(self):
        scalar_conflict_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            scalar Character
        """
        )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("interface", parse(ISS.interface_schema)),
                        ("bad", parse(scalar_conflict_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("bad", parse(scalar_conflict_schema)),
                        ("interface", parse(ISS.interface_schema)),
                    ]
                ),
                [],
            )

    def test_enum_scalar_merge_conflict(self):
        scalar_conflict_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type SchemaQuery {
              Int: Int
            }

            scalar Height
        """
        )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("enum", parse(ISS.enum_schema)),
                        ("bad", parse(scalar_conflict_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("bad", parse(scalar_conflict_schema)),
                        ("enum", parse(ISS.enum_schema)),
                    ]
                ),
                [],
            )

    def test_dedup_scalars(self):
        extra_scalar_schema = dedent(
            """\
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
        """
        )
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.scalar_schema)),
                    ("second", parse(extra_scalar_schema)),
                ]
            ),
            [],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Kid: Kid
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              birthday: Date
            }

            scalar Date

            scalar Decimal

            type Kid {
              height: Decimal
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))
        self.assertEqual({"Human": "first", "Kid": "second"}, merged_schema.type_name_to_schema_id)

    def test_dedup_same_directives(self):
        extra_directive_schema = dedent(
            """\
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
        """
        )
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.directive_schema)),
                    ("second", parse(extra_directive_schema)),
                ]
            ),
            [],
        )
        merged_schema_string = dedent(
            """\
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
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))
        self.assertEqual(
            {"Human": "first", "Droid": "first", "Kid": "second"},
            merged_schema.type_name_to_schema_id,
        )

    def test_clashing_directives(self):
        extra_directive_schema = dedent(
            """\
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
        """
        )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.directive_schema)),
                        ("second", parse(extra_directive_schema)),
                    ]
                ),
                [],
            )

    def test_invalid_identifiers(self):
        with self.assertRaises(ValueError):
            merge_schemas(
                OrderedDict(
                    [
                        ("", parse(ISS.basic_schema)),
                        ("enum", parse(ISS.enum_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(ValueError):
            merge_schemas(
                OrderedDict(
                    [
                        ("hello\n", parse(ISS.basic_schema)),
                        ("enum", parse(ISS.enum_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(ValueError):
            merge_schemas(
                OrderedDict(
                    [
                        ('<script>alert("hello world")</script>', parse(ISS.basic_schema)),
                        ("enum", parse(ISS.enum_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(ValueError):
            merge_schemas(
                OrderedDict(
                    [
                        ("\t\b", parse(ISS.basic_schema)),
                        ("enum", parse(ISS.enum_schema)),
                    ]
                ),
                [],
            )
        with self.assertRaises(ValueError):
            merge_schemas(
                OrderedDict(
                    [
                        (42, parse(ISS.basic_schema)),  # type: ignore
                        ("enum", parse(ISS.enum_schema)),
                    ]
                ),
                [],
            )

    def test_too_few_input_schemas(self):
        with self.assertRaises(ValueError):
            merge_schemas(
                OrderedDict(),
                [],
            )
        with self.assertRaises(ValueError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                    ]
                ),
                [],
            )


class TestMergeSchemasCrossSchemaEdgesWithoutSubclasses(unittest.TestCase):
    def test_simple_cross_schema_edge_descriptor(self):
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.basic_schema)),
                    ("second", parse(ISS.same_field_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Person: Person
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              out_example_edge: [Person] @stitch(source_field: "id", sink_field: "identifier")
            }

            type Person {
              identifier: String
              in_example_edge: [Human] @stitch(source_field: "identifier", sink_field: "id")
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_original_unmodified_when_edges_added(self):
        basic_schema_ast = parse(ISS.basic_schema)
        same_field_schema_ast = parse(ISS.same_field_schema)
        merge_schemas(
            OrderedDict(
                [
                    ("first", basic_schema_ast),
                    ("second", same_field_schema_ast),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        self.assertEqual(ISS.basic_schema, print_ast(basic_schema_ast))
        self.assertEqual(ISS.same_field_schema, print_ast(same_field_schema_ast))

    def test_one_directional_cross_schema_edge_descriptor(self):
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.basic_schema)),
                    ("second", parse(ISS.same_field_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=True,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Person: Person
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              out_example_edge: [Person] @stitch(source_field: "id", sink_field: "identifier")
            }

            type Person {
              identifier: String
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_multiple_fields_cross_schema_edge_descriptor(self):
        multiple_fields_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              age: Int
              name: String!
              identifier: String
              friends: [Person]
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.basic_schema)),
                    ("second", parse(multiple_fields_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Person: Person
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              out_example_edge: [Person] @stitch(source_field: "id", sink_field: "identifier")
            }

            type Person {
              age: Int
              name: String!
              identifier: String
              friends: [Person]
              in_example_edge: [Human] @stitch(source_field: "identifier", sink_field: "id")
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_non_null_scalar_match_normal_scalar(self):
        non_null_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              identifier: String!
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.basic_schema)),
                    ("second", parse(non_null_field_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Person: Person
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              out_example_edge: [Person] @stitch(source_field: "id", sink_field: "identifier")
            }

            type Person {
              identifier: String!
              in_example_edge: [Human] @stitch(source_field: "identifier", sink_field: "id")
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_matching_user_defined_scalar(self):
        additional_scalar_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              age: Int
              bday: Date
            }

            scalar Date

            type SchemaQuery {
              Person: Person
            }
        """
        )
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.scalar_schema)),
                    ("second", parse(additional_scalar_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="birthday",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="bday",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Person: Person
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              birthday: Date
              out_example_edge: [Person] @stitch(source_field: "birthday", sink_field: "bday")
            }

            scalar Date

            type Person {
              age: Int
              bday: Date
              in_example_edge: [Human] @stitch(source_field: "bday", sink_field: "birthday")
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_id_match_string(self):
        id_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              identifier: ID
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.basic_schema)),
                    ("second", parse(id_field_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Person: Person
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              out_example_edge: [Person] @stitch(source_field: "id", sink_field: "identifier")
            }

            type Person {
              identifier: ID
              in_example_edge: [Human] @stitch(source_field: "identifier", sink_field: "id")
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_id_match_int(self):
        int_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Human {
              id: Int
            }

            type SchemaQuery {
              Human: Human
            }
        """
        )
        id_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Person {
              identifier: ID
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(int_field_schema)),
                    ("second", parse(id_field_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Person: Person
            }

            type Human {
              id: Int
              out_example_edge: [Person] @stitch(source_field: "id", sink_field: "identifier")
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Person {
              identifier: ID
              in_example_edge: [Human] @stitch(source_field: "identifier", sink_field: "id")
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))


class TestMergeSchemasInvalidCrossSchemaEdges(unittest.TestCase):
    def test_invalid_edge_within_single_schema(self):
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.union_schema)),
                        ("second", parse(ISS.interface_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="example_edge",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Droid",
                            field_name="id",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_nonexistent_schema(self):
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(ISS.same_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="example_edge",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="third",
                            type_name="Person",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_type_in_wrong_schema(self):
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(ISS.same_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="example_edge",
                        outbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Person",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_nonexistent_type(self):
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(ISS.same_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="example_edge",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Droid",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_vertex_field_scalar_type(self):
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(ISS.same_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="example_edge",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="String",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Droid",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_vertex_field_enum_type(self):
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(ISS.enum_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="example_edge",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Height",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_vertex_field_union_type(self):
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.union_schema)),
                        ("second", parse(ISS.interface_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="example_edge",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="HumanOrDroid",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Kid",
                            field_name="id",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_nonexistent_property_field(self):
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(ISS.same_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="example_edge",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="name",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_new_vertex_field_clash_with_existing_field(self):
        clashing_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              identifier: String
              in_clashing_name: Int
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(clashing_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="clashing_name",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_new_vertex_field_clash_with_previous_edge_vertex_field(self):
        with self.assertRaises(SchemaMergeNameConflictError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(ISS.same_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="clashing_name",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                    CrossSchemaEdgeDescriptor(
                        edge_name="clashing_name",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_property_field_not_scalar_type(self):
        not_scalar_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              friend: Person
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(not_scalar_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="clashing_name",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="friend",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_property_field_list_of_types(self):
        not_scalar_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              friend: [Person]
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(not_scalar_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="clashing_name",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="friend",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_property_field_list_of_scalars(self):
        not_scalar_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              id: [String]
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(not_scalar_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="clashing_name",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="id",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_property_field_non_null_type(self):
        not_scalar_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              friend: Person!
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(not_scalar_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="clashing_name",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="friend",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_property_fields_mismatched_scalars(self):
        mismatched_scalar_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              identifier: Int
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(mismatched_scalar_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="clashing_name",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )

    def test_invalid_edge_property_fields_non_null_scalar_mismatch_normal_scalar(self):
        non_null_field_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            type Person {
              identifier: Int!
            }

            type SchemaQuery {
              Person: Person
            }
        """
        )
        with self.assertRaises(InvalidCrossSchemaEdgeError):
            merge_schemas(
                OrderedDict(
                    [
                        ("first", parse(ISS.basic_schema)),
                        ("second", parse(non_null_field_schema)),
                    ]
                ),
                [
                    CrossSchemaEdgeDescriptor(
                        edge_name="example_edge",
                        outbound_field_reference=FieldReference(
                            schema_id="first",
                            type_name="Human",
                            field_name="id",
                        ),
                        inbound_field_reference=FieldReference(
                            schema_id="second",
                            type_name="Person",
                            field_name="identifier",
                        ),
                        out_edge_only=False,
                    ),
                ],
            )


class TestMergeSchemasCrossSchemaEdgesWithSubclasses(unittest.TestCase):
    def get_type_equivalence_hints(self, schema_id_to_ast, type_equivalence_hints_names):
        """Get type_equivalence_hints for input into merge_schemas.

        Args:
            schema_id_to_ast: Dict[str, Document]
            type_equivalence_hints_names: Dict[str, str], mapping object type name to its
                                          equivalent union type name

        Returns:
            Dict[GraphQLObjectType, GraphQLUnionType], mapping object type to its equivalent
            union type
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

    def test_edge_outbound_field_reference_interface(self):
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.basic_schema)),
                    ("second", parse(ISS.interface_with_subclasses_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Individual",
                        field_name="ID",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Individual: Individual
              President: President
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              out_example_edge: [Individual] @stitch(source_field: "id", sink_field: "ID")
            }

            interface Individual {
              ID: String
              in_example_edge: [Human] @stitch(source_field: "ID", sink_field: "id")
            }

            type President implements Individual {
              ID: String
              year: Int
              in_example_edge: [Human] @stitch(source_field: "ID", sink_field: "id")
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_edge_inbound_field_reference_interface(self):
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.basic_schema)),
                    ("second", parse(ISS.interface_with_subclasses_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Individual",
                        field_name="ID",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Individual: Individual
              President: President
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              in_example_edge: [Individual] @stitch(source_field: "id", sink_field: "ID")
            }

            interface Individual {
              ID: String
              out_example_edge: [Human] @stitch(source_field: "ID", sink_field: "id")
            }

            type President implements Individual {
              ID: String
              year: Int
              out_example_edge: [Human] @stitch(source_field: "ID", sink_field: "id")
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_edge_both_sides_interfaces(self):
        additional_interface_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            interface Person {
              identifier: String
              name: String
            }

            type Politician implements Person {
              identifier: String
              name: String
              party: String
            }

            type SchemaQuery {
              Person: Person
              Politician: Politician
            }
        """
        )
        merged_schema = merge_schemas(
            OrderedDict(
                [
                    ("first", parse(ISS.interface_with_subclasses_schema)),
                    ("second", parse(additional_interface_schema)),
                ]
            ),
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Individual",
                        field_name="ID",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=False,
                ),
            ],
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Individual: Individual
              President: President
              Person: Person
              Politician: Politician
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            interface Individual {
              ID: String
              out_example_edge: [Person] @stitch(source_field: "ID", sink_field: "identifier")
            }

            type President implements Individual {
              ID: String
              year: Int
              out_example_edge: [Person] @stitch(source_field: "ID", sink_field: "identifier")
            }

            interface Person {
              identifier: String
              name: String
              in_example_edge: [Individual] @stitch(source_field: "identifier", sink_field: "ID")
            }

            type Politician implements Person {
              identifier: String
              name: String
              party: String
              in_example_edge: [Individual] @stitch(source_field: "identifier", sink_field: "ID")
            }
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_edge_outbound_field_reference_union_equivalent_type(self):
        schema_id_to_ast = OrderedDict(
            [
                ("first", parse(ISS.basic_schema)),
                ("second", parse(ISS.union_with_subclasses_schema)),
            ]
        )
        merged_schema = merge_schemas(
            schema_id_to_ast,
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Human",
                        field_name="id",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=False,
                ),
            ],
            self.get_type_equivalence_hints(schema_id_to_ast, {"Person": "PersonOrKid"}),
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Human: Human
              Person: Person
              Kid: Kid
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Human {
              id: String
              out_example_edge: [PersonOrKid] @stitch(source_field: "id", sink_field: "identifier")
            }

            type Person {
              identifier: String
              in_example_edge: [Human] @stitch(source_field: "identifier", sink_field: "id")
            }

            type Kid {
              identifier: String
              age: Int
              in_example_edge: [Human] @stitch(source_field: "identifier", sink_field: "id")
            }

            union PersonOrKid = Person | Kid
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_edge_both_sides_union_equivalent_type(self):
        additional_union_schema = dedent(
            """\
            schema {
              query: SchemaQuery
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Individual {
              ID: String
            }

            type President {
              ID: String
              year: Int
            }

            union IndivOrPres = Individual | President

            type SchemaQuery {
              Individual: Individual
              President: President
            }
        """
        )
        schema_id_to_ast = OrderedDict(
            [
                ("first", parse(ISS.union_with_subclasses_schema)),
                ("second", parse(additional_union_schema)),
            ]
        )
        merged_schema = merge_schemas(
            schema_id_to_ast,
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Individual",
                        field_name="ID",
                    ),
                    out_edge_only=False,
                ),
            ],
            self.get_type_equivalence_hints(
                schema_id_to_ast, {"Person": "PersonOrKid", "Individual": "IndivOrPres"}
            ),
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Person: Person
              Kid: Kid
              Individual: Individual
              President: President
            }

            type Person {
              identifier: String
              out_example_edge: [IndivOrPres] @stitch(source_field: "identifier", sink_field: "ID")
            }

            type Kid {
              identifier: String
              age: Int
              out_example_edge: [IndivOrPres] @stitch(source_field: "identifier", sink_field: "ID")
            }

            union PersonOrKid = Person | Kid

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            type Individual {
              ID: String
              in_example_edge: [PersonOrKid] @stitch(source_field: "ID", sink_field: "identifier")
            }

            type President {
              ID: String
              year: Int
              in_example_edge: [PersonOrKid] @stitch(source_field: "ID", sink_field: "identifier")
            }

            union IndivOrPres = Individual | President
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))

    def test_edge_outbound_interface_inbound_union_equivalent_type(self):
        schema_id_to_ast = OrderedDict(
            [
                ("first", parse(ISS.interface_with_subclasses_schema)),
                ("second", parse(ISS.union_with_subclasses_schema)),
            ]
        )
        merged_schema = merge_schemas(
            schema_id_to_ast,
            [
                CrossSchemaEdgeDescriptor(
                    edge_name="example_edge",
                    outbound_field_reference=FieldReference(
                        schema_id="first",
                        type_name="Individual",
                        field_name="ID",
                    ),
                    inbound_field_reference=FieldReference(
                        schema_id="second",
                        type_name="Person",
                        field_name="identifier",
                    ),
                    out_edge_only=False,
                ),
            ],
            self.get_type_equivalence_hints(schema_id_to_ast, {"Person": "PersonOrKid"}),
        )
        merged_schema_string = dedent(
            """\
            schema {
              query: RootSchemaQuery
            }

            type RootSchemaQuery {
              Individual: Individual
              President: President
              Person: Person
              Kid: Kid
            }

            directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

            interface Individual {
              ID: String
              out_example_edge: [PersonOrKid] @stitch(source_field: "ID", sink_field: "identifier")
            }

            type President implements Individual {
              ID: String
              year: Int
              out_example_edge: [PersonOrKid] @stitch(source_field: "ID", sink_field: "identifier")
            }

            type Person {
              identifier: String
              in_example_edge: [Individual] @stitch(source_field: "identifier", sink_field: "ID")
            }

            type Kid {
              identifier: String
              age: Int
              in_example_edge: [Individual] @stitch(source_field: "identifier", sink_field: "ID")
            }

            union PersonOrKid = Person | Kid
        """
        )
        self.assertEqual(merged_schema_string, print_ast(merged_schema.schema_ast))
