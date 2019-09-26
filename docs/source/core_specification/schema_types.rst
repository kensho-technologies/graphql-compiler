Schema Types
============

A GraphQL schema might look like the one below. Do not be intimidated by the number of components
since we will immediately proceed to dissect the schema.

.. TODO: Use a better "documentation" schema. I used a subset of the schema that we used in tests
   because it was the one referenced by all the queries in the Directives section and I can
   easily modify  the directives section so that it only includes types in this subset. However,
   it is  a bit more difficult to completely change what schema we are using for documentation.
   Though this schema is less than ideal for documentation. It is to large and some of types,
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

    type Food implements Entity {
        _x_count: Int
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
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
        name: String
        in_Animal_PlaysWith: [Animal]
    }

    interface Entity {
        _x_count: Int
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
    }

    union Union__Food__Species = Food | Species


.. note::

    A GraphQL schema can be serialized with the :code:`print_schema` function from the
    :code:`graphql.utils.schema_printer` module.


GraphQL Objects and Fields
--------------------------

The core components of a GraphQL schema are *GraphQL Object Types*. They conceptually represent the
concrete vertices in the underlying database. For relational databases, we think of the tables as
the concrete vertices.

Lets go over a toy example of a GraphQL object type:

.. code::

    type Toy {
        name: String
        in_Animal_PlaysWith: [Animal]
    }

Here are some of the details:

- :code:`name` is a **property field** representing a property of a vertex. Property fields
  are the leaf fields that represent concrete data.
- :code:`in_Animal_PlaysWith` is a **vertex field** representing an outbound edge to other
  vertices in the graph. All vertex fields begin with an :code:`in_` or :code:`out_` prefix.
- :code:`String` is a built-in *GraphQL Scalar Type*. The compiler uses the built-in GraphQL
  scalar types and a couple of custom scalar types. We will talk more about these in the
  `scalar types <#scalar-types>`__ section.
- :code:`[Animal]` is a *GraphQL List Type* that represents an array of :code:`Animal`
   objects. All vertex fields have a GraphQL list type.

Now that we have an idea of a rough idea of how GraphQL objects works, lets go over some of the
other components.

GraphQL Directives
------------------

In this section we'll go over how query directives are defined. For information on the available
query directives and their semantics see :doc:`query directives <query_directives>`.

Let's look at the :code:`@output` directive:

.. code::

   directive @output(out_name: String!) on FIELD

- :code:`@output` defines the directive name.
- :code:`out_name: String!` is a *GraphQL Argument*. The :code:`!` indicates that the string
  :code:`out_name` argument must not be null.
- :code:`on FIELD` defines where the directive can be located. According to the definition, this
  directive can only be located next to fields. The compiler might have additional restrictions
  for where a query can be located. See :doc:`query directives <query_directives>` for more info.

Query Operation
---------------

GraphQL allows for three operation types *query*, *mutation* and *subscription*. The compiler
only allows *query* operation types as shown in the code snippet below:

.. code::

    schema {
        query: RootSchemaQuery
    }

The special :code:`RootSchemaQuery` GraphQL object defines all the "entry points" of the query:

.. code::

    type RootSchemaQuery {
        Animal: [Animal]
        Entity: [Entity]
        Food: [Food]
        Species: [Species]
        Toy: [Toy]
    }



Scalar Types
------------

The compiler uses the built-in GraphQL
`scalar types <https://graphql.org/learn/schema/#scalar-types>`__ as well as three custom scalars:

- :code:`DateTime` represents timezone-aware second-accuracy timestamps.
- :code:`Date` represents day-accuracy date objects.
- :code:`Decimal` is an arbitrary-precision decimal number object useful for representing values
  that should never be rounded, such as currency amounts.

GraphQL Inheritance
-------------------

If compiling to a database without any inheritance, (e.g. all SQL databases), feel free to
ignore this section.

We use two types to model type inheritance in GraphQL: *GraphQL Interface Types* and *GraphQL
Union Types*. We will first explain how to query them and then proceed to explain how are they
structured and what they conceptually represent.

GraphQL interfaces can be queried in the same way that GraphQL objects are queried. They can also
be *type coerced*. GraphQL unions may only be used in a query when type coerced.

Type coercions
~~~~~~~~~~~~~~

Type coercions are operations that create a new scope whose type is
different than the type of the enclosing scope of the coercion -- they
coerce the enclosing scope into a different type. Type coercions are
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

GraphQL Interface Types
~~~~~~~~~~~~~~~~~~~~~~~

GraphQL interfaces represent the abstract vertices of the underlying database.

.. code::

    interface Entity {
        _x_count: Int
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
    }

GraphQL objects can *implement* interfaces, (as in the example below). If an object
implements an interface, then it means that the interface is a superclass of said object.

.. code::

    type Food implements Entity {
        _x_count: Int
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
    }

GraphQL Union Types and :code:`type_equivalence_hints`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GraphQL does not support a notion of concrete inheritance, (GraphQL objects cannot inherit from
other GraphQL objects), which we need to be able to represent the schemas of certain databases
and emit the correct queries during compilation.

We use GraphQL unions along with the :code:`type_equivalence_hints` parameter, (which
signals an equivalence between a GraphQL union and a GraphQL object), to model concrete type
inheritance. Let's look at an example:

Suppose :code:`Food` and :code:`Species` are concrete types and :code:`Food` is a superclass of
:code:`Species`. Then during the schema info generation, the compiler would generate a type
representing the union of food or species:

.. code::

    union Union__Food__Species = Food | Species

The schema info generation function would also generate a entry in :code:`type_equivalence_hints`
mapping the :code:`Food` :code:`GraphQLObjectType` to the :code:`Union__Food__Species` the
:code:`GraphQLUnionType` to signify their equivalence.

.. note::

   :code:`GraphQLObjectType` and :code:`GraphQLObjectType` are python representations GraphQL
   types. All GraphQL types have an equivalent python representation.

Meta fields
-----------

\_\_typename
~~~~~~~~~~~~

The compiler supports the standard GraphQL meta field :code:`__typename`,
which returns the runtime type of the scope where the field is found.
Assuming the GraphQL schema matches the database's schema, the runtime
type will always be a subtype of (or exactly equal to) the static type
of the scope determined by the GraphQL type system. Below, we provide an
example query in which the runtime type is a subtype of the static type,
but is not equal to it.

The :code:`__typename` field is treated as a property field of type
:code:`String`, and supports all directives that can be applied to any other
property field.

Example Use
^^^^^^^^^^^

.. code::

    {
        Entity {
            __typename @output(out_name: "entity_type")
            name @output(out_name: "entity_name")
        }
    }

This query returns one row for each :code:`Entity` vertex. The scope in
which :code:`__typename` appears is of static type :code:`Entity`. However,
:code:`Animal` is a type of :code:`Entity`, as are :code:`Species`, :code:`Food`, and
others. Vertices of all subtypes of :code:`Entity` will therefore be
returned, and the :code:`entity_type` column that outputs the :code:`__typename`
field will show their runtime type: :code:`Animal`, :code:`Species`, :code:`Food`,
etc.

\_x\_count
~~~~~~~~~~

The :code:`_x_count` meta field is a non-standard meta field defined by the
GraphQL compiler that makes it possible to interact with the *number* of
elements in a scope marked :code:`@fold`. By applying directives like
:code:`@output` and :code:`@filter` to this meta field, queries can output the
number of elements captured in the :code:`@fold` and filter down results to
select only those with the desired fold sizes.

We use the :code:`_x_` prefix to signify that this is an extension meta
field introduced by the compiler, and not part of the canonical set of
GraphQL meta fields defined by the GraphQL specification. We do not use
the GraphQL standard double-underscore (:code:`__`) prefix for meta fields,
since all names with that prefix are `explicitly reserved and prohibited
from being
used <https://facebook.github.io/graphql/draft/#sec-Reserved-Names>`__
in directives, fields, or any other artifacts.

.. TODO: Add a more specific link below to point to the fold directives.

Example Use
^^^^^^^^^^^

Since the :code:`_x_count` field can only be used with the :code:`@fold` please see :doc:`@fold
<query_directives>` for an example use.
