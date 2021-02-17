# Copyright 2017-present Kensho Technologies, LLC.
"""Common test data and helper functions."""
from collections import namedtuple
from inspect import getmembers, isfunction
from pprint import pformat
import re
from typing import Dict, List, Optional, Set, Tuple, Union, cast
from unittest import TestCase

from graphql import GraphQLList, build_schema, lexicographic_sort_schema, print_schema
from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType, GraphQLUnionType
from graphql.type.schema import GraphQLSchema
from pyorient.orient import OrientDB
import six
import sqlalchemy
from sqlalchemy.dialects import mssql, postgresql

from ..compiler.compiler_entities import BasicBlock
from ..compiler.subclass import compute_subclass_sets
from ..debugging_utils import pretty_print_gremlin, pretty_print_match
from ..global_utils import is_same_type
from ..macros import MacroRegistry, create_macro_registry, register_macro_edge
from ..query_formatting.graphql_formatting import pretty_print_graphql
from ..schema import (
    ClassToFieldTypeOverridesType,
    GraphQLSchemaFieldType,
    TypeEquivalenceHintsType,
    is_vertex_field_name,
)
from ..schema.schema_info import (
    CommonSchemaInfo,
    CompositeJoinDescriptor,
    DirectJoinDescriptor,
    JoinDescriptor,
    SQLAlchemySchemaInfo,
    make_sqlalchemy_schema_info,
)
from ..schema_generation.orientdb import get_graphql_schema_from_orientdb_schema_data
from ..schema_generation.orientdb.schema_graph_builder import get_orientdb_schema_graph
from ..schema_generation.orientdb.utils import (
    ORIENTDB_INDEX_RECORDS_QUERY,
    ORIENTDB_SCHEMA_RECORDS_QUERY,
)
from ..schema_generation.schema_graph import SchemaGraph


# The strings which we will be comparing have newlines and spaces we'd like to get rid of,
# so we can compare expected and produced emitted code irrespective of whitespace.
WHITESPACE_PATTERN = re.compile("[\t\n ]*", flags=re.UNICODE)

# flag to indicate a test component should be skipped
SKIP_TEST = "SKIP"

# Text representation of a GraphQL schema generated from OrientDB.
# This schema isn't meant to be a paragon of good schema design.
# Instead, it aims to capture as many real-world edge cases as possible,
# without requiring a massive number of types and interfaces.
SCHEMA_TEXT = """
    schema {
        query: RootSchemaQuery
    }

    directive @filter(
        \"\"\"Name of the filter operation to perform.\"\"\"
        op_name: String!

        \"\"\"List of string operands for the operator.\"\"\"
        value: [String!]
    ) repeatable on FIELD | INLINE_FRAGMENT

    directive @tag(
        \"\"\"Name to apply to the given property field.\"\"\"
        tag_name: String!
    ) on FIELD

    directive @output(
        \"\"\"What to designate the output field generated from this property field.\"\"\"
        out_name: String!
    ) on FIELD

    directive @output_source on FIELD

    directive @optional on FIELD

    directive @recurse(
        \"\"\"
        Recurse up to this many times on this edge. A depth of 1 produces the current \
vertex and its immediate neighbors along the given edge.
        \"\"\"
        depth: Int!
    ) on FIELD

    directive @fold on FIELD

    directive @macro_edge on FIELD_DEFINITION

    directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION

    type Animal implements Entity & UniquelyIdentifiable {
        _x_count: Int
        alias: [String]
        birthday: Date
        color: String
        description: String
        in_Animal_ParentOf: [Animal]
        in_Entity_Related: [Entity]
        name: String
        net_worth: Decimal
        out_Animal_BornAt: [BirthEvent]
        out_Animal_FedAt: [FeedingEvent]
        out_Animal_ImportantEvent: [Union__BirthEvent__Event__FeedingEvent]
        out_Animal_LivesIn: [Location]
        out_Animal_OfSpecies: [Species]
        out_Animal_ParentOf: [Animal]
        out_Entity_Related: [Entity]
        uuid: ID
    }

    type BirthEvent implements Entity & UniquelyIdentifiable {
        _x_count: Int
        alias: [String]
        description: String
        event_date: DateTime
        in_Animal_BornAt: [Animal]
        in_Animal_ImportantEvent: [Animal]
        in_Entity_Related: [Entity]
        in_Event_RelatedEvent: [Union__BirthEvent__Event__FeedingEvent]
        name: String
        out_Entity_Related: [Entity]
        out_Event_RelatedEvent: [Union__BirthEvent__Event__FeedingEvent]
        uuid: ID
    }

    \"\"\"
    The `Date` scalar type represents day-accuracy date objects.
    Values are serialized following the ISO-8601 datetime format specification,
    for example "2017-03-21". Serialization and parsing support is guaranteed for the format
    described here, with the year, month and day fields included and separated by dashes as
    in the example. Implementations are allowed to support additional serialization formats,
    if they so choose.
    \"\"\"
    scalar Date

    \"\"\"
    The `DateTime` scalar type represents timezone-naive timestamps with up to microsecond
    accuracy. Values are serialized following the ISO-8601 datetime format specification,
    for example "2017-03-21T12:34:56.012345" or "2017-03-21T12:34:56". Serialization and
    parsing support is guaranteed for the format described here, with all fields down to
    and including seconds required to be included, and fractional seconds optional, as in
    the example. Implementations are allowed to support additional serialization formats,
    if they so choose.
    \"\"\"
    scalar DateTime

    \"\"\"
    The `Decimal` scalar type is an arbitrary-precision decimal number object useful
    for representing values that should never be rounded, such as currency amounts.
    Values are allowed to be transported as either a native Decimal type, if the
    underlying transport allows that, or serialized as strings in decimal format,
    without thousands separators and using a "." as the decimal separator: for
    example, "12345678.012345".
    \"\"\"
    scalar Decimal

    interface Entity {
        _x_count: Int
        alias: [String]
        description: String
        in_Entity_Related: [Entity]
        name: String
        out_Entity_Related: [Entity]
        uuid: ID
    }

    type Event implements Entity & UniquelyIdentifiable {
        _x_count: Int
        alias: [String]
        description: String
        event_date: DateTime
        in_Animal_ImportantEvent: [Animal]
        in_Entity_Related: [Entity]
        in_Event_RelatedEvent: [Union__BirthEvent__Event__FeedingEvent]
        name: String
        out_Entity_Related: [Entity]
        out_Event_RelatedEvent: [Union__BirthEvent__Event__FeedingEvent]
        uuid: ID
    }

    type FeedingEvent implements Entity & UniquelyIdentifiable {
        _x_count: Int
        alias: [String]
        description: String
        event_date: DateTime
        in_Animal_FedAt: [Animal]
        in_Animal_ImportantEvent: [Animal]
        in_Entity_Related: [Entity]
        in_Event_RelatedEvent: [Union__BirthEvent__Event__FeedingEvent]
        name: String
        out_Entity_Related: [Entity]
        out_Event_RelatedEvent: [Union__BirthEvent__Event__FeedingEvent]
        uuid: ID
    }

    type Food implements Entity & UniquelyIdentifiable {
        _x_count: Int
        alias: [String]
        description: String
        in_Entity_Related: [Entity]
        in_Species_Eats: [Species]
        name: String
        out_Entity_Related: [Entity]
        uuid: ID
    }

    type FoodOrSpecies implements Entity & UniquelyIdentifiable {
        _x_count: Int
        alias: [String]
        description: String
        in_Entity_Related: [Entity]
        in_Species_Eats: [Species]
        name: String
        out_Entity_Related: [Entity]
        uuid: ID
    }

    type Location implements Entity & UniquelyIdentifiable {
        _x_count: Int
        alias: [String]
        description: String
        in_Animal_LivesIn: [Animal]
        in_Entity_Related: [Entity]
        name: String
        out_Entity_Related: [Entity]
        uuid: ID
    }

    type RootSchemaQuery {
        Animal: [Animal]
        BirthEvent: [BirthEvent]
        Entity: [Entity]
        Event: [Event]
        FeedingEvent: [FeedingEvent]
        Food: [Food]
        FoodOrSpecies: [FoodOrSpecies]
        Location: [Location]
        Species: [Species]
        UniquelyIdentifiable: [UniquelyIdentifiable]
    }

    type Species implements Entity & UniquelyIdentifiable {
        _x_count: Int
        alias: [String]
        description: String
        in_Animal_OfSpecies: [Animal]
        in_Entity_Related: [Entity]
        in_Species_Eats: [Species]
        limbs: Int
        name: String
        out_Entity_Related: [Entity]
        out_Species_Eats: [Union__Food__FoodOrSpecies__Species]
        uuid: ID
    }

    union Union__BirthEvent__Event__FeedingEvent = BirthEvent | Event | FeedingEvent

    union Union__Food__FoodOrSpecies__Species = Food | FoodOrSpecies | Species

    interface UniquelyIdentifiable {
        _x_count: Int
        uuid: ID
    }
"""

VALID_MACROS_TEXT = [
    (
        """\
    {
        Entity @macro_edge_definition(name: "out_Entity_AlmostRelated") {
            out_Entity_Related {
                out_Entity_Related @macro_edge_target{
                    uuid
                }
            }
        }
    }
    """,
        {},
    ),
    (
        """\
    {
        Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
            out_Animal_ParentOf {
                out_Animal_ParentOf @macro_edge_target {
                    uuid
                }
            }
        }
    }""",
        {},
    ),
    (
        """\
    {
        Animal @macro_edge_definition(name: "out_Animal_GrandchildrenCalledNate") {
            out_Animal_ParentOf {
                out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$wanted"])
                                    @macro_edge_target {
                    uuid
                }
            }
        }
    }""",
        {
            "wanted": "Nate",
        },
    ),
    (
        """\
    {
        Animal @macro_edge_definition(name: "out_Animal_RichSiblings") {
            in_Animal_ParentOf {
                net_worth @tag(tag_name: "parent_net_worth")
                out_Animal_ParentOf @macro_edge_target {
                    net_worth @filter(op_name: ">", value: ["%parent_net_worth"])
                }
            }
        }
    }""",
        {},
    ),
    (
        """\
    {
        Location @macro_edge_definition(name: "out_Location_Orphans") {
            in_Animal_LivesIn @macro_edge_target {
                in_Animal_ParentOf @filter(op_name: "has_edge_degree", value: ["$num_parents"])
                                   @optional {
                    uuid
                }
            }
        }
    }""",
        {
            "num_parents": 0,
        },
    ),
    # Testing that @optional that doesn't include @macro_edge_target is okay.
    (
        """\
    {
        Animal @macro_edge_definition(name: "out_Animal_MaybeYoungerSiblings") {
            out_Animal_BornAt @optional {
                event_date @tag(tag_name: "birthday")
            }
            in_Animal_ParentOf {
                out_Animal_ParentOf @macro_edge_target {
                    out_Animal_BornAt @optional {
                        event_date @filter(op_name: ">", value: ["%birthday"])
                    }
                }
            }
        }
    }""",
        {},
    ),
    (
        """\
    {
        Animal @macro_edge_definition(name: "out_Animal_RichYoungerSiblings") {
            net_worth @tag(tag_name: "net_worth")
            out_Animal_BornAt {
                event_date @tag(tag_name: "birthday")
            }
            in_Animal_ParentOf {
                out_Animal_ParentOf @macro_edge_target {
                    net_worth @filter(op_name: ">", value: ["%net_worth"])
                    out_Animal_BornAt {
                        event_date @filter(op_name: "<", value: ["%birthday"])
                    }
                }
            }
        }
    }""",
        {},
    ),
    # The same as out_AnimalRichYoungerSiblings, but with a filter after the target.
    (
        """\
    {
        Animal @macro_edge_definition(name: "out_Animal_RichYoungerSiblings_2") {
            net_worth @tag(tag_name: "net_worth")
            in_Animal_ParentOf {
                out_Animal_ParentOf @macro_edge_target {
                    net_worth @filter(op_name: ">", value: ["%net_worth"])
                    out_Animal_BornAt {
                        event_date @tag(tag_name: "birthday")
                    }
                }
            }
            out_Animal_BornAt {
                event_date @filter(op_name: ">", value: ["%birthday"])
            }
        }
    }""",
        {},
    ),
    (
        """\
    {
        Animal @macro_edge_definition(name: "out_Animal_RelatedFood") {
            in_Entity_Related {
                ... on Food @macro_edge_target {
                    uuid
                }
            }
        }
    }""",
        {},
    ),
    (
        """\
    {
        Animal @macro_edge_definition(name: "out_Animal_RelatedEntity") {
            in_Entity_Related {
                ... on Entity @macro_edge_target {
                    uuid
                }
            }
        }
    }""",
        {},
    ),
]


# A class holding all necessary backend-specific testing utilities.
BackendTester = namedtuple(
    "BackendTester",
    (
        # Backend to be tested
        "backend"
        # Returns whether two emitted queries are the same, up to differences in syntax/whitespace
        "compare_queries",
        # An instance of backend.SchemaInfoClass consistend with the standard testing schema.
        "schema_info",
        # Given a SchemaInfo and a connection pool to a database, install the given schema into
        # the database, erasing content if necessary.
        "setup_schema"
        # Given a SchemaInfo, a dict representation of data fitting the schema,
        # and a connection pool to a database with the same schema,
        # install the given data into the database, erasing any existing data.
        "setup_data",
    ),
)


def get_function_names_from_module(module):
    """Return a set of function names present in a given module."""
    return {member for member, member_type in getmembers(module) if isfunction(member_type)}


def get_test_function_names_from_class(test_class):
    """Return a set of test function names present in a given TestCase class."""
    if not issubclass(test_class, TestCase):
        raise AssertionError("Received non-test class {} as input.".format(test_class))
    member_dict = test_class.__dict__
    return {
        member
        for member in member_dict
        if isfunction(member_dict[member]) and member[:5] == "test_"
    }


def transform(emitted_output: str) -> str:
    """Transform emitted_output into a unique representation, regardless of lines / indentation."""
    return WHITESPACE_PATTERN.sub("", emitted_output)


def _get_mismatch_message(
    expected_blocks: List[BasicBlock], received_blocks: List[BasicBlock]
) -> str:
    """Create a well-formated error message indicating that two lists of blocks are mismatched."""
    pretty_expected = pformat(expected_blocks)
    pretty_received = pformat(received_blocks)
    return "{}\n\n!=\n\n{}".format(pretty_expected, pretty_received)


def compare_ir_blocks(
    test_case: TestCase, expected_blocks: List[BasicBlock], received_blocks: List[BasicBlock]
) -> None:
    """Compare the expected and received IR blocks."""
    mismatch_message = _get_mismatch_message(expected_blocks, received_blocks)

    if len(expected_blocks) != len(received_blocks):
        test_case.fail("Not the same number of blocks:\n\n{}".format(mismatch_message))

    for i, (expected, received) in enumerate(zip(expected_blocks, received_blocks)):
        test_case.assertEqual(
            expected,
            received,
            msg=(
                "Blocks at position {} were different: {} vs {}\n\n"
                "{}".format(i, expected, received, mismatch_message)
            ),
        )


def compare_graphql(test_case: TestCase, expected: str, received: str) -> None:
    """Compare the expected and received GraphQL code, ignoring whitespace."""
    msg = "\n{}\n\n!=\n\n{}".format(pretty_print_graphql(expected), pretty_print_graphql(received))
    compare_ignoring_whitespace(test_case, expected, received, msg)


def compare_match(
    test_case: TestCase,
    expected: str,
    received: str,
    parameterized: bool = True,
) -> None:
    """Compare the expected and received MATCH code, ignoring whitespace."""
    msg = "\n{}\n\n!=\n\n{}".format(
        pretty_print_match(expected, parameterized=parameterized),
        pretty_print_match(received, parameterized=parameterized),
    )
    compare_ignoring_whitespace(test_case, expected, received, msg)


def compare_sql(test_case: TestCase, expected: str, received: str) -> None:
    """Compare the expected and received SQL query, ignoring whitespace."""
    msg = "\n{}\n\n!=\n\n{}".format(expected, received)
    compare_ignoring_whitespace(test_case, expected, received, msg)


def compare_gremlin(
    test_case: TestCase,
    expected: str,
    received: str,
) -> None:
    """Compare the expected and received Gremlin code, ignoring whitespace."""
    msg = "\n{}\n\n!=\n\n{}".format(pretty_print_gremlin(expected), pretty_print_gremlin(received))
    compare_ignoring_whitespace(test_case, expected, received, msg)


def compare_cypher(test_case: TestCase, expected: str, received: str) -> None:
    """Compare the expected and received Cypher query, ignoring whitespace."""
    msg = "\n{}\n\n!=\n\n{}".format(expected, received)
    compare_ignoring_whitespace(test_case, expected, received, msg)


def compare_input_metadata(
    test_case: TestCase,
    expected: Dict[str, GraphQLSchemaFieldType],
    received: Dict[str, GraphQLSchemaFieldType],
) -> None:
    """Compare two dicts of input metadata, using proper GraphQL type comparison operators."""
    # First, assert that the sets of keys in both dicts are equal.
    test_case.assertEqual(set(six.iterkeys(expected)), set(six.iterkeys(received)))

    # Then, compare the values for each key in both dicts.
    for key in six.iterkeys(expected):
        expected_value = expected[key]
        received_value = received[key]

        test_case.assertTrue(
            is_same_type(expected_value, received_value),
            msg="{} != {}".format(str(expected_value), str(received_value)),
        )


def compare_ignoring_whitespace(
    test_case: TestCase, expected: str, received: str, msg: Optional[str]
) -> None:
    """Compare expected and received code, ignoring whitespace, with the given failure message."""
    test_case.assertEqual(transform(expected), transform(received), msg=msg)


def _lexicographic_sort_schema_text(schema_text: str) -> str:
    """Sort the schema types and fields in a lexicographic order."""
    return print_schema(lexicographic_sort_schema(build_schema(schema_text)))


def compare_schema_texts_order_independently(
    test_case: TestCase,
    expected_schema_text: str,
    received_schema_text: str,
) -> None:
    """Compare expected and received schema texts, ignoring order of definitions."""
    sorted_expected_schema_text = _lexicographic_sort_schema_text(expected_schema_text)
    sorted_received_schema_text = _lexicographic_sort_schema_text(received_schema_text)
    msg = "\n{}\n\n!=\n\n{}".format(sorted_expected_schema_text, sorted_received_schema_text)
    compare_ignoring_whitespace(
        test_case, sorted_expected_schema_text, sorted_received_schema_text, msg
    )


def get_schema() -> GraphQLSchema:
    """Get a schema object for testing."""
    return build_schema(SCHEMA_TEXT)


def get_type_equivalence_hints() -> TypeEquivalenceHintsType:
    """Get the default type_equivalence_hints used for testing."""
    schema = get_schema()
    type_equivalence_hints: Dict[
        Union[GraphQLInterfaceType, GraphQLObjectType], GraphQLUnionType
    ] = {}
    for key, value in [
        ("Event", "Union__BirthEvent__Event__FeedingEvent"),
        ("FoodOrSpecies", "Union__Food__FoodOrSpecies__Species"),
    ]:
        key_type = schema.get_type(key)
        value_type = schema.get_type(value)
        if (
            key_type
            and value_type
            and (
                isinstance(key_type, GraphQLInterfaceType)
                or isinstance(key_type, GraphQLObjectType)
            )
            and isinstance(value_type, GraphQLUnionType)
        ):
            type_equivalence_hints[key_type] = value_type
    return type_equivalence_hints


def get_common_schema_info() -> CommonSchemaInfo:
    """Get the default CommonSchemaInfo used for testing."""
    return CommonSchemaInfo(get_schema(), get_type_equivalence_hints())


def _get_schema_without_list_valued_property_fields() -> GraphQLSchema:
    """Get the default testing schema, skipping any list-valued property fields it has."""
    schema = get_schema()

    types_with_fields = (GraphQLInterfaceType, GraphQLObjectType)
    for type_name, graphql_type in six.iteritems(schema.type_map):
        if isinstance(graphql_type, types_with_fields):
            if type_name != "RootSchemaQuery" and not type_name.startswith("__"):
                fields_to_pop = []
                for field_name, field_type in six.iteritems(graphql_type.fields):
                    if not is_vertex_field_name(field_name):
                        if isinstance(field_type.type, GraphQLList):
                            fields_to_pop.append(field_name)
                for field_to_pop in fields_to_pop:
                    graphql_type.fields.pop(field_to_pop)

    return schema


def get_sqlalchemy_schema_info(dialect: str = "mssql") -> SQLAlchemySchemaInfo:
    """Get a SQLAlchemySchemaInfo for testing."""
    # We don't support list-valued property fields in SQL for now.
    schema = _get_schema_without_list_valued_property_fields()
    type_equivalence_hints = get_type_equivalence_hints()

    sqlalchemy_metadata = sqlalchemy.MetaData()

    uuid_type = sqlalchemy.String(36)

    tables = {
        "Animal": sqlalchemy.Table(
            "Animal",
            sqlalchemy_metadata,
            sqlalchemy.Column("birthday", sqlalchemy.DateTime, nullable=False),
            sqlalchemy.Column("color", sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column("description", sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column("parent", sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column("related_entity", sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column("name", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("net_worth", sqlalchemy.Integer, nullable=True),
            sqlalchemy.Column("fed_at", uuid_type, nullable=True),
            sqlalchemy.Column("birth_date", sqlalchemy.DateTime, nullable=True),
            sqlalchemy.Column("birth_uuid", uuid_type, nullable=True),
            sqlalchemy.Column("lives_in", uuid_type, nullable=True),
            sqlalchemy.Column("important_event", sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column("species", sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            schema=("db_1." if dialect == "mssql" else "") + "schema_1",
        ),
        "BirthEvent": sqlalchemy.Table(
            "BirthEvent",
            sqlalchemy_metadata,
            sqlalchemy.Column("description", sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("event_date", sqlalchemy.DateTime, nullable=False, primary_key=True),
            sqlalchemy.Column("related_event", uuid_type, primary_key=False),
            schema=("db_1." if dialect == "mssql" else "") + "schema_1",
        ),
        "Entity": sqlalchemy.Table(
            "Entity",
            sqlalchemy_metadata,
            sqlalchemy.Column("description", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("related_entity", uuid_type, nullable=True),
            schema=("db_1." if dialect == "mssql" else "") + "schema_1",
        ),
        "Event": sqlalchemy.Table(
            "Event",
            sqlalchemy_metadata,
            sqlalchemy.Column("description", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("event_date", sqlalchemy.DateTime, nullable=False),
            sqlalchemy.Column("related_event", uuid_type, primary_key=False),
            schema=("db_2." if dialect == "mssql" else "") + "schema_1",
        ),
        "FeedingEvent": sqlalchemy.Table(
            "FeedingEvent",
            sqlalchemy_metadata,
            sqlalchemy.Column("description", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("event_date", sqlalchemy.DateTime, nullable=False),
            sqlalchemy.Column("related_event", uuid_type, primary_key=False),
            schema=("db_2." if dialect == "mssql" else "") + "schema_1",
        ),
        "Food": sqlalchemy.Table(
            "Food",
            sqlalchemy_metadata,
            sqlalchemy.Column("description", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String(40), nullable=False),
            schema=("db_2." if dialect == "mssql" else "") + "schema_2",
        ),
        "FoodOrSpecies": sqlalchemy.Table(
            "FoodOrSpecies",
            sqlalchemy_metadata,
            sqlalchemy.Column("description", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String(40), nullable=False),
            schema=("db_2." if dialect == "mssql" else "") + "schema_2",
        ),
        "Location": sqlalchemy.Table(
            "Location",
            sqlalchemy_metadata,
            sqlalchemy.Column("description", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String(40), nullable=False),
            schema=("db_1." if dialect == "mssql" else "") + "schema_1",
        ),
        "Species": sqlalchemy.Table(
            "Species",
            sqlalchemy_metadata,
            sqlalchemy.Column("description", sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            sqlalchemy.Column("name", sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column("eats", uuid_type, nullable=True),
            sqlalchemy.Column("limbs", sqlalchemy.Integer, nullable=True),
            sqlalchemy.Column("related_entity", uuid_type, nullable=True),
            schema=("db_1." if dialect == "mssql" else "") + "schema_1",
        ),
        "UniquelyIdentifiable": sqlalchemy.Table(
            "UniquelyIdentifiable",
            sqlalchemy_metadata,
            sqlalchemy.Column("uuid", uuid_type, primary_key=True),
            schema=("db_1." if dialect == "mssql" else "") + "schema_1",
        ),
    }

    # Compute the subclass sets, including union types
    subclasses = compute_subclass_sets(schema, type_equivalence_hints=type_equivalence_hints)
    for object_type, equivalent_union_type in six.iteritems(type_equivalence_hints):
        subclasses[equivalent_union_type.name] = subclasses[object_type.name]
        subclasses[equivalent_union_type.name].add(object_type.name)

    # HACK(bojanserafimov): Some of these edges are many-to-many, but I've represented them
    #                       as many-to-one edges. If I didn't, I'd have to implement many-to-many
    #                       edges before I can get any tests to run, because most tests use
    #                       these edges.
    edges = [
        {
            "name": "Animal_ParentOf",
            "from_table": "Animal",
            "to_table": "Animal",
            "column_pairs": {("uuid", "parent")},
        },
        {
            "name": "Animal_OfSpecies",
            "from_table": "Animal",
            "to_table": "Species",
            "column_pairs": {("species", "uuid")},
        },
        {
            "name": "Animal_FedAt",
            "from_table": "Animal",
            "to_table": "FeedingEvent",
            "column_pairs": {("fed_at", "uuid")},
        },
        {
            "name": "Animal_BornAt",
            "from_table": "Animal",
            "to_table": "BirthEvent",
            "column_pairs": {
                ("birth_uuid", "uuid"),
                ("birth_date", "event_date"),
            },
        },
        {
            "name": "Animal_LivesIn",
            "from_table": "Animal",
            "to_table": "Location",
            "column_pairs": {("lives_in", "uuid")},
        },
        {
            "name": "Animal_ImportantEvent",
            "from_table": "Animal",
            "to_table": "Union__BirthEvent__Event__FeedingEvent",
            "column_pairs": {("important_event", "uuid")},
        },
        {
            "name": "Species_Eats",
            "from_table": "Species",
            "to_table": "Union__Food__FoodOrSpecies__Species",
            "column_pairs": {("eats", "uuid")},
        },
        {
            "name": "Entity_Related",
            "from_table": "Entity",
            "to_table": "Entity",
            "column_pairs": {("related_entity", "uuid")},
        },
        {
            "name": "Event_RelatedEvent",
            "from_table": "Union__BirthEvent__Event__FeedingEvent",
            "to_table": "Union__BirthEvent__Event__FeedingEvent",
            "column_pairs": {("related_event", "uuid")},
        },
        {
            "name": "Entity_Alias",
            "from_table": "Entity",
            "to_table": "Alias",
            "column_pairs": {("uuid", "alias_for")},
        },
    ]

    # Create the appropriate JoinDescriptor for each specified edge, in both the
    # in and out directions.
    join_descriptors: Dict[str, Dict[str, JoinDescriptor]] = {}
    for edge in edges:
        column_pairs = cast(Set[Tuple[str, str]], edge["column_pairs"])
        from_table = cast(str, edge["from_table"])
        to_table = cast(str, edge["to_table"])
        if len(column_pairs) > 1:
            join_descriptors.setdefault(from_table, {})[
                "out_{}".format(edge["name"])
            ] = CompositeJoinDescriptor(column_pairs)
            join_descriptors.setdefault(to_table, {})[
                "in_{}".format(edge["name"])
            ] = CompositeJoinDescriptor(
                {(to_column, from_column) for from_column, to_column in column_pairs}
            )
        elif len(column_pairs) == 1:
            from_column, to_column = next(iter(column_pairs))
            join_descriptors.setdefault(from_table, {})[
                "out_{}".format(edge["name"])
            ] = DirectJoinDescriptor(from_column, to_column)
            join_descriptors.setdefault(to_table, {})[
                "in_{}".format(edge["name"])
            ] = DirectJoinDescriptor(to_column, from_column)

    # Inherit join_descriptors from superclasses
    # TODO(bojanserafimov): Properties can be inferred too, instead of being explicitly inherited.
    for class_name, subclass_set in six.iteritems(subclasses):
        for subclass in subclass_set:
            for edge_name, join_info in six.iteritems(join_descriptors.get(class_name, {})):
                join_descriptors.setdefault(subclass, {})[edge_name] = join_info
    if dialect == "postgresql":
        sqlalchemy_compiler_dialect = postgresql.dialect()
    elif dialect == "mssql":
        sqlalchemy_compiler_dialect = mssql.dialect()
    else:
        raise AssertionError("Unrecognized dialect {}".format(dialect))
    return make_sqlalchemy_schema_info(
        schema, type_equivalence_hints, sqlalchemy_compiler_dialect, tables, join_descriptors
    )


def generate_schema_graph(orientdb_client: OrientDB) -> SchemaGraph:
    """Generate SchemaGraph from a pyorient client."""
    schema_records = orientdb_client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
    schema_data = [x.oRecordData for x in schema_records]
    index_records = orientdb_client.command(ORIENTDB_INDEX_RECORDS_QUERY)
    index_query_data = [x.oRecordData for x in index_records]
    return get_orientdb_schema_graph(schema_data, index_query_data)


def generate_schema(
    orientdb_client: OrientDB,
    class_to_field_type_overrides: Optional[ClassToFieldTypeOverridesType] = None,
    hidden_classes: Optional[Set[str]] = None,
) -> Tuple[GraphQLSchema, TypeEquivalenceHintsType]:
    """Generate schema and type equivalence dict from a pyorient client."""
    schema_records = orientdb_client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
    schema_data = [x.oRecordData for x in schema_records]
    return get_graphql_schema_from_orientdb_schema_data(
        schema_data, class_to_field_type_overrides, hidden_classes
    )


def get_empty_test_macro_registry() -> MacroRegistry:
    """Return a MacroRegistry with appropriate type_equivalence_hints and subclass_set."""
    schema = get_schema()
    type_equivalence_hints = cast(
        TypeEquivalenceHintsType,
        {
            schema.get_type("Event"): schema.get_type("Union__BirthEvent__Event__FeedingEvent"),
        },
    )
    subclass_sets = compute_subclass_sets(schema, type_equivalence_hints)
    macro_registry = create_macro_registry(schema, type_equivalence_hints, subclass_sets)
    return macro_registry


def get_test_macro_registry() -> MacroRegistry:
    """Return a MacroRegistry object containing macros used in tests."""
    macro_registry = get_empty_test_macro_registry()
    for graphql, args in VALID_MACROS_TEXT:
        register_macro_edge(macro_registry, graphql, args)
    return macro_registry
