Schema Types
============

A GraphQL schema might look like the one below. Do not be intimidated by the number of components
since we will immediately proceed to dissect the schema.

.. TODO: Use a better "documentation" schema. I used a subset of the schema that we used in tests
   because it was the one referenced by all the queries in the Directives section and I can
   easily modify the directives section so that it only includes types in this subset. However,
   it is a bit more difficult to completely change what schema we are using for documentation.
   This schema is less than ideal for documentation though. It is too large and some of types,
   like Entity, are not intuitive.

.. code::

    schema {
        query: RootSchemaQuery
    }

    type RootSchemaQuery {
        Animal: [Animal]
        Entity: [Entity]
        Food: [Food]
        Species: [Species]
        Toy: [Toy]
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

    type Food implements Entity {
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
    }

    type Species implements Entity {
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
        name: String
        in_Animal_PlaysWith: [Animal]
    }

    interface Entity {
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
    }

    union Union__Food__Species = Food | Species


.. note::

    A GraphQL schema can be serialized with the :code:`print_schema` function from the
    :code:`graphql.utils.schema_printer` module.


Objects types and fields
------------------------

The core components of a GraphQL schema are GraphQL object types. They conceptually represent the
concrete vertex types in the underlying database. For relational databases, we think of the
tables as the concrete vertex types.

Lets go over a toy example of a GraphQL object type:

.. code::

    type Toy {
        name: String
        in_Animal_PlaysWith: [Animal]
    }

Here are some of the details:

- :code:`name` is a **property field** that represents concrete data.
- :code:`in_Animal_PlaysWith` is a **vertex field** representing an inbound edge.
- :code:`String` is a built-in GraphQL scalar type.
- :code:`[Animal]` is a GraphQL list representing a list of :code:`Animal` objects.

Directives
----------

Directives are keywords that modify query execution. The compiler includes a list of directives,
which we'll talk about more in the :doc:`query directives <query_directives>` section. For now
lets see how they are defined by looking at an example:

.. code::

   directive @output(out_name: String!) on FIELD

- :code:`@output` defines the directive name.
- :code:`out_name: String!` is a GraphQL argument. The :code:`!` indicates that it must not be null.
- :code:`on FIELD` defines where the directive can be located. According to the definition, this
  directive can only be located next to fields. The compiler might have additional restrictions
  for where a query can be located.

Scalar types
------------

The compiler uses the built-in GraphQL
`scalar types <https://graphql.org/learn/schema/#scalar-types>`__ as well as three custom scalar
types:

- :code:`DateTime` represents timezone-aware second-accuracy timestamps.
- :code:`Date` represents day-accuracy date objects.
- :code:`Decimal` is an arbitrary-precision decimal number object useful for representing values
  that should never be rounded, such as currency amounts.

Operation types
---------------

GraphQL allows for three operation types *query*, *mutation* and *subscription*. The compiler
only allows for read-only *query* operation types as shown in the code snippet below:

.. code::

    schema {
        query: RootSchemaQuery
    }

A query may begin in any of the **root vertex types** specified by the special
:code:`RootSchemaQuery` object type:

.. code::

    type RootSchemaQuery {
        Animal: [Animal]
        Entity: [Entity]
        Food: [Food]
        Species: [Species]
        Toy: [Toy]
    }

Inheritance
-----------

The compiler uses interface and union types in representing the inheritance
structure of the underlying schema. Some database backends do not support inheritance, (e.g. SQL),
so this feature is only supported for certain backends.

Interface types
~~~~~~~~~~~~~~~

Object types may declare that they *implement* an interface type, meaning that they contain all
property and vertex fields that the interface declares. In many programming languages, this
concept is called interface inheritance or abstract inheritance. The compiler uses interface
implementation in the GraphQL schema to model the abstract inheritance in the underlying database.

.. code::

   interface Entity {
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
    }

    type Food implements Entity {
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
    }

Querying an interface type without any `type coercion <#type-coercion>`__ returns all of the
the objects implemented by the interface. For instance, the following query returns the name of all
:code:`Food`, :code:`Species` and :code:`Animal` objects.

.. code::

   {
      Entity {
         name @output(out_name: "entity_name")
      }
   }


Union types and :code:`type_equivalence_hints`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GraphQL's type system does not allow object types to inherit other object types
(i.e. it has no notion of concrete inheritance). However, to model the database schema of certain
backends and to emit the right query in certain cases, the compiler needs to have a notion of the
underlying concrete inheritance.

In order to work around this limitation, the GraphQL compiler uses GraphQL union types as means of
listing the subclasses of an object with multiple implicit subclasses. It also takes in a
:code:`type_equivalence_hints` parameter to match an object type with the union
type listing its subclasses.

For example, suppose :code:`Food` and :code:`Species` are concrete types and :code:`Food` is a
superclass of :code:`Species` in an OrientDB schema. Then the GraphQL schema info generation
function would generate a union type in the schema

.. code::

    union Union__Food__Species = Food | Species

as well an entry in :code:`type_equivalence_hints` mapping :code:`Food` to
:code:`Union_Food_Species`.

.. TODO: Add a section explaining how edges to union types are generated.

To query an union type, one must always type coerce to one of the encompassed object types as
illustrated in the section below.

Type coercions
~~~~~~~~~~~~~~

.. TODO: Clarify the paragraph below. It is kind of hard to read.

Type coercions are operations than can be run against interfaces and unions to create a new scope
whose type is different than the type of the enclosing scope of the coercion. Type coercions are
represented with GraphQL inline fragments.

Example Use
^^^^^^^^^^^

.. code::

    {
        Species {
            name @output(out_name: "species_name")
            out_Species_Eats {
                ... on Food {
                    name @output(out_name: "food_name")
                }
            }
        }
    }

Here, the :code:`out_Species_Eats` vertex field is of the
:code:`Union__Food__FoodOrSpecies__Species` union type. To proceed with the
query, the user must choose which of the types in the
:code:`Union__Food__FoodOrSpecies__Species` union to use. In this example,
:code:`... on Food` indicates that the :code:`Food` type was chosen, and any
vertices at that scope that are not of type :code:`Food` are filtered out
and discarded.

.. code::

    {
        Species {
            name @output(out_name: "species_name")
            out_Entity_Related {
                ... on Species {
                    name @output(out_name: "entity_name")
                }
            }
        }
    }

In this query, the :code:`out_Entity_Related` is of :code:`Entity` type.
However, the query only wants to return results where the related entity
is a :code:`Species`, which :code:`... on Species` ensures is the case.
