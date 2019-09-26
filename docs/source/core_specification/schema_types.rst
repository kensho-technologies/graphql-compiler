Schema Types
============

A GraphQL schema representing a database schema might look like the one below.

Do not be intimidated by the number of components since we will proceed to dissect the schema
part by part.

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
        _x_count: Int
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

    A GraphQL schema can be serialized as with the :code:`print_schema` function from the
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

.. TODO: Add a better hyperlink below for metafields.

Here are some of the details:

    - :code:`_x_count` is a **meta field**. It is used in conjunction with the :code:`@fold`
      directive and it is explained in the :doc:`Query Directives <query_directives>` section.
    - :code:`name` is a **property field** representing a property of a vertex, (think of table
      columns for relational databases).
    - :code:`String` is a built-in scalar type. The compiler uses the built-in GraphQL scalar types
      and a couple of custom scalar types. We will talk more about these in a later section.
    - :code:`in_Animal_PlaysWith` is a **vertex field** representing an outbound edge to other
      vertices in the graph. All vertex fields begin with an :code:`in_` or :code:`out_`
      prefix.
    - :code:`[Animal]` is a *GraphQL List Type* that represents an array of :code:`Animal`
      objects. All vertex fields have a GraphQL list type.

Now that we have an idea of a rough idea of how GraphQL objects works, lets go over some of the
other components.

GraphQL Directives
------------------

In this section we'll go over how query directives are defined. For information on the available
query directives and their semantics see :doc:`Query Directives <query_directives`.

Let's look at how the :code:`@output` directive is defined:

.. code::

    directive @output(out_name: String!) on FIELD

-   :code:`@output` defines the directive name.
-   :code:`out_name: String!` is a *GraphQL Argument*. The :code:`!` indicates that the string
    :code:`out_name` argument must not be null.
-   :code:`on FIELD` defines where the locations where the query can be included. This query can
    included near all argument fields.

Query Operation
---------------

GraphQL allows for three operation types *query*, *mutation* and *subscription*. The compiler
only allows *query* operation types as shown in the code snippet below:

.. code::

    schema {
        query: RootSchemaQuery
    }

The :code:`RootSchemaQuery` defines all the "entry points" of the query:

.. code::

    type RootSchemaQuery {
        Animal: [Animal]
        Entity: [Entity]
        Food: [Food]
        Species: [Species]
        Toy: [Toy]
    }

For the GraphQL compiler, all vertices are valid entry points.


Scalar Types
------------

The compiler uses the built-in GraphQL
`scalar types <https://graphql.org/learn/schema/#scalar-types>`__ as well as three custom types:

-   :code:`DateTime` represents timezone-aware second-accuracy timestamps. Values are
    serialized following the ISO-8601 datetime format specification, for example
    "2017-03-21T12:34:56+00:00". All of these fields must be included, including the seconds and the
    time zone, and the format followed exactly, or the behavior is undefined.
-   :code:`Date` represents day-accuracy date objects. Values are serialized following the
    ISO-8601 datetime format specification, for example "2017-03-21". The year, month and day fields
    must be included, and the format followed exactly, or the behavior is undefined.
-   :code:`Decimal` is an arbitrary-precision decimal number object useful for representing values
    that should never be rounded, such as currency amounts. Values are allowed to be transported as
    either a native Decimal type, if the underlying transport allows that, or serialized as strings
    in decimal format, without thousands separators and using a "." as the decimal separator: for
    example, "12345678.012345".

GraphQL Inheritance
-------------------

If compiling to a database without any inheritance, (e.g. all SQL databases), feel free to
ignore this section.

We use two types to model type inheritance in GraphQL: *GraphQL Interface Types* and *GraphQL
Union Types*.

GraphQL Interface Types
~~~~~~~~~~~~~~~~~~~~~~~

GraphQL interfaces represent abstract vertices. They can be queried in the same way that
GraphQL objects are queried and they can be `type coerced <#type-coercion>`.

.. code::

    interface Entity {
        _x_count: Int
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
    }

GraphQL objects can *implement* interfaces, (as in the example below). If an object
implements an interface, then it means that the interface is a superclass of said object. To
implement an interface an object must also contain all of the interface's fields.

.. code::
   :emphasize-lines: 1

    type Food implements Entity {
        _x_count: Int
        name: String
        alias: [String]
        in_Entity_Related: [Entity]
        out_Entity_Related: [Entity]
        in_Species_Eats: [Species]
    }

GraphQL Union Types
~~~~~~~~~~~~~~~~~~~

In the compiler, GraphQL union types along with :code:`type_equivalence_hints` are used to
model concrete inheritance as in the following example.

:code:`Food` is a concrete type. :code:`Species` is also a concrete type. However,
Dogs, Cats and :code:`Food`
