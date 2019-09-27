Schema Types
============

A GraphQL schema might look like the one below. Do not be intimidated by the number of components
since we will immediately proceed to dissect the schema.

.. TODO: Use a better "documentation" schema. I used a subset of the schema that we used in tests
   because it was the one referenced by all the queries in the Directives section and I can
   easily modify the directives section so that it only includes types in this subset. However,
   it is a bit more difficult to completely change what schema we are using for documentation.
   Though this schema is less than ideal for documentation. It is too large and some of types,
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
- :code:`[Animal]` is a GraphQL list type that represents an array of :code:`Animal`
  objects.


Directives
----------

In this section we'll go over how query directives are defined. For information on the available
query directives and their semantics see :doc:`query directives <query_directives>`.

Lets look at the :code:`@output` directive:

.. code::

   directive @output(out_name: String!) on FIELD

- :code:`@output` defines the directive name.
- :code:`out_name: String!` is a GraphQL argument. The :code:`!` indicates that it must not be null.
- :code:`on FIELD` defines where the directive can be located. According to the definition, this
  directive can only be located next to fields. The compiler might have additional restrictions
  for where a query can be located. See :doc:`query directives <query_directives>` for more info.

Scalar types
------------

The compiler uses the built-in GraphQL
`scalar types <https://graphql.org/learn/schema/#scalar-types>`__ as well as three custom scalars:

- :code:`DateTime` represents timezone-aware second-accuracy timestamps.
- :code:`Date` represents day-accuracy date objects.
- :code:`Decimal` is an arbitrary-precision decimal number object useful for representing values
  that should never be rounded, such as currency amounts.

Query Operation
---------------

GraphQL allows for three types *query*, *mutation* and *subscription*. The compiler
only allows for *query* operation types as shown in the code snippet below:

.. code::

    schema {
        query: RootSchemaQuery
    }

A query may begin in any of the **root vertex types** specified by the :code:`RootSchemaQuery`
object:

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

The compiler uses GraphQL interfaces and GraphQL unions in representing the inheritance structure
of the underlying schema. You may ignore this section if are compiling to a language with no
inheritance structure, (e.g. SQL).

Interfaces
~~~~~~~~~~

GraphQL interfaces represent the abstract vertices of the underlying database.

.. code::

    interface Entity {
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
    }

Abstract inheritance is modeled through interface implementation.

.. code::

    type Food implements Entity {
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
    }

Unions and :code:`type_equivalence_hints`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GraphQL does not support a notion of concrete inheritance. In other words, GraphQL objects cannot
inherit from other objects. However, for certain query dialects, the compiler needs concrete
inheritance information to emit the right query.

To model concrete inheritance, we use GraphQL unions that encompass an object's
subclasses and a :code:`type_equivalence_hints` parameter to signify that object is equivalent to
the GraphQL union.

For example, suppose :code:`Food` and :code:`Species` are concrete types and :code:`Food` is a
superclass of :code:`Species` in an OrientDB schema. Then the GraphQL schema generation function
would generate an union class in the schema

.. code::

    union Union__Food__Species = Food | Species

and an entry in :code:`type_equivalence_hints` mapping :code:`Food` to
:code:`Union_Food_Species`.


Type coercions
~~~~~~~~~~~~~~

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
                    name @output(out_name: "food_name")
                }
            }
        }
    }

In this query, the :code:`out_Entity_Related` is of :code:`Entity` type.
However, the query only wants to return results where the related entity
is a :code:`Species`, which :code:`... on Species` ensures is the case.
