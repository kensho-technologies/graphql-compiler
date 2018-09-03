# Copyright 2017-present Kensho Technologies, LLC.
"""Common test data and helper functions."""
from pprint import pformat
import re

from graphql import parse
from graphql.utils.build_ast_schema import build_ast_schema
import six

from ..debugging_utils import pretty_print_gremlin, pretty_print_match


# The strings which we will be comparing have newlines and spaces we'd like to get rid of,
# so we can compare expected and produced emitted code irrespective of whitespace.
WHITESPACE_PATTERN = re.compile(u'[\t\n ]*', flags=re.UNICODE)


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


def compare_match(test_case, expected, received, parameterized=True):
    """Compare the expected and received MATCH code, ignoring whitespace."""
    msg = '\n{}\n\n!=\n\n{}'.format(
        pretty_print_match(expected, parameterized=parameterized),
        pretty_print_match(received, parameterized=parameterized))
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
    # This schema isn't meant to be a paragon of good schema design.
    # Instead, it aims to capture as many real-world edge cases as possible,
    # without requiring a massive number of types and interfaces.
    schema_text = '''
        schema {
            query: RootSchemaQuery
        }

        directive @recurse(depth: Int!) on FIELD

        directive @filter(op_name: String!, value: [String!]!) on FIELD | INLINE_FRAGMENT

        directive @tag(tag_name: String!) on FIELD

        directive @output(out_name: String!) on FIELD

        directive @output_source on FIELD

        directive @optional on FIELD

        directive @fold on FIELD

        scalar Decimal

        scalar DateTime

        scalar Date

        interface Entity {
            name: String
            alias: [String]
            description: String
            uuid: ID
            in_Entity_Related: [Entity]
            out_Entity_Related: [Entity]
        }

        type Animal implements Entity {
            name: String
            color: String
            description: String
            alias: [String]
            birthday: Date
            net_worth: Decimal
            uuid: ID
            out_Animal_ParentOf: [Animal]
            in_Animal_ParentOf: [Animal]
            out_Animal_OfSpecies: [Species]
            out_Animal_FedAt: [Event]
            out_Animal_BornAt: [BirthEvent]
            out_Animal_ImportantEvent: [EventOrBirthEvent]
            in_Entity_Related: [Entity]
            out_Entity_Related: [Entity]
            out_Animal_LivesIn: [Location]
        }

        type Location {
            name: String
            uuid: ID
            in_Animal_LivesIn: [Animal]
        }

        type Species implements Entity {
            name: String
            description: String
            alias: [String]
            limbs: Int
            uuid: ID
            out_Species_Eats: [FoodOrSpecies]
            in_Species_Eats: [Species]
            in_Animal_OfSpecies: [Animal]
            in_Entity_Related: [Entity]
            out_Entity_Related: [Entity]
        }

        type Food implements Entity {
            name: String
            origin: String
            description: String
            alias: [String]
            uuid: ID
            in_Species_Eats: [Species]
            in_Entity_Related: [Entity]
            out_Entity_Related: [Entity]
        }

        union FoodOrSpecies = Food | Species

        type Event implements Entity {
            name: String
            alias: [String]
            description: String
            uuid: ID
            event_date: DateTime
            in_Animal_FedAt: [Animal]
            in_Animal_ImportantEvent: [Animal]
            in_Entity_Related: [Entity]
            out_Entity_Related: [Entity]
        }

        # Assume that in the database, the below type is actually a subclass of Event.
        type BirthEvent implements Entity {
            name: String
            alias: [String]
            description: String
            uuid: ID
            event_date: DateTime
            in_Animal_FedAt: [Animal]
            in_Animal_BornAt: [Animal]
            in_Animal_ImportantEvent: [Animal]
            in_Entity_Related: [Entity]
            out_Entity_Related: [Entity]
        }

        # Because of the above, the base type for this union is Event.
        union EventOrBirthEvent = Event | BirthEvent

        type RootSchemaQuery {
            Animal: Animal
            BirthEvent: BirthEvent
            Entity: Entity
            Event: Event
            Food: Food
            Species: Species
            Location: Location
        }
    '''

    ast = parse(schema_text)
    return build_ast_schema(ast)


def construct_location_types(location_types_as_strings):
    """Convert the supplied dict into a proper location_types dict with GraphQL types as values."""
    schema = get_schema()

    return {
        location: schema.get_type(type_name)
        for location, type_name in six.iteritems(location_types_as_strings)
    }
