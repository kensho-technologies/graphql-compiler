# Copyright 2017-present Kensho Technologies, LLC.
"""Common test data and helper functions."""
from pprint import pformat
import re

from graphql import parse
from graphql.utils.build_ast_schema import build_ast_schema
import six

from graphql_compiler import get_graphql_schema_from_orientdb_schema_data
from graphql_compiler.schema_generation.schema_graph import SchemaGraph
from graphql_compiler.schema_generation.utils import ORIENTDB_SCHEMA_RECORDS_QUERY

from ..compiler.subclass import compute_subclass_sets
from ..debugging_utils import pretty_print_gremlin, pretty_print_match
from ..macros import create_macro_registry, register_macro_edge
from ..query_formatting.graphql_formatting import pretty_print_graphql


# The strings which we will be comparing have newlines and spaces we'd like to get rid of,
# so we can compare expected and produced emitted code irrespective of whitespace.
WHITESPACE_PATTERN = re.compile(u'[\t\n ]*', flags=re.UNICODE)

# flag to indicate a test component should be skipped
SKIP_TEST = 'SKIP'

# Text representation of a GraphQL schema generated from OrientDB.
# This schema isn't meant to be a paragon of good schema design.
# Instead, it aims to capture as many real-world edge cases as possible,
# without requiring a massive number of types and interfaces.
SCHEMA_TEXT = '''
    schema {
      query: RootSchemaQuery
    }

    directive @filter(op_name: String!, value: [String!]!) on FIELD | INLINE_FRAGMENT

    directive @tag(tag_name: String!) on FIELD

    directive @output(out_name: String!) on FIELD

    directive @output_source on FIELD

    directive @optional on FIELD

    directive @recurse(depth: Int!) on FIELD

    directive @fold on FIELD

    type Animal implements Entity, UniquelyIdentifiable {
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

    type BirthEvent implements Entity, UniquelyIdentifiable {
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

    scalar Date

    scalar DateTime

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

    type Event implements Entity, UniquelyIdentifiable {
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

    type FeedingEvent implements Entity, UniquelyIdentifiable {
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

    type Food implements Entity, UniquelyIdentifiable {
      _x_count: Int
      alias: [String]
      description: String
      in_Entity_Related: [Entity]
      in_Species_Eats: [Species]
      name: String
      out_Entity_Related: [Entity]
      uuid: ID
    }

    type FoodOrSpecies implements Entity, UniquelyIdentifiable {
      _x_count: Int
      alias: [String]
      description: String
      in_Entity_Related: [Entity]
      in_Species_Eats: [Species]
      name: String
      out_Entity_Related: [Entity]
      uuid: ID
    }

    type Location implements Entity, UniquelyIdentifiable {
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
      Animal: Animal
      BirthEvent: BirthEvent
      Entity: Entity
      Event: Event
      FeedingEvent: FeedingEvent
      Food: Food
      FoodOrSpecies: FoodOrSpecies
      Location: Location
      Species: Species
      UniquelyIdentifiable: UniquelyIdentifiable
    }

    type Species implements Entity, UniquelyIdentifiable {
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
'''


def transform(emitted_output):
    """Transform emitted_output into a unique representation, regardless of lines / indentation."""
    return WHITESPACE_PATTERN.sub(u'', emitted_output)


def _get_mismatch_message(expected_blocks, received_blocks):
    """Create a well-formated error message indicating that two lists of blocks are mismatched."""
    pretty_expected = pformat(expected_blocks)
    pretty_received = pformat(received_blocks)
    return u'{}\n\n!=\n\n{}'.format(pretty_expected, pretty_received)


def compare_ir_blocks(test_case, expected_blocks, received_blocks):
    """Compare the expected and received IR blocks."""
    mismatch_message = _get_mismatch_message(expected_blocks, received_blocks)

    if len(expected_blocks) != len(received_blocks):
        test_case.fail(u'Not the same number of blocks:\n\n'
                       u'{}'.format(mismatch_message))

    for i in six.moves.xrange(len(expected_blocks)):
        expected = expected_blocks[i]
        received = received_blocks[i]
        test_case.assertEqual(expected, received,
                              msg=u'Blocks at position {} were different: {} vs {}\n\n'
                                  u'{}'.format(i, expected, received, mismatch_message))


def compare_graphql(test_case, expected, received):
    """Compare the expected and received GraphQL code, ignoring whitespace."""
    msg = '\n{}\n\n!=\n\n{}'.format(
        pretty_print_graphql(expected),
        pretty_print_graphql(received))
    compare_ignoring_whitespace(test_case, expected, received, msg)


def compare_match(test_case, expected, received, parameterized=True):
    """Compare the expected and received MATCH code, ignoring whitespace."""
    msg = '\n{}\n\n!=\n\n{}'.format(
        pretty_print_match(expected, parameterized=parameterized),
        pretty_print_match(received, parameterized=parameterized))
    compare_ignoring_whitespace(test_case, expected, received, msg)


def compare_sql(test_case, expected, received):
    """Compare the expected and received SQL query, ignoring whitespace."""
    msg = '\n{}\n\n!=\n\n{}'.format(expected, received)
    compare_ignoring_whitespace(test_case, expected, received, msg)


def compare_gremlin(test_case, expected, received):
    """Compare the expected and received Gremlin code, ignoring whitespace."""
    msg = '\n{}\n\n!=\n\n{}'.format(
        pretty_print_gremlin(expected),
        pretty_print_gremlin(received))
    compare_ignoring_whitespace(test_case, expected, received, msg)


def compare_input_metadata(test_case, expected, received):
    """Compare two dicts of input metadata, using proper GraphQL type comparison operators."""
    # First, assert that the sets of keys in both dicts are equal.
    test_case.assertEqual(set(six.iterkeys(expected)), set(six.iterkeys(received)))

    # Then, compare the values for each key in both dicts.
    for key in six.iterkeys(expected):
        expected_value = expected[key]
        received_value = received[key]

        test_case.assertTrue(expected_value.is_same_type(received_value),
                             msg=u'{} != {}'.format(str(expected_value), str(received_value)))


def compare_ignoring_whitespace(test_case, expected, received, msg):
    """Compare expected and received code, ignoring whitespace, with the given failure message."""
    test_case.assertEqual(transform(expected), transform(received), msg=msg)


def get_schema():
    """Get a schema object for testing."""
    ast = parse(SCHEMA_TEXT)
    schema = build_ast_schema(ast)
    return schema


def generate_schema_graph(graph_client):
    """Generate SchemaGraph from a pyorient client"""
    schema_records = graph_client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
    schema_data = [x.oRecordData for x in schema_records]
    return SchemaGraph(schema_data)


def generate_schema(graph_client, class_to_field_type_overrides=None, hidden_classes=None):
    """Generate schema and type equivalence dict from a pyorient client"""
    schema_records = graph_client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
    schema_data = [x.oRecordData for x in schema_records]
    return get_graphql_schema_from_orientdb_schema_data(schema_data, class_to_field_type_overrides,
                                                        hidden_classes)


def construct_location_types(location_types_as_strings):
    """Convert the supplied dict into a proper location_types dict with GraphQL types as values."""
    schema = get_schema()

    return {
        location: schema.get_type(type_name)
        for location, type_name in six.iteritems(location_types_as_strings)
    }


def get_empty_test_macro_registry():
    """Return a MacroRegistry with appropriate type_equivalence_hints and subclass_set."""
    schema = get_schema()
    type_equivalence_hints = {
        schema.get_type('Event'): schema.get_type('Union__BirthEvent__Event__FeedingEvent'),
    }
    subclass_sets = compute_subclass_sets(schema, type_equivalence_hints)
    macro_registry = create_macro_registry(schema, type_equivalence_hints, subclass_sets)
    return macro_registry


def get_test_macro_registry():
    """Return a MacroRegistry object containing macros used in tests."""
    macro_registry = get_empty_test_macro_registry()
    valid_macros = [
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }''', {}),
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_GrandchildrenCalledNate") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$wanted"])
                                        @macro_edge_target {
                        uuid
                    }
                }
            }
        }''', {
            'wanted': 'Nate',
        }),
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_RichSiblings") {
                in_Animal_ParentOf {
                    net_worth @tag(tag_name: "parent_net_worth")
                    out_Animal_ParentOf @macro_edge_target {
                        net_worth @filter(op_name: ">", value: ["%parent_net_worth"])
                    }
                }
            }
        }''', {}),
        ('''{
            Location @macro_edge_definition(name: "out_Location_Orphans") {
                in_Animal_LivesIn @macro_edge_target {
                    in_Animal_ParentOf @filter(op_name: "has_edge_degree", value: ["$num_parents"])
                                       @optional {
                        uuid
                    }
                }
            }
        }''', {
            'num_parents': 0,
        }),
        ('''{
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
        }''', {}),
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_RelatedFood") {
                in_Entity_Related {
                    ... on Food @macro_edge_target {
                        uuid
                    }
                }
            }
        }''', {}),
        ('''{
            Animal @macro_edge_definition(name: "out_Animal_RelatedEntity") {
                in_Entity_Related {
                    ... on Entity @macro_edge_target {
                        uuid
                    }
                }
            }
        }''', {}),
    ]

    for graphql, args in valid_macros:
        register_macro_edge(macro_registry, graphql, args)
    return macro_registry
