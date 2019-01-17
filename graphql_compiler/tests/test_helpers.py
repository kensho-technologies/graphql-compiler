# Copyright 2017-present Kensho Technologies, LLC.
"""Common test data and helper functions."""
from pprint import pformat
import re

from graphql import parse
from graphql.utils.build_ast_schema import build_ast_schema
import six
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, create_engine

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
            out_Animal_FriendsWith: [Animal]
            in_Animal_FriendsWith: [Animal]
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

            # out_SpeciesEatenBy is the same as in_Species_Eats
            # allowing backends to test equivalent edges
            in_Species_Eats: [Species]
            out_Species_EatenBy: [Species]

            in_Animal_Eats: [Animal]
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
            in_Animal_Eats: [Animal]
            in_Entity_Related: [Entity]
            out_Entity_Related: [Entity]
            out_Food_OfCuisine: [Cuisine]
        }

        type Cuisine implements Entity {
            name: String
            description: String
            alias: [String]
            uuid: ID
            in_Entity_Related: [Entity]
            out_Entity_Related: [Entity]
            in_Food_OfCuisine: [Food]
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
            out_Event_RelatedEvent: [EventOrBirthEvent]
            in_Event_RelatedEvent: [EventOrBirthEvent]
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
            out_Event_RelatedEvent: [EventOrBirthEvent]
            in_Event_RelatedEvent: [EventOrBirthEvent]
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


def create_sqlite_db():
    engine = create_engine('sqlite:///:memory:')
    metadata = MetaData()

    animal_table = Table(
        'animal',
        metadata,
        Column('animal_id', Integer, primary_key=True),
        Column('name', String(10), nullable=False),
        Column('alias', String(50), nullable=False),
        Column('parentof_id', Integer, ForeignKey("animal.animal_id"), nullable=True),
    )

    animal_rows = [
        (1, 'Big Bear', 'The second biggest bear.', 3),
        (2, 'Little Bear', 'The smallest bear', None),
        (3, 'Medium Bear', 'The midsize bear.', 2),
        (4, 'Biggest Bear', 'The biggest bear.', 1),
    ]

    animal_to_friend_table = Table(
        'animal_friendswith',
        metadata,
        Column('animal_friendswith_id', Integer, primary_key=True),
        Column('animal_id', Integer, ForeignKey("animal.animal_id")),
        Column('friendswith_id', Integer, ForeignKey("animal.animal_id")),
    )

    animal_to_friend_rows = [
        # little bear is friends with big bear
        (16, 2, 1),
        # little bear is best friends with biggest bear
        (17, 2, 4),
        # biggest bear is friends with medium bear (cycle)
        (18, 4, 3),
        # medium bear is best friends with himself (cycle)
        (19, 3, 3),
        # medium bear is friends with biggest bear
        (21, 3, 4),
    ]

    animal_important_event_event_table = Table(
        'animal_importantevent_event',
        metadata,
        Column('animal_importantevent_event_id', Integer, primary_key=True),
        Column('animal_id', Integer, ForeignKey("animal.animal_id")),
        Column('importantevent_id', Integer, ForeignKey("event.event_id")),
    )

    animal_important_event_event_rows = [
        # big bear gets fed a lot
        (12, 1, 9),
        (13, 1, 10),
        (14, 1, 11),
        # medium bear was only fed in the morning
        (15, 3, 9),
    ]

    location_table = Table(
        'location',
        metadata,
        Column('location_id', Integer, primary_key=True),
        Column('livesin_id', Integer, ForeignKey("animal.animal_id")),
        Column('name', String(10))
    )

    location_rows = [
        (4, 1, 'Wisconsin'),
        (5, 2, 'Florida'),
        (6, 3, 'Florida'),
        (7, 3, 'Miami'),
        (8, 3, 'Miami Beach'),
    ]

    event_table = Table(
        'event',
        metadata,
        Column('event_id', Integer, primary_key=True),
        Column('name', String(10)),
    )

    event_rows = [
        (9, 'Morning Feed Event'),
        (10, 'Afternoon Feed Event'),
        (11, 'Night Feed Event'),
    ]

    species_table = Table(
        'species',
        metadata,
        Column('species_id', Integer, primary_key=True),
        Column('name', String(10)),
        Column('eats_id', Integer, ForeignKey('species.species_id'), nullable=True),
        Column('eatenby_id', Integer, ForeignKey('species.species_id'), nullable=True),
    )

    species_rows = [
        (24, 'Bear', 22, None),
        (22, 'Rabbit', None, 24)
    ]

    animal_to_species_table = Table(
        'animal_ofspecies',
        metadata,
        Column('animal_ofspecies_id', Integer, primary_key=True),
        Column('animal_id', Integer, ForeignKey("animal.animal_id")),
        Column('ofspecies_id', Integer, ForeignKey("animal.animal_id")),
    )

    animal_to_species = [
        (25, 1, 24),
        (27, 3, 24),
        (28, 4, 24),
    ]

    metadata.create_all(engine)

    tables_values = [
        (animal_table, animal_rows),
        (location_table, location_rows),
        (species_table, species_rows),
        (animal_to_species_table, animal_to_species),
        (animal_to_friend_table, animal_to_friend_rows),
        (event_table, event_rows),
        (animal_important_event_event_table, animal_important_event_event_rows),
    ]

    for table, vals in tables_values:
        for val in vals:
            engine.execute(table.insert(val))
    return engine, metadata


def create_misconfigured_sqlite_db():
    engine = create_engine('sqlite:///:memory:')
    metadata = MetaData()

    Table(
        'animal',
        metadata,
        Column('animal_id', Integer, primary_key=True),
        Column('name', String(10), nullable=False),
        Column('alias', String(50), nullable=False),
        Column('parentof_id', Integer, ForeignKey("animal.animal_id"), nullable=True),
    )

    Table(
        'animal_friendswith',
        metadata,
        Column('animal_friendswith_id', Integer, primary_key=True),
        Column('animal_id', Integer, ForeignKey("animal.animal_id")),
        # the column below, following convention, should be friendswith_id (no initial underscore)
        Column('friends_with_id', Integer, ForeignKey("animal.animal_id")),
    )

    Table(
        'animal_importantevent_event',
        metadata,
        Column('animal_importantevent_event_id', Integer, primary_key=True),
        Column('animal_id', Integer, ForeignKey("animal.animal_id")),
        Column('importantevent_id', Integer, ForeignKey("event.event_id")),
    )

    Table(
        'animal_importantevent',
        metadata,
        Column('animal_importantevent_event_id', Integer, primary_key=True),
        Column('animal_id', Integer, ForeignKey("animal.animal_id")),
        Column('importantevent_id', Integer, ForeignKey("event.event_id")),
    )

    Table(
        'location',
        metadata,
        Column('location_id', Integer, primary_key=True),
        Column('livesin_id', Integer, ForeignKey("animal.animal_id")),
        Column('name', String(10))
    )

    Table(
        'event',
        metadata,
        Column('event_id', Integer, primary_key=True),
        # per the schema, this should be column "name"
        Column('names', String(10)),
    )

    Table(
        'species',
        metadata,
        Column('species_id', Integer, primary_key=True),
        Column('name', String(10), primary_key=True),
        Column('eats_id', Integer, ForeignKey('species.species_id'), nullable=True),
        Column('eatenby_id', Integer, ForeignKey('species.species_id'), nullable=True),
    )

    Table(
        'animal_ofspecies',
        metadata,
        Column('animal_ofspecies_id', Integer, primary_key=True),
        Column('animal_id', Integer, ForeignKey("animal.animal_id")),
        Column('ofspecies_id', Integer, ForeignKey("animal.animal_id")),
    )

    metadata.create_all(engine)
    return engine, metadata
