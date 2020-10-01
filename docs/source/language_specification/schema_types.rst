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
        _x_count: Int
        uuid: ID
        name: String
        alias: [String]
        color: String
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
        uuid: ID
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
    }

    type Species implements Entity {
        _x_count: Int
        uuid: ID
        name: String
        alias: [String]
        in_Animal_OfSpecies: [Animal]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
        out_Species_Eats: [Union__Food__Species]
    }

    type Toy {
        _x_count: Int
        uuid: ID
        name: String
        in_Animal_PlaysWith: [Animal]
    }

    interface Entity {
        _x_count: Int
        uuid: ID
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
        _x_count: Int
        name: String
        in_Animal_PlaysWith: [Animal]
    }

Here are some of the details:

- :code:`_x_count`: is a :ref:`meta field <meta_fields>`. Meta fields are an advanced compiler
  feature.
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

- :code:`DateTime` represents timezone-naive second-accuracy timestamps.
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

Querying an interface type without any `type coercion <type_coercion>`__ returns all of the
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

.. _type_coercion:

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

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be the only selection in scope. No field may exist in the same
   scope as a type coercion. No scope may contain more than one type
   coercion.

.. _meta_fields:

Meta fields
-----------

Meta fields are fields that do not represent a property/column in the underlying vertex type.
They are also an advanced compiler feature. Before continuing, readers should familiarize
themselves with the various :doc:`query directives <query_directives>` supported by the compiler.

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

.. _x_count:

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

Adding the :code:`_x_count` meta field to your schema
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Since the :code:`_x_count` meta field is not currently part of the GraphQL
standard, it has to be explicitly added to all interfaces and types in
your schema. There are two ways to do this.

The preferred way to do this is to use the
:code:`EXTENDED_META_FIELD_DEFINITIONS` constant as a starting point for
building your interfaces' and types' field descriptions:

.. code:: python

    from graphql import GraphQLInt, GraphQLField, GraphQLObjectType, GraphQLString
    from graphql_compiler import EXTENDED_META_FIELD_DEFINITIONS
    fields = EXTENDED_META_FIELD_DEFINITIONS.copy()
    fields.update({
        'foo': GraphQLField(GraphQLString),
        'bar': GraphQLField(GraphQLInt),
        # etc.
    })
    graphql_type = GraphQLObjectType('MyType', fields)
    # etc.

If you are not able to programmatically define the schema, and instead
simply have a pre-made GraphQL schema object that you are able to
mutate, the alternative approach is via the
:code:`insert_meta_fields_into_existing_schema()` helper function defined by
the compiler:

.. code:: python

    # assuming that existing_schema is your GraphQL schema object
    insert_meta_fields_into_existing_schema(existing_schema)
    # existing_schema was mutated in-place and all custom meta-fields were added

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @fold {
                _x_count @output(out_name: "number_of_children")
                name @output(out_name: "child_names")
            }
        }
    }

This query returns one row for each :code:`Animal` vertex. Each row contains
its name, and the number and names of its children. While the output
type of the :code:`child_names` selection is a list of strings, the output
type of the :code:`number_of_children` selection is an integer.

.. code::

    {
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @fold {
                _x_count @filter(op_name: ">=", value: ["$min_children"])
                        @output(out_name: "number_of_children")
                name @filter(op_name: "has_substring", value: ["$substr"])
                     @output(out_name: "child_names")
            }
        }
    }

Here, we've modified the above query to add two more filtering
constraints to the returned rows:

- child :code:`Animal` vertices must contain the value of :code:`$substr` as a substring in their
  name, and
- :code:`Animal` vertices must have at least :code:`$min_children` children that
  satisfy the above filter.

Importantly, any filtering on :code:`_x_count` is applied *after* any other
filters and type coercions that are present in the :code:`@fold` in
question. This order of operations matters a lot: selecting :code:`Animal`
vertices with 3+ children, then filtering the children based on their
names is not the same as filtering the children first, and then
selecting :code:`Animal` vertices that have 3+ children that matched the
earlier filter.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  The :code:`_x_count` field is only allowed to appear within a vertex
   field marked :code:`@fold`.
-  Filtering on :code:`_x_count` is always applied *after* any other filters
   and type coercions present in that :code:`@fold`.
-  Filtering or outputting the value of the :code:`_x_count` field must
   always be done at the innermost scope of the :code:`@fold`. It is invalid
   to expand vertex fields within a :code:`@fold` after filtering or
   outputting the value of the :code:`_x_count` meta field.

How is filtering on :code:`_x_count` different from :code:`@filter` with :code:`has_edge_degree`?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :code:`has_edge_degree` filter allows filtering based on the number of
edges of a particular type. There are situations in which filtering with
:code:`has_edge_degree` and filtering using :code:`=` on :code:`_x_count` produce
equivalent queries. Here is one such pair of queries:

.. code::

    {
        Species {
            name @output(out_name: "name")
            in_Animal_OfSpecies @filter(op_name: "has_edge_degree", value: ["$num_animals"]) {
                uuid
            }
        }
    }

and

.. code::

    {
        Species {
            name @output(out_name: "name")
            in_Animal_OfSpecies @fold {
                _x_count @filter(op_name: "=", value: ["$num_animals"])
            }
        }
    }

In both of these queries, we ask for the names of the :code:`Species`
vertices that have precisely :code:`$num_animals` members. However, we have
expressed this question in two different ways: once as a property of the
:code:`Species` vertex ("the degree of the :code:`in_Animal_OfSpecies` is
:code:`$num_animals`"), and once as a property of the list of :code:`Animal`
vertices produced by the :code:`@fold` ("the number of elements in the
:code:`@fold` is :code:`$num_animals`").

When we add additional filtering within the :code:`Animal` vertices of the
:code:`in_Animal_OfSpecies` vertex field, this distinction becomes very
important. Compare the following two queries:

.. code::

    {
        Species {
            name @output(out_name: "name")
            in_Animal_OfSpecies @filter(op_name: "has_edge_degree", value: ["$num_animals"]) {
                out_Animal_LivesIn {
                    name @filter(op_name: "=", value: ["$location"])
                }
            }
        }
    }

versus

.. code::

    {
        Species {
            name @output(out_name: "name")
            in_Animal_OfSpecies @fold {
                out_Animal_LivesIn {
                    _x_count @filter(op_name: "=", value: ["$num_animals"])
                    name @filter(op_name: "=", value: ["$location"])
                }
            }
        }
    }

In the first, for the purposes of the :code:`has_edge_degree` filtering, the
location where the animals live is irrelevant: the :code:`has_edge_degree`
only makes sure that the :code:`Species` vertex has the correct number of
edges of type :code:`in_Animal_OfSpecies`, and that's it. In contrast, the
second query ensures that only :code:`Species` vertices that have
:code:`$num_animals` animals that live in the selected location are returned
-- the location matters since the :code:`@filter` on the :code:`_x_count` field
applies to the number of elements in the :code:`@fold` scope.
