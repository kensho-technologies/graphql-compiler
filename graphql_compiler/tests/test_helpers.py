# Copyright 2017-present Kensho Technologies, LLC.
"""Common test data and helper functions."""
from collections import namedtuple
from pprint import pformat
import re

from graphql import GraphQLList, parse
from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType
from graphql.utils.build_ast_schema import build_ast_schema
import six
import sqlalchemy
from sqlalchemy.dialects import mssql, postgresql

from graphql_compiler.schema_generation.orientdb import get_graphql_schema_from_orientdb_schema_data

from ..compiler.subclass import compute_subclass_sets
from ..debugging_utils import pretty_print_gremlin, pretty_print_match
from ..macros import create_macro_registry, register_macro_edge
from ..query_formatting.graphql_formatting import pretty_print_graphql
from ..schema import CUSTOM_SCALAR_TYPES, is_vertex_field_name
from ..schema.schema_info import CommonSchemaInfo, DirectJoinDescriptor, make_sqlalchemy_schema_info
from ..schema_generation.orientdb.schema_graph_builder import get_orientdb_schema_graph
from ..schema_generation.orientdb.utils import (
    ORIENTDB_INDEX_RECORDS_QUERY, ORIENTDB_SCHEMA_RECORDS_QUERY
)
from ..schema_generation.utils import amend_custom_scalar_types


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

VALID_MACROS_TEXT = [
    ('''\
    {
        Entity @macro_edge_definition(name: "out_Entity_AlmostRelated") {
            out_Entity_Related {
                out_Entity_Related @macro_edge_target{
                    uuid
                }
            }
        }
    }
    ''', {}),
    ('''\
    {
        Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
            out_Animal_ParentOf {
                out_Animal_ParentOf @macro_edge_target {
                    uuid
                }
            }
        }
    }''', {}),
    ('''\
    {
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
    ('''\
    {
        Animal @macro_edge_definition(name: "out_Animal_RichSiblings") {
            in_Animal_ParentOf {
                net_worth @tag(tag_name: "parent_net_worth")
                out_Animal_ParentOf @macro_edge_target {
                    net_worth @filter(op_name: ">", value: ["%parent_net_worth"])
                }
            }
        }
    }''', {}),
    ('''\
    {
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
    # Testing that @optional that doesn't include @macro_edge_target is okay.
    ('''\
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
    }''', {}),
    ('''\
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
    }''', {}),
    # The same as out_AnimalRichYoungerSiblings, but with a filter after the target.
    ('''\
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
    }''', {}),
    ('''\
    {
        Animal @macro_edge_definition(name: "out_Animal_RelatedFood") {
            in_Entity_Related {
                ... on Food @macro_edge_target {
                    uuid
                }
            }
        }
    }''', {}),
    ('''\
    {
        Animal @macro_edge_definition(name: "out_Animal_RelatedEntity") {
            in_Entity_Related {
                ... on Entity @macro_edge_target {
                    uuid
                }
            }
        }
    }''', {}),
]


# A class holding all necessary backend-specific testing utilities.
BackendTester = namedtuple('BackendTester', (
    # Backend to be tested
    'backend'

    # Returns whether two emitted queries are the same, up to differences in syntax/whitespace
    'compare_queries',

    # An instance of backend.SchemaInfoClass consistend with the standard testing schema.
    'schema_info',

    # Given a SchemaInfo and a connection pool to a database, install the given schema into
    # the database, erasing content if necessary.
    'setup_schema'

    # Given a SchemaInfo, a dict representation of data fitting the schema, and a connection pool
    # to a database with the same schema, install the given data into the database, erasing any
    # existing data.
    'setup_data'
))


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


def compare_cypher(test_case, expected, received):
    """Compare the expected and received Cypher query, ignoring whitespace."""
    msg = '\n{}\n\n!=\n\n{}'.format(expected, received)
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
    amend_custom_scalar_types(schema, CUSTOM_SCALAR_TYPES)  # Mutates the schema.
    return schema


def get_type_equivalence_hints():
    """Get the default type_equivalence_hints used for testing."""
    schema = get_schema()
    return {
        schema.get_type(key): schema.get_type(value)
        for key, value in [
            ('Event', 'Union__BirthEvent__Event__FeedingEvent'),
            ('FoodOrSpecies', 'Union__Food__FoodOrSpecies__Species'),
        ]
    }


def get_common_schema_info():
    """Get the default CommonSchemaInfo used for testing."""
    return CommonSchemaInfo(get_schema(), get_type_equivalence_hints())


def _get_schema_without_list_valued_property_fields():
    """Get the default testing schema, skipping any list-valued property fields it has."""
    schema = get_schema()

    types_with_fields = (GraphQLInterfaceType, GraphQLObjectType)
    for type_name, graphql_type in six.iteritems(schema.get_type_map()):
        if isinstance(graphql_type, types_with_fields):
            if type_name != 'RootSchemaQuery' and not type_name.startswith('__'):
                fields_to_pop = []
                for field_name, field_type in six.iteritems(graphql_type.fields):
                    if not is_vertex_field_name(field_name):
                        if isinstance(field_type.type, GraphQLList):
                            fields_to_pop.append(field_name)
                for field_to_pop in fields_to_pop:
                    graphql_type.fields.pop(field_to_pop)

    return schema


def get_sqlalchemy_schema_info(dialect='mssql'):
    """Get a SQLAlchemySchemaInfo for testing."""
    # We don't support list-valued property fields in SQL for now.
    schema = _get_schema_without_list_valued_property_fields()
    type_equivalence_hints = get_type_equivalence_hints()

    # Every SQLAlchemy Table needs to be attached to a MetaData object. We don't actually use it.
    # We use a mixture of two metadata objects to make sure our implementation does not rely
    # on all the tables sharing a metadata object.
    sqlalchemy_metadata_1 = sqlalchemy.MetaData()
    sqlalchemy_metadata_2 = sqlalchemy.MetaData()

    uuid_type = sqlalchemy.String(36)

    tables = {
        'Animal': sqlalchemy.Table(
            'Animal',
            sqlalchemy_metadata_1,
            sqlalchemy.Column('birthday', sqlalchemy.DateTime, nullable=False),
            sqlalchemy.Column('color', sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column('description', sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column('parent', sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column('related_entity', sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column('name', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('net_worth', sqlalchemy.Integer, nullable=True),
            sqlalchemy.Column('fed_at', uuid_type, nullable=True),
            sqlalchemy.Column('born_at', uuid_type, nullable=True),
            sqlalchemy.Column('lives_in', uuid_type, nullable=True),
            sqlalchemy.Column('important_event', sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column('species', sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            schema=('db_1.' if dialect == 'mssql' else '') + 'schema_1'
        ),
        'BirthEvent': sqlalchemy.Table(
            'BirthEvent',
            sqlalchemy_metadata_2,
            sqlalchemy.Column('description', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            sqlalchemy.Column('name', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('event_date', sqlalchemy.DateTime, nullable=False),
            sqlalchemy.Column('related_event', uuid_type, primary_key=False),
            schema=('db_1.' if dialect == 'mssql' else '') + 'schema_1'
        ),
        'Entity': sqlalchemy.Table(
            'Entity',
            sqlalchemy_metadata_2,
            sqlalchemy.Column('description', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            sqlalchemy.Column('name', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('related_entity', uuid_type, nullable=True),
            schema=('db_1.' if dialect == 'mssql' else '') + 'schema_1'
        ),
        'Event': sqlalchemy.Table(
            'Event',
            sqlalchemy_metadata_2,
            sqlalchemy.Column('description', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            sqlalchemy.Column('name', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('event_date', sqlalchemy.DateTime, nullable=False),
            sqlalchemy.Column('related_event', uuid_type, primary_key=False),
            schema=('db_2.' if dialect == 'mssql' else '') + 'schema_1'
        ),
        'FeedingEvent': sqlalchemy.Table(
            'FeedingEvent',
            sqlalchemy_metadata_1,
            sqlalchemy.Column('description', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            sqlalchemy.Column('name', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('event_date', sqlalchemy.DateTime, nullable=False),
            sqlalchemy.Column('related_event', uuid_type, primary_key=False),
            schema=('db_2.' if dialect == 'mssql' else '') + 'schema_1'
        ),
        'Food': sqlalchemy.Table(
            'Food',
            sqlalchemy_metadata_1,
            sqlalchemy.Column('description', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            sqlalchemy.Column('name', sqlalchemy.String(40), nullable=False),
            schema=('db_2.' if dialect == 'mssql' else '') + 'schema_2'
        ),
        'FoodOrSpecies': sqlalchemy.Table(
            'FoodOrSpecies',
            sqlalchemy_metadata_1,
            sqlalchemy.Column('description', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            sqlalchemy.Column('name', sqlalchemy.String(40), nullable=False),
            schema=('db_2.' if dialect == 'mssql' else '') + 'schema_2'
        ),
        'Location': sqlalchemy.Table(
            'Location',
            sqlalchemy_metadata_1,
            sqlalchemy.Column('description', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            sqlalchemy.Column('name', sqlalchemy.String(40), nullable=False),
            schema=('db_1.' if dialect == 'mssql' else '') + 'schema_1'
        ),
        'Species': sqlalchemy.Table(
            'Species',
            sqlalchemy_metadata_2,
            sqlalchemy.Column('description', sqlalchemy.String(40), nullable=True),
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            sqlalchemy.Column('name', sqlalchemy.String(40), nullable=False),
            sqlalchemy.Column('eats', uuid_type, nullable=True),
            sqlalchemy.Column('limbs', sqlalchemy.Integer, nullable=True),
            sqlalchemy.Column('related_entity', uuid_type, nullable=True),
            schema=('db_1.' if dialect == 'mssql' else '') + 'schema_1'
        ),
        'UniquelyIdentifiable': sqlalchemy.Table(
            'UniquelyIdentifiable',
            sqlalchemy_metadata_1,
            sqlalchemy.Column('uuid', uuid_type, primary_key=True),
            schema=('db_1.' if dialect == 'mssql' else '') + 'schema_1'
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
            'name': 'Animal_ParentOf',
            'from_table': 'Animal',
            'to_table': 'Animal',
            'from_column': 'uuid',
            'to_column': 'parent',
        }, {
            'name': 'Animal_OfSpecies',
            'from_table': 'Animal',
            'to_table': 'Species',
            'from_column': 'species',
            'to_column': 'uuid',
        }, {
            'name': 'Animal_FedAt',
            'from_table': 'Animal',
            'to_table': 'FeedingEvent',
            'from_column': 'fed_at',
            'to_column': 'uuid',
        }, {
            'name': 'Animal_BornAt',
            'from_table': 'Animal',
            'to_table': 'BirthEvent',
            'from_column': 'born_at',
            'to_column': 'uuid',
        }, {
            'name': 'Animal_LivesIn',
            'from_table': 'Animal',
            'to_table': 'Location',
            'from_column': 'lives_in',
            'to_column': 'uuid',
        }, {
            'name': 'Animal_ImportantEvent',
            'from_table': 'Animal',
            'to_table': 'Union__BirthEvent__Event__FeedingEvent',
            'from_column': 'important_event',
            'to_column': 'uuid',
        }, {
            'name': 'Species_Eats',
            'from_table': 'Species',
            'to_table': 'Union__Food__FoodOrSpecies__Species',
            'from_column': 'eats',
            'to_column': 'uuid',
        }, {
            'name': 'Entity_Related',
            'from_table': 'Entity',
            'to_table': 'Entity',
            'from_column': 'related_entity',
            'to_column': 'uuid',
        }, {
            'name': 'Event_RelatedEvent',
            'from_table': 'Union__BirthEvent__Event__FeedingEvent',
            'to_table': 'Union__BirthEvent__Event__FeedingEvent',
            'from_column': 'related_event',
            'to_column': 'uuid',
        }, {
            'name': 'Entity_Alias',
            'from_table': 'Entity',
            'to_table': 'Alias',
            'from_column': 'uuid',
            'to_column': 'alias_for',
        }
    ]

    join_descriptors = {}
    for edge in edges:
        join_descriptors.setdefault(edge['from_table'], {})['out_{}'.format(edge['name'])] = (
            DirectJoinDescriptor(edge['from_column'], edge['to_column']))
        join_descriptors.setdefault(edge['to_table'], {})['in_{}'.format(edge['name'])] = (
            DirectJoinDescriptor(edge['to_column'], edge['from_column']))

    # Inherit join_descriptors from superclasses
    # TODO(bojanserafimov): Properties can be inferred too, instead of being explicitly inherited.
    for class_name, subclass_set in six.iteritems(subclasses):
        for subclass in subclass_set:
            for edge_name, join_info in six.iteritems(join_descriptors.get(class_name, {})):
                join_descriptors.setdefault(subclass, {})[edge_name] = join_info
    if dialect == 'postgresql':
        sqlalchemy_compiler_dialect = postgresql.dialect()
    elif dialect == 'mssql':
        sqlalchemy_compiler_dialect = mssql.dialect()
    else:
        raise AssertionError(u'Unrecognized dialect {}'.format(dialect))
    return make_sqlalchemy_schema_info(
        schema, type_equivalence_hints, sqlalchemy_compiler_dialect, tables, join_descriptors)


def generate_schema_graph(orientdb_client):
    """Generate SchemaGraph from a pyorient client."""
    schema_records = orientdb_client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
    schema_data = [x.oRecordData for x in schema_records]
    index_records = orientdb_client.command(ORIENTDB_INDEX_RECORDS_QUERY)
    index_query_data = [x.oRecordData for x in index_records]
    return get_orientdb_schema_graph(schema_data, index_query_data)


def generate_schema(orientdb_client, class_to_field_type_overrides=None, hidden_classes=None):
    """Generate schema and type equivalence dict from a pyorient client."""
    schema_records = orientdb_client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
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
    for graphql, args in VALID_MACROS_TEXT:
        register_macro_edge(macro_registry, graphql, args)
    return macro_registry
