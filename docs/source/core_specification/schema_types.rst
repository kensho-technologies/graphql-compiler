Schema Types
============

A GraphQL schema representing a database schema might look like the one below. Do not be intimidated
by the number of components since we will proceed to dissect the schema part by part.

.. code::

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

    scalar Date

    scalar DateTime

    scalar Decimal

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

    union Union__Food__FoodOrSpecies__Species = Food | FoodOrSpecies | Species

    interface UniquelyIdentifiable {
        _x_count: Int
        uuid: ID
    }


.. note::

    A GraphQL schema can be serialized as with the :code:`print_schema` function in the
    :code:`graphql.utils.schema_printer`


GraphQL Objects and Fields
--------------------------

The core components of a GraphQL schema are GraphQL object types.
