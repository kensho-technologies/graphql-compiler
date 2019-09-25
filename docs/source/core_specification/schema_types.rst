Schema Types
============

A GraphQL schema representing a database schema might look like the one below.

Do not be intimidated by the number of components since we will proceed to dissect the schema
part by part.

.. code::

    schema {
        query: RootSchemaQuery
    }

    directive @filter(op_name: String!, value: [String!]) on FIELD | INLINE_FRAGMENT

    directive @tag(tag_name: String!) on FIELD

    directive @output(out_name: String!) on FIELD

    directive @output_source on FIELD

    directive @optional on FIELD

    directive @recurse(depth: Int!) on FIELD

    directive @fold on FIELD

    scalar Date

    scalar DateTime

    scalar Decimal

    type Animal implements Entity {
        _x_count: Int
        name: String
        alias: [String]
        birthday: Date
        net_worth: Decimal
        in_Animal_ParentOf: [Animal]
        out_Animal_ParentOf: [Animal]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        out_Animal_OfSpecies: [Species]
        out_Animal_PlaysWith: [Toy]
    }

    interface Entity {
        _x_count: Int
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
    }

    type Food implements Entity {
        _x_count: Int
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
    }

    type RootSchemaQuery {
        Animal: [Animal]
        Entity: [Entity]
        Food: [Food]
        Species: [Species]
    }

    type Species implements Entity {
        _x_count: Int
        name: String
        alias: [String]
        description: String
        in_Animal_OfSpecies: [Animal]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
        out_Species_Eats: [Union__Food__Species]
    }

    type Toy {
        _x_count: Int
        name: String
        in_Animal_PlaysWith: [Animal]
    }

    union Union__Food__Species = Food | Species


.. note::

    A GraphQL schema can be serialized as with the :code:`print_schema` function in the
    :code:`graphql.utils.schema_printer` module.


GraphQL Objects and Fields
--------------------------

The core components of a GraphQL schema are *GraphQL Object Types*.

They conceptually represent the concrete, (non-abstract), vertices in the underlying database. For
relational databases, we think of the tables as the concrete vertices. Lets go over a toy example
of a GraphQL object type:

.. code::

    type Toy {
        _x_count: Int
        name: String
        in_Animal_PlaysWith: [Animal]
    }

Here are some of the details:

    - :code:`name` is a **property field** representing a property of a vertex, (think of table
      columns for relational databases).
    - :code:`String` is a built-in scalar type. The compiler uses the built-in GraphQL scalar types
      and a couple of custom scalar types. We will talk more about these in a later section.
    - :code:`in_Animal_PlaysWith` is a **vertex field** representing an outbound edge to other
      vertices in the graph. All **vertex fields** begin with an :code:`in_` or :code:`out_`
      prefix.
    - :code:`[Species]` is a *GraphQL List Type* that represents an array of :code:`Animal`
      objects. All **vertex fields** have a *GraphQL List Type*.

Now that we have an idea of a rough idea of how GraphQL objects works, lets go over some of the
other components.

GraphQL Directives
------------------

We define a series of directives that define query semantics. Let's look at the core compiler
directive:

.. code::

    directive @output(out_name: String!) on FIELD

-   :code:`@output` defines the directive name.
-   :code:`out_name: String!` is a *GraphQL Argument*. The :code:`!` indicates that the string
    :code:`out_name` argument must not be null.
-   :code:`on FIELD` defines where the locations where the query can be included. This query can
    included near all argument fields.

In this section, we've gone over how we specify directives. For information on query semantics see
:doc:`Query Directives <query_directives>`


Roo
---------
