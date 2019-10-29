graphql-compiler
================

|Build Status| |Coverage Status| |License| |PyPI Python| |PyPI Version|
|PyPI Status| |PyPI Wheel|

Turn complex GraphQL queries into optimized database queries.

::

    pip install graphql-compiler

Quick Overview
--------------

Through the GraphQL compiler, users can write powerful queries that
uncover deep relationships in the data while not having to worry about
the underlying database query language. The GraphQL compiler turns
read-only queries written in GraphQL syntax to different query
languages.

Furthermore, the GraphQL compiler validates queries through the use of a
GraphQL schema that specifies the underlying schema of the database. We
we can currently autogenerate GraphQL schemas from OrientDB databases, (see `End-to-End Example
<#end-to-end-example>`__) and from SQL databases, (see `End-to-End SQL Example
<#end-to-end-sql-example>`__).

For a more detailed overview and getting started guide, please see `our
blog
post <https://blog.kensho.com/compiled-graphql-as-a-database-query-language-72e106844282>`__.

Table of contents
-----------------

-  `Features <#features>`__
-  `End-to-End Example <#end-to-end-example>`__
-  `Definitions <#definitions>`__
-  `Directives <#directives>`__

   -  `@optional <#optional>`__
   -  `@output <#output>`__
   -  `@fold <#fold>`__
   -  `@tag <#tag>`__
   -  `@filter <#filter>`__
   -  `@recurse <#recurse>`__
   -  `@output\_source <#output-source>`__

-  `Supported filtering operations <#supported-filtering-operations>`__

   -  `Comparison operators <#comparison-operators>`__
   -  `name\_or\_alias <#name-or-alias>`__
   -  `between <#between>`__
   -  `in\_collection <#in-collection>`__
   -  `not\_in\_collection <#not-in-collection>`__
   -  `has\_substring <#has-substring>`__
   -  `starts\_with <#starts-with>`__
   -  `ends\_with <#ends-with>`__
   -  `contains <#contains>`__
   -  `not\_contains <#not-contains>`__
   -  `intersects <#intersects>`__
   -  `has\_edge\_degree <#has-edge-degree>`__
   -  `is\_null <#is-null>`__
   -  `is\_not\_null <#is-not-null>`__

-  `Type coercions <#type-coercions>`__
-  `Meta fields <#meta-fields>`__

   -  `\_\_typename <#typename>`__
   -  `\_x\_count <#x-count>`__

-  `The GraphQL schema <#the-graphql-schema>`__
-  `Execution model <#execution-model>`__
-  `SQL <#sql>`__

   -  `End-To-End SQL Example <#end-to-end-sql-example>`__
   -  `Advanced Features <#advanced-features>`__

-  `Macro system <#macro-system>`__

   -  `Macro registry <#macro-registry>`__
   -  `Schema for defining macros <#schema-for-defining-macros>`__
   -  `Macro edges <#macro-edges>`__

-  `Miscellaneous <#miscellaneous>`__

   -  `Pretty-Printing GraphQL
      Queries <#pretty-printing-graphql-queries>`__
   -  `Expanding @optional vertex
      fields <#expanding-optional-vertex-fields>`__
   -  `Optional type_equivalence_hints compilation
      parameter <#optional-type_equivalence_hints-parameter>`__
   -  `SchemaGraph <#schemagraph>`__
   -  `Cypher query parameters <#cypher-query-parameters>`__

-  `FAQ <#faq>`__
-  `License <#license>`__

Features
--------

-  **Databases and Query Languages:** We currently support a single
   database, OrientDB version 2.2.28+, and two query languages that
   OrientDB supports: the OrientDB dialect of gremlin, and OrientDB's
   own custom SQL-like query language that we refer to as MATCH, after
   the name of its graph traversal operator. With OrientDB, MATCH should
   be the preferred choice for most users, since it tends to run faster
   than gremlin, and has other desirable properties. See the Execution
   model section for more details.

   Support for relational databases including PostgreSQL, MySQL, SQLite,
   and Microsoft SQL Server is a work in progress. A subset of compiler
   features are available for these databases. See the `SQL <#sql>`__
   section for more details.

-  **GraphQL Language Features:** We prioritized and implemented a subset of all functionality
   supported by the GraphQL language. We hope to add more functionality over time.

End-to-End Example
------------------

Even though this example specifically targets an OrientDB database, it
is meant to be a generic end-to-end example of how to use the GraphQL
compiler.

.. code:: python

    from graphql.utils.schema_printer import print_schema
    from graphql_compiler import (
        get_graphql_schema_from_orientdb_schema_data, graphql_to_match
    )
    from graphql_compiler.schema_generation.orientdb.utils import ORIENTDB_SCHEMA_RECORDS_QUERY

    # Step 1: Get schema metadata from hypothetical Animals database.
    client = your_function_that_returns_an_orientdb_client()
    schema_records = client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
    schema_data = [record.oRecordData for record in schema_records]

    # Step 2: Generate GraphQL schema from metadata.
    schema, type_equivalence_hints = get_graphql_schema_from_orientdb_schema_data(schema_data)

    print(print_schema(schema))
    # schema {
    #    query: RootSchemaQuery
    # }
    #
    # directive @filter(op_name: String!, value: [String!]!) on FIELD | INLINE_FRAGMENT
    #
    # directive @tag(tag_name: String!) on FIELD
    #
    # directive @output(out_name: String!) on FIELD
    #
    # directive @output_source on FIELD
    #
    # directive @optional on FIELD
    #
    # directive @recurse(depth: Int!) on FIELD
    #
    # directive @fold on FIELD
    #
    # type Animal {
    #     name: String
    #     net_worth: Int
    #     limbs: Int
    # }
    #
    # type RootSchemaQuery{
    #     Animal: [Animal]
    # }

    # Step 3: Write GraphQL query that returns the names of all animals with a certain net worth.
    # Note that we prefix net_worth with '$' and surround it with quotes to indicate it's a parameter.
    graphql_query = '''
    {
        Animal {
            name @output(out_name: "animal_name")
            net_worth @filter(op_name: "=", value: ["$net_worth"])
        }
    }
    '''
    parameters = {
        'net_worth': '100',
    }

    # Step 4: Use autogenerated GraphQL schema to compile query into the target database language.
    compilation_result = graphql_to_match(schema, graphql_query, parameters, type_equivalence_hints)
    print(compilation_result.query)
    # SELECT Animal___1.name AS `animal_name`
    # FROM  ( MATCH  { class: Animal, where: ((net_worth = decimal("100"))), as: Animal___1 }
    # RETURN $matches)

Definitions
-----------

-  **Vertex field**: A field corresponding to a vertex in the graph. In
   the below example, :code:`Animal` and :code:`out_Entity_Related` are vertex
   fields. The :code:`Animal` field is the field at which querying starts,
   and is therefore the **root vertex field**. In any scope, fields with
   the prefix :code:`out_` denote vertex fields connected by an outbound
   edge, whereas ones with the prefix :code:`in_` denote vertex fields
   connected by an inbound edge.

   .. code::

       {
           Animal {
               name @output(out_name: "name")
               out_Entity_Related {
                   ... on Species {
                       description @output(out_name: "description")
                   }
               }
           }
       }

-  **Property field**: A field corresponding to a property of a vertex
   in the graph. In the above example, the :code:`name` and :code:`description`
   fields are property fields. In any given scope, **property fields
   must appear before vertex fields**.
-  **Result set**: An assignment of vertices in the graph to scopes
   (locations) in the query. As the database processes the query, new
   result sets may be created (e.g. when traversing edges), and result
   sets may be discarded when they do not satisfy filters or type
   coercions. After all parts of the query are processed by the
   database, all remaining result sets are used to form the query
   result, by taking their values at all properties marked for output.
-  **Scope**: The part of a query between any pair of curly braces. The
   compiler infers the type of each scope. For example, in the above
   query, the scope beginning with :code:`Animal {` is of type :code:`Animal`,
   the one beginning with :code:`out_Entity_Related {` is of type
   :code:`Entity`, and the one beginning with :code:`... on Species {` is of
   type :code:`Species`.
-  **Type coercion**: An operation that produces a new scope of narrower
   type than the scope in which it exists. Any result sets that cannot
   satisfy the narrower type are filtered out and not returned. In the
   above query, :code:`... on Species` is a type coercion which takes its
   enclosing scope of type :code:`Entity`, and coerces it into a narrower
   scope of type :code:`Species`. This is possible since :code:`Entity` is an
   interface, and :code:`Species` is a type that implements the :code:`Entity`
   interface.

Directives
----------

@optional
~~~~~~~~~

Without this directive, when a query includes a vertex field, any
results matching that query must be able to produce a value for that
vertex field. Applied to a vertex field, this directive prevents result
sets that are unable to produce a value for that field from being
discarded, and allowed to continue processing the remainder of the
query.

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
            }
        }
    }

For each :code:`Animal`:

- if it is a parent of another animal, at least one row containing the parent and child animal's
  names, in the :code:`name` and :code:`child_name` columns respectively;
- if it is not a parent of another animal, a row with its name in the :code:`name` column, and a
  :code:`null` value in the :code:`child_name` column.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  :code:`@optional` can only be applied to vertex fields, except the root
   vertex field.
-  It is allowed to expand vertex fields within an :code:`@optional` scope.
   However, doing so is currently associated with a performance penalty
   in :code:`MATCH`. For more detail, see: `Expanding @optional vertex
   fields <#expanding-optional-vertex-fields>`__.
-  :code:`@recurse`, :code:`@fold`, or :code:`@output_source` may not be used at the
   same vertex field as :code:`@optional`.
-  :code:`@output_source` and :code:`@fold` may not be used anywhere within a
   scope marked :code:`@optional`.

If a given result set is unable to produce a value for a vertex field
marked :code:`@optional`, any fields marked :code:`@output` within that vertex
field return the :code:`null` value.

When filtering (via :code:`@filter`) or type coercion (via e.g.
:code:`... on Animal`) are applied at or within a vertex field marked
:code:`@optional`, the :code:`@optional` is given precedence:

- If a given result set cannot produce a value for the optional vertex field, it is
  preserved: the :code:`@optional` directive is applied first, and no filtering or type coercion
  can happen.
- If a given result set is able to produce a value for the optional vertex field, the
  :code:`@optional` does not apply, and that value is then checked against the filtering or type
  coercion. These subsequent operations may then cause the result set to be discarded if it does
  not match.

For example, suppose we have two :code:`Person` vertices with names
:code:`Albert` and :code:`Betty` such that there is a :code:`Person_Knows` edge from
:code:`Albert` to :code:`Betty`.

Then the following query:

.. code::

    {
      Person {
        out_Person_Knows @optional {
          name @filter(op_name: "=", value: ["$name"])
        }
        name @output(out_name: "person_name")
      }
    }

with runtime parameter

.. code:: python

    {
      "name": "Charles"
    }

would output an empty list because the :code:`Person_Knows` edge from
:code:`Albert` to :code:`Betty` satisfies the :code:`@optional` directive, but
:code:`Betty` doesn't match the filter checking for a node with name
:code:`Charles`.

However, if no such :code:`Person_Knows` edge existed from :code:`Albert`, then
the output would be

.. code:: python

    {
      name: 'Albert'
    }

because no such edge can satisfy the :code:`@optional` directive, and no
filtering happens.

@output
~~~~~~~

Denotes that the value of a property field should be included in the
output. Its :code:`out_name` argument specifies the name of the column in
which the output value should be returned.

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")
        }
    }

This query returns the name of each :code:`Animal` in the graph, in a column
named :code:`animal_name`.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  :code:`@output` can only be applied to property fields.
-  The value provided for :code:`out_name` may only consist of upper or
   lower case letters (:code:`A-Z`, :code:`a-z`), or underscores (:code:`_`).
-  The value provided for :code:`out_name` cannot be prefixed with :code:`___`
   (three underscores). This namespace is reserved for compiler internal
   use.
-  For any given query, all :code:`out_name` values must be unique. In other
   words, output columns must have unique names.

If the property field marked :code:`@output` exists within a scope marked
:code:`@optional`, result sets that are unable to assign a value to the
optional scope return the value :code:`null` as the output of that property
field.

@fold
~~~~~

Applying :code:`@fold` on a scope "folds" all outputs from within that
scope: rather than appearing on separate rows in the query result, the
folded outputs are coalesced into parallel lists starting at the scope
marked :code:`@fold`.

It is also possible to output or apply filters to the number of results
captured in a :code:`@fold`. The :code:`_x_count` meta field that is available
within :code:`@fold` scopes represents the number of elements in the fold,
and may be filtered or output as usual. As :code:`_x_count` represents a
count of elements, marking it :code:`@output` will produce an integer value.
See the `\_x\_count <#x-count>`__ section for more details.

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")
            out_Entity_Related @fold {
                ... on Location {
                    _x_count @output(out_name: "location_count")
                    name @output(out_name: "location_names")
                }
            }
        }
    }

Each returned row has three columns: :code:`animal_name` with the name of
each :code:`Animal` in the graph, :code:`location_count` with the related
locations for that :code:`Animal`, and :code:`location_names` with a list of the
names of all related locations of the :code:`Animal` named :code:`animal_name`.
If a given :code:`Animal` has no related locations, its :code:`location_names`
list is empty and the :code:`location_count` value is 0.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  :code:`@fold` can only be applied to vertex fields, except the root
   vertex field.
-  May not exist at the same vertex field as :code:`@recurse`,
   :code:`@optional`, or :code:`@output_source`.
-  Any scope that is either marked with :code:`@fold` or is nested within a
   :code:`@fold` marked scope, may expand at most one vertex field.
-  "No no-op :code:`@fold` scopes": within any :code:`@fold` scope, there must
   either be at least one field that is marked :code:`@output`, or there
   must be a :code:`@filter` applied to the :code:`_x_count` field.
-  All :code:`@output` fields within a :code:`@fold` traversal must be present
   at the innermost scope. It is invalid to expand vertex fields within
   a :code:`@fold` after encountering an :code:`@output` directive.
-  :code:`@tag`, :code:`@recurse`, :code:`@optional`, :code:`@output_source` and
   :code:`@fold` may not be used anywhere within a scope marked :code:`@fold`.
-  The :code:`_x_count` meta field may only appear at the innermost scope of
   a :code:`@fold` marked scope.
-  Marking the :code:`_x_count` meta field with an :code:`@output` produces an
   integer value corresponding to the number of results within that
   fold.
-  Marking for :code:`@output` any field other than the :code:`_x_count` meta
   field produces a list of results, where the number of elements in
   that list is equal to the value of the :code:`_x_count` meta field, if it
   were selected for output.
-  If multiple fields (other than :code:`_x_count`) are marked :code:`@output`,
   the resulting output lists are parallel: the :code:`i`\ th element of
   each such list is the value of the corresponding field of the
   :code:`i`\ th element of the :code:`@fold`, for some fixed order of elements
   in that :code:`@fold`. The order of elements within the output of a
   :code:`@fold` is only fixed for a particular execution of a given query,
   for the results of a given :code:`@fold` that are part of a single result
   set. There is no guarantee of consistent ordering of elements for the
   same :code:`@fold` in any of the following situations:

   -  across two or more result sets that are both the result of the
      execution of the same query;
   -  across different executions of the same query, or
   -  across different queries that contain the same :code:`@fold` scope.

-  Use of type coercions or :code:`@filter` at or within the vertex field
   marked :code:`@fold` is allowed. The order of operations is conceptually
   as follows:

   -  First, type coercions and filters (except :code:`@filter` on the
      :code:`_x_count` meta field) are applied, and any data that does not
      satisfy such coercions and filters is discarded. At this point, the
      size of the fold (i.e. its number of results) is fixed.
   -  Then, any :code:`@filter` directives on the :code:`_x_count` meta field are
      applied, allowing filtering of result sets based on the fold size.
      Any result sets that do not match these filters are discarded.
   -  Finally, if the result set was not discarded by the previous step,
      :code:`@output` directives are processed, selecting folded data for
      output.
-  If the compiler is able to prove that a type coercion in the
   :code:`@fold` scope is actually a no-op, it may optimize it away. See the
   `Optional type_equivalence_hints compilation parameter
   <#optional-type-equivalence-hints-parameter>`__ section for more details.

Example
^^^^^^^

The following GraphQL is *not allowed* and will produce a
:code:`GraphQLCompilationError`. This query is *invalid* for two separate
reasons:

- It expands vertex fields after an :code:`@output` directive (outputting :code:`animal_name`)
- The :code:`in_Animal_ParentOf` scope, which is within a scope marked :code:`@fold`, expands two
  vertex fields instead of at most one.

.. code::

    {
        Animal {
            out_Animal_ParentOf @fold {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf {
                    out_Animal_OfSpecies {
                        uuid @output(out_name: "species_id")
                    }
                    out_Entity_Related {
                        ... on Animal {
                            name @output(out_name: "relative_name")
                        }
                    }
                }
            }
        }
    }

The following GraphQL query is similarly *not allowed* and will produce
a :code:`GraphQLCompilationError`, since the :code:`_x_count` field is not
within the innermost scope in the :code:`@fold`.

.. code::

    {
        Animal {
            out_Animal_ParentOf @fold {
                _x_count @output(out_name: "related_count")
                out_Entity_Related {
                    ... on Animal {
                        name @output(out_name: "related_name")
                    }
                }
            }
        }
    }

Moving the :code:`_x_count` field to the innermost scope results in the
following valid use of :code:`@fold`:

.. code::

    {
        Animal {
            out_Animal_ParentOf @fold {
                out_Entity_Related {
                    ... on Animal {
                        _x_count @output(out_name: "related_count")
                        name @output(out_name: "related_name")
                    }
                }
            }
        }
    }

Here is an example of query whose :code:`@fold` does not output any data; it
returns the names of all animals that have more than :code:`count` children
whose names contain the substring :code:`substr`:

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ParentOf @fold {
                _x_count @filter(op_name: ">=", value: ["$count"])
                name @filter(op_name: "has_substring", value: ["$substr"])
            }
        }
    }

@tag
~~~~

The :code:`@tag` directive enables filtering based on values encountered
elsewhere in the same query. Applied on a property field, it assigns a
name to the value of that property field, allowing that value to then be
used as part of a :code:`@filter` directive.

To supply a tagged value to a :code:`@filter` directive, place the tag name
(prefixed with a :code:`%` symbol) in the :code:`@filter`'s :code:`value` array. See
`Passing parameters <#passing-parameters>`__ for more details.

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @tag(tag_name: "parent_name")
            out_Animal_ParentOf {
                name @filter(op_name: "<", value: ["%parent_name"])
                     @output(out_name: "child_name")
            }
        }
    }

Each row returned by this query contains, in the :code:`child_name` column,
the name of an :code:`Animal` that is the child of another :code:`Animal`, and
has a name that is lexicographically smaller than the name of its
parent.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  :code:`@tag` can only be applied to property fields.
-  The value provided for :code:`tag_name` may only consist of upper or
   lower case letters (:code:`A-Z`, :code:`a-z`), or underscores (:code:`_`).
-  For any given query, all :code:`tag_name` values must be unique.
-  Cannot be applied to property fields within a scope marked :code:`@fold`.
-  Using a :code:`@tag` and a :code:`@filter` that references the tag within the
   same vertex is allowed, so long as the two do not appear on the exact
   same property field.

@filter
~~~~~~~

Allows filtering of the data to be returned, based on any of a set of
filtering operations. Conceptually, it is the GraphQL equivalent of the
SQL :code:`WHERE` keyword.

See `Supported filtering operations <#supported-filtering-operations>`__
for details on the various types of filtering that the compiler
currently supports. These operations are currently hardcoded in the
compiler; in the future, we may enable the addition of custom filtering
operations via compiler plugins.

Multiple :code:`@filter` directives may be applied to the same field at
once. Conceptually, it is as if the different :code:`@filter` directives
were joined by SQL :code:`AND` keywords.

Using a :code:`@tag` and a :code:`@filter` that references the tag within the
same vertex is allowed, so long as the two do not appear on the exact
same property field.

Passing Parameters
^^^^^^^^^^^^^^^^^^

The :code:`@filter` directive accepts two types of parameters: runtime
parameters and tagged parameters.

**Runtime parameters** are represented with a :code:`$` prefix (e.g.
:code:`$foo`), and denote parameters whose values will be known at runtime.
The compiler will compile the GraphQL query leaving a spot for the value
to fill at runtime. After compilation, the user will have to supply
values for all runtime parameters, and their values will be inserted
into the final query before it can be executed against the database.

Consider the following query:

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")
            color @filter(op_name: "=", value: ["$animal_color"])
        }
    }

It returns one row for every :code:`Animal` vertex that has a color equal to
:code:`$animal_color`. Each row contains the animal's name in a column named
:code:`animal_name`. The parameter :code:`$animal_color` is a runtime parameter
-- the user must pass in a value (e.g. :code:`{"animal_color": "blue"}`)
that will be inserted into the query before querying the database.

**Tagged parameters** are represented with a :code:`%` prefix (e.g.
:code:`%foo`) and denote parameters whose values are derived from a property
field encountered elsewhere in the query. If the user marks a property
field with a :code:`@tag` directive and a suitable name, that value becomes
available to use as a tagged parameter in all subsequent :code:`@filter`
directives.

Consider the following query:

.. code::

    {
        Animal {
            name @tag(out_name: "parent_name")
            out_Animal_ParentOf {
                name @filter(op_name: "has_substring", value: ["%parent_name"])
                     @output(out_name: "child_name")
            }
        }
    }

It returns the names of animals that contain their parent's name as a
substring of their own. The database captures the value of the parent
animal's name as the :code:`parent_name` tag, and this value is then used as
the :code:`%parent_name` tagged parameter in the child animal's :code:`@filter`.

We considered and **rejected** the idea of allowing literal values (e.g.
:code:`123`) as :code:`@filter` parameters, for several reasons:

- The GraphQL type of the :code:`@filter` directive's :code:`value` field cannot reasonably
  encompass all the different types of arguments that people might supply. Even counting scalar
  types only, there's already :code:`ID, Int, Float, Boolean, String, Date, DateTime...` -- way
  too many to include.
- Literal values would be used when the parameter's value is known to be fixed. We can just as
  easily accomplish the same thing by using a runtime parameter with a fixed value. That approach
  has the added benefit of potentially reducing the number of different queries that have to be
  compiled: two queries with different literal values would have to be compiled twice, whereas
  using two different sets of runtime arguments only requires the compilation of one query.
- We were concerned about the potential for accidental misuse of literal values. SQL systems have
  supported stored procedures and parameterized queries for decades, and yet ad-hoc SQL query
  construction via simple string interpolation is still a serious problem and is the source of
  many SQL injection vulnerabilities. We felt that disallowing literal values in the query will
  drastically reduce both the use and the risks of unsafe string interpolation, at an acceptable
  cost.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  The value provided for :code:`op_name` may only consist of upper or lower
   case letters (:code:`A-Z`, :code:`a-z`), or underscores (:code:`_`).
-  Values provided in the :code:`value` list must start with either :code:`$`
   (denoting a runtime parameter) or :code:`%` (denoting a tagged
   parameter), followed by exclusively upper or lower case letters
   (:code:`A-Z`, :code:`a-z`) or underscores (:code:`_`).
-  The :code:`@tag` directives corresponding to any tagged parameters in a
   given :code:`@filter` query must be applied to fields that appear either
   at the same vertex as the one with the :code:`@filter`, or strictly
   before the field with the :code:`@filter` directive.
-  "Can't compare apples and oranges" -- the GraphQL type of the
   parameters supplied to the :code:`@filter` must match the GraphQL types
   the compiler infers based on the field the :code:`@filter` is applied to.
-  If the :code:`@tag` corresponding to a tagged parameter originates from
   within a vertex field marked :code:`@optional`, the emitted code for the
   :code:`@filter` checks if the :code:`@optional` field was assigned a value.
   If no value was assigned to the :code:`@optional` field, comparisons
   against the tagged parameter from within that field return :code:`True`.

   -  For example, assuming :code:`%from_optional` originates from an
      :code:`@optional` scope, when no value is assigned to the :code:`@optional`
      field:

      -  using :code:`@filter(op_name: "=", value: ["%from_optional"])` is
         equivalent to not having the filter at all;
      -  using :code:`@filter(op_name: "between", value: ["$lower", "%from_optional"])`
         is equivalent to :code:`@filter(op_name: ">=", value: ["$lower"])`.

-  Using a :code:`@tag` and a :code:`@filter` that references the tag within the
   same vertex is allowed, so long as the two do not appear on the exact
   same property field.

@recurse
~~~~~~~~

Applied to a vertex field, specifies that the edge connecting that
vertex field to the current vertex should be visited repeatedly, up to
:code:`depth` times. The recursion always starts at :code:`depth = 0`, i.e. the
current vertex -- see the below sections for a more thorough
explanation.

Example Use
^^^^^^^^^^^

Say the user wants to fetch the names of the children and grandchildren
of each :code:`Animal`. That could be accomplished by running the following
two queries and concatenating their results:

.. code::

    {
        Animal {
            name @output(out_name: "ancestor")
            out_Animal_ParentOf {
                name @output(out_name: "descendant")
            }
        }
    }

.. code::

    {
        Animal {
            name @output(out_name: "ancestor")
            out_Animal_ParentOf {
                out_Animal_ParentOf {
                    name @output(out_name: "descendant")
                }
            }
        }
    }

If the user then wanted to also add great-grandchildren to the
:code:`descendants` output, that would require yet another query, and so on.
Instead of concatenating the results of multiple queries, the user can
simply use the :code:`@recurse` directive. The following query returns the
child and grandchild descendants:

.. code::

    {
        Animal {
            name @output(out_name: "ancestor")
            out_Animal_ParentOf {
                out_Animal_ParentOf @recurse(depth: 1) {
                    name @output(out_name: "descendant")
                }
            }
        }
    }

Each row returned by this query contains the name of an :code:`Animal` in
the :code:`ancestor` column and the name of its child or grandchild in the
:code:`descendant` column. The :code:`out_Animal_ParentOf` vertex field marked
:code:`@recurse` is already enclosed within another :code:`out_Animal_ParentOf`
vertex field, so the recursion starts at the "child" level (the
:code:`out_Animal_ParentOf` not marked with :code:`@recurse`). Therefore, the
:code:`descendant` column contains the names of an :code:`ancestor`'s children
(from :code:`depth = 0` of the recursion) and the names of its grandchildren
(from :code:`depth = 1`).

Recursion using this directive is possible since the types of the
enclosing scope and the recursion scope work out: the :code:`@recurse`
directive is applied to a vertex field of type :code:`Animal` and its vertex
field is enclosed within a scope of type :code:`Animal`. Additional cases
where recursion is allowed are described in detail below.

The :code:`descendant` column cannot have the name of the :code:`ancestor`
animal since the :code:`@recurse` is already within one
:code:`out_Animal_ParentOf` and not at the root :code:`Animal` vertex field.
Similarly, it cannot have descendants that are more than two steps
removed (e.g., great-grandchildren), since the :code:`depth` parameter of
:code:`@recurse` is set to :code:`1`.

Now, let's see what happens when we eliminate the outer
:code:`out_Animal_ParentOf` vertex field and simply have the :code:`@recurse`
applied on the :code:`out_Animal_ParentOf` in the root vertex field scope:

.. code::

    {
        Animal {
            name @output(out_name: "ancestor")
            out_Animal_ParentOf @recurse(depth: 1) {
                name @output(out_name: "self_or_descendant")
            }
        }
    }

In this case, when the recursion starts at :code:`depth = 0`, the :code:`Animal`
within the recursion scope will be the same :code:`Animal` at the root
vertex field, and therefore, in the :code:`depth = 0` step of the recursion,
the value of the :code:`self_or_descendant` field will be equal to the value
of the :code:`ancestor` field.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  "The types must work out" -- when applied within a scope of type
   :code:`A`, to a vertex field of type :code:`B`, at least one of the following
   must be true:

   -  :code:`A` is a GraphQL union;
   -  :code:`B` is a GraphQL interface, and :code:`A` is a type that implements
      that interface;
   -  :code:`A` and :code:`B` are the same type.
-  :code:`@recurse` can only be applied to vertex fields other than the root
   vertex field of a query.
-  Cannot be used within a scope marked :code:`@optional` or :code:`@fold`.
-  The :code:`depth` parameter of the recursion must always have a value
   greater than or equal to 1. Using :code:`depth = 1` produces the current
   vertex and its neighboring vertices along the specified edge.
-  Type coercions and :code:`@filter` directives within a scope marked
   :code:`@recurse` do not limit the recursion depth. Conceptually,
   recursion to the specified depth happens first, and then type
   coercions and :code:`@filter` directives eliminate some of the locations
   reached by the recursion.
-  As demonstrated by the examples above, the recursion always starts at
   depth 0, so the recursion scope always includes the vertex at the
   scope that encloses the vertex field marked :code:`@recurse`.

@output\_source
~~~~~~~~~~~~~~~

See the `Completeness of returned
results <#completeness-of-returned-results>`__ section for a description
of the directive and examples.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  May exist at most once in any given GraphQL query.
-  Can exist only on a vertex field, and only on the last vertex field
   used in the query.
-  Cannot be used within a scope marked :code:`@optional` or :code:`@fold`.

Supported filtering operations
------------------------------

Comparison operators
~~~~~~~~~~~~~~~~~~~~

Supported comparison operators:

- Equal to: :code:`=`
- Not equal to: :code:`!=`
- Greater than: :code:`>`
- Less than: :code:`<`
- Greater than or equal to: :code:`>=`
- Less than or equal to: :code:`<=`

Example Use
^^^^^^^^^^^

Equal to (:code:`=`):
'''''''''''''''''''''

.. code::

    {
        Species {
            name @filter(op_name: "=", value: ["$species_name"])
            uuid @output(out_name: "species_uuid")
        }
    }

This returns one row for every :code:`Species` whose name is equal to the
value of the :code:`$species_name` parameter. Each row contains the :code:`uuid`
of the :code:`Species` in a column named :code:`species_uuid`.

Greater than or equal to (:code:`>=`):
''''''''''''''''''''''''''''''''''''''

.. code::

    {
        Animal {
            name @output(out_name: "name")
            birthday @output(out_name: "birthday")
                     @filter(op_name: ">=", value: ["$point_in_time"])
        }
    }

This returns one row for every :code:`Animal` vertex that was born after or
on a :code:`$point_in_time`. Each row contains the animal's name and
birthday in columns named :code:`name` and :code:`birthday`, respectively.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  All comparison operators must be on a property field.

name\_or\_alias
~~~~~~~~~~~~~~~

Allows you to filter on vertices which contain the exact string
:code:`$wanted_name_or_alias` in their :code:`name` or :code:`alias` fields.

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal @filter(op_name: "name_or_alias", value: ["$wanted_name_or_alias"]) {
            name @output(out_name: "name")
        }
    }

This returns one row for every :code:`Animal` vertex whose name and/or alias
is equal to :code:`$wanted_name_or_alias`. Each row contains the animal's
name in a column named :code:`name`.

The value provided for :code:`$wanted_name_or_alias` must be the full name
and/or alias of the :code:`Animal`. Substrings will not be matched.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a vertex field that has :code:`name` and :code:`alias` properties.

between
~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "name")
            birthday @filter(op_name: "between", value: ["$lower", "$upper"])
                     @output(out_name: "birthday")
        }
    }

This returns:

- One row for every :code:`Animal` vertex whose birthday is in between :code:`$lower` and
  :code:`$upper` dates (inclusive). Each row contains the animal's name in a column named
  :code:`name`.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a property field.
-  The lower and upper bounds represent an inclusive interval, which
   means that the output may contain values that match them exactly.

in\_collection
~~~~~~~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")
            color @output(out_name: "color")
                  @filter(op_name: "in_collection", value: ["$colors"])
        }
    }

This returns one row for every :code:`Animal` vertex which has a color
contained in a list of colors. Each row contains the :code:`Animal`'s name
and color in columns named :code:`animal_name` and :code:`color`, respectively.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a property field that is not of list type.

not\_in\_collection
~~~~~~~~~~~~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")
            color @output(out_name: "color")
                  @filter(op_name: "not_in_collection", value: ["$colors"])
        }
    }

This returns one row for every :code:`Animal` vertex which has a color not
contained in a list of colors. Each row contains the :code:`Animal`'s name
and color in columns named :code:`animal_name` and :code:`color`, respectively.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a property field that is not of list type.

has\_substring
~~~~~~~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @filter(op_name: "has_substring", value: ["$substring"])
                 @output(out_name: "animal_name")
        }
    }

This returns one row for every :code:`Animal` vertex whose name contains the
value supplied for the :code:`$substring` parameter. Each row contains the
matching :code:`Animal`'s name in a column named :code:`animal_name`.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a property field of string type.

starts\_with
~~~~~~~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @filter(op_name: "starts_with", value: ["$prefix"])
                 @output(out_name: "animal_name")
        }
    }

This returns one row for every :code:`Animal` vertex whose name starts with the
value supplied for the :code:`$prefix` parameter. Each row contains the
matching :code:`Animal`'s name in a column named :code:`animal_name`.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a property field of string type.

ends\_with
~~~~~~~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @filter(op_name: "ends_with", value: ["$suffix"])
                 @output(out_name: "animal_name")
        }
    }

This returns one row for every :code:`Animal` vertex whose name ends with the
value supplied for the :code:`$suffix` parameter. Each row contains the
matching :code:`Animal`'s name in a column named :code:`animal_name`.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a property field of string type.

contains
~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            alias @filter(op_name: "contains", value: ["$wanted"])
            name @output(out_name: "animal_name")
        }
    }

This returns one row for every :code:`Animal` vertex whose list of aliases
contains the value supplied for the :code:`$wanted` parameter. Each row
contains the matching :code:`Animal`'s name in a column named
:code:`animal_name`.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a property field of list type.

not\_contains
~~~~~~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            alias @filter(op_name: "not_contains", value: ["$wanted"])
            name @output(out_name: "animal_name")
        }
    }

This returns one row for every :code:`Animal` vertex whose list of aliases
does not contain the value supplied for the :code:`$wanted` parameter. Each
row contains the matching :code:`Animal`'s name in a column named
:code:`animal_name`.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a property field of list type.

intersects
~~~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            alias @filter(op_name: "intersects", value: ["$wanted"])
            name @output(out_name: "animal_name")
        }
    }

This returns one row for every :code:`Animal` vertex whose list of aliases
has a non-empty intersection with the list of values supplied for the
:code:`$wanted` parameter. Each row contains the matching :code:`Animal`'s name
in a column named :code:`animal_name`.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a property field of list type.

has\_edge\_degree
~~~~~~~~~~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")

            out_Animal_ParentOf @filter(op_name: "has_edge_degree", value: ["$child_count"]) @optional {
                uuid
            }
        }
    }

This returns one row for every :code:`Animal` vertex that has exactly
:code:`$child_count` children (i.e. where the :code:`out_Animal_ParentOf` edge
appears exactly :code:`$child_count` times). Each row contains the matching
:code:`Animal`'s name, in a column named :code:`animal_name`.

The :code:`uuid` field within the :code:`out_Animal_ParentOf` vertex field is
added simply to satisfy the GraphQL syntax rule that requires at least
one field to exist within any :code:`{}`. Since this field is not marked
with any directive, it has no effect on the query.

*N.B.:* Please note the :code:`@optional` directive on the vertex field
being filtered above. If in your use case you expect to set
:code:`$child_count` to 0, you must also mark that vertex field
:code:`@optional`. Recall that absence of :code:`@optional` implies that at
least one such edge must exist. If the :code:`has_edge_degree` filter is
used with a parameter set to 0, that requires the edge to not exist.
Therefore, if the :code:`@optional` is not present in this situation, no
valid result sets can be produced, and the resulting query will return
no results.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be on a vertex field that is not the root vertex of the query.
-  Tagged values are not supported as parameters for this filter.
-  If the runtime parameter for this operator can be :code:`0`, it is
   *strongly recommended* to also apply :code:`@optional` to the vertex
   field being filtered (see N.B. above for details).

is\_null
~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")
            color @filter(op_name: "is_null", value: [])
        }
    }

This returns one row for every :code:`Animal` that does not have a color
defined.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be applied on a property field.
-  :code:`value` must be empty.

is\_not\_null
~~~~~~~~~~~~~

Example Use
^^^^^^^^^^^

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")
            color @filter(op_name: "is_not_null", value: [])
        }
    }

This returns one row for every :code:`Animal` that has a color defined.

Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  Must be applied on a property field.
-  :code:`value` must be empty.

Type coercions
--------------

Type coercions are operations that create a new scope whose type is
different than the type of the enclosing scope of the coercion -- they
coerce the enclosing scope into a different type. Type coercions are
represented with GraphQL inline fragments.

Example Use
~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~

-  Must be the only selection in scope. No field may exist in the same
   scope as a type coercion. No scope may contain more than one type
   coercion.

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

::

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

The GraphQL schema
------------------

This section assumes that the reader is familiar with the way schemas
work in the `reference implementation of
GraphQL <http://graphql.org/learn/schema/>`__.

The GraphQL schema used with the compiler must contain the custom
directives and custom :code:`Date` and :code:`DateTime` scalar types defined by
the compiler:

.. code::

    directive @recurse(depth: Int!) on FIELD

    directive @filter(value: [String!]!, op_name: String!) on FIELD | INLINE_FRAGMENT

    directive @tag(tag_name: String!) on FIELD

    directive @output(out_name: String!) on FIELD

    directive @output_source on FIELD

    directive @optional on FIELD

    directive @fold on FIELD

    scalar DateTime

    scalar Date

If constructing the schema programmatically, one can simply import the
the Python object representations of the custom directives and the
custom types:

.. code:: python

    from graphql_compiler import DIRECTIVES  # the list of custom directives
    from graphql_compiler import GraphQLDate, GraphQLDateTime  # the custom types

Since the GraphQL and OrientDB type systems have different rules, there
is no one-size-fits-all solution to writing the GraphQL schema for a
given database schema. However, the following rules of thumb are useful
to keep in mind:

- Generally, represent OrientDB abstract classes as GraphQL interfaces. In GraphQL's type system,
  GraphQL interfaces cannot inherit from other GraphQL interfaces.
- Generally, represent OrientDB non-abstract classes as GraphQL types, listing the GraphQL
  interfaces that they implement. In GraphQL's type system, GraphQL types cannot inherit from
  other GraphQL types.
- Inheritance relationships between two OrientDB non-abstract classes, or between two OrientDB
  abstract classes, introduce some difficulties in GraphQL. When modelling your data in OrientDB,
  it's best to avoid such inheritance if possible.
- If it is impossible to avoid having two non-abstract OrientDB classes :code:`A` and :code:`B`
  such that :code:`B` inherits from :code:`A`, you have two options:

  - You may choose to represent the :code:`A` OrientDB class as a GraphQL
    interface, which the GraphQL type corresponding to :code:`B` can implement.
    In this case, the GraphQL schema preserves the inheritance relationship between :code:`A` and
    :code:`B`, but sacrifices the representation of any inheritance relationships :code:`A` may
    have with any OrientDB superclasses.
  - You may choose to represent both :code:`A` and :code:`B` as GraphQL types. The tradeoff in
    this case is exactly the opposite from the previous case: the GraphQL schema sacrifices the
    inheritance relationship between :code:`A` and :code:`B`, but preserves the inheritance
    relationships of :code:`A` with its superclasses. In this case, it is recommended to create a
    GraphQL union type :code:`A | B`, and to use that GraphQL union type for any vertex fields
    that in OrientDB would be of type :code:`A`.
- If it is impossible to avoid having two abstract OrientDB classes :code:`A` and :code:`B`
  such that :code:`B` inherits from :code:`A`, you similarly have two options:

  - You may choose to represent :code:`B` as a GraphQL type that can implement the GraphQL interface corresponding
    to :code:`A`. This makes the GraphQL schema preserve the inheritance relationship between
    :code:`A` and :code:`B`, but sacrifices the ability for other GraphQL types to inherit from
    :code:`B`.
  - You may choose to represent both :code:`A` and :code:`B` as GraphQL interfaces,
    sacrificing the schema's representation of the inheritance between :code:`A` and :code:`B`, but
    allowing GraphQL types to inherit from both :code:`A` and :code:`B`. If necessary, you can
    then create a GraphQL union type :code:`A | B` and use it for any vertex fields that in
    OrientDB would be of type :code:`A`.
- It is legal to fully omit classes and fields that are not representable in
  GraphQL. The compiler currently does not support OrientDB's :code:`EmbeddedMap` type nor
  embedded non-primitive typed fields, so such fields can simply be omitted in the GraphQL
  representation of their classes. Alternatively, the entire OrientDB class and all edges that may
  point to it may be omitted entirely from the GraphQL schema.

Execution model
---------------

Since the GraphQL compiler can target multiple different query
languages, each with its own behaviors and limitations, the execution
model must also be defined as a function of the compilation target
language. While we strive to minimize the differences between
compilation targets, some differences are unavoidable.

The compiler abides by the following principles:

- When the database is queried with a compiled query string, its response must always be in the
  form of a list of results.
- The precise format of each such result is defined by each compilation target separately.

  - :code:`gremlin`, :code:`MATCH` and :code:`SQL` return data in a tabular format, where each
    result is a row of the table, and fields marked for output are columns.
  - However, future compilation targets may have a different format. For example,
    each result may appear in the nested tree format used by the standard
    GraphQL specification.
- Each such result must satisfy all directives and types in its corresponding GraphQL query.
- The returned list of results is **not** guaranteed to be complete!

  - In other words, there may have been additional result sets that satisfy all directives and
    types in the corresponding GraphQL query, but were not returned by the database.
  - However, compilation target implementations are encouraged to return complete results if at all
    practical. The :code:`MATCH` compilation target is guaranteed to produce complete results.

Completeness of returned results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To explain the completeness of returned results in more detail, assume
the database contains the following example graph:

::

    a  ---->_ x
    |____   /|
        _|_/
       / |____
      /      \/
    b  ----> y

Let :code:`a, b, x, y` be the values of the :code:`name` property field of four
vertices. Let the vertices named :code:`a` and :code:`b` be of type :code:`S`, and
let :code:`x` and :code:`y` be of type :code:`T`. Let vertex :code:`a` be connected to
both :code:`x` and :code:`y` via directed edges of type :code:`E`. Similarly, let
vertex :code:`b` also be connected to both :code:`x` and :code:`y` via directed
edges of type :code:`E`.

Consider the GraphQL query:

.. code::

    {
        S {
            name @output(out_name: "s_name")
            out_E {
                name @output(out_name: "t_name")
            }
        }
    }

Between the data in the database and the query's structure, it is clear
that combining any of :code:`a` or :code:`b` with any of :code:`x` or :code:`y` would
produce a valid result. Therefore, the complete result list, shown here
in JSON format, would be:

.. code:: python

    [
        {"s_name": "a", "t_name": "x"},
        {"s_name": "a", "t_name": "y"},
        {"s_name": "b", "t_name": "x"},
        {"s_name": "b", "t_name": "y"},
    ]

This is precisely what the :code:`MATCH` compilation target is guaranteed to
produce. The remainder of this section is only applicable to the
:code:`gremlin` compilation target. If using :code:`MATCH`, all of the queries
listed in the remainder of this section will produce the same, complete
result list.

Since the :code:`gremlin` compilation target does not guarantee a complete
result list, querying the database using a query string generated by the
:code:`gremlin` compilation target will produce only a partial result list
resembling the following:

.. code:: python

    [
        {"s_name": "a", "t_name": "x"},
        {"s_name": "b", "t_name": "x"},
    ]

Due to limitations in the underlying query language, :code:`gremlin` will by
default produce at most one result for each of the starting locations in
the query. The above Gr aphQL query started at the type :code:`S`, so each
:code:`s_name` in the returned result list is therefore distinct.
Furthermore, there is no guarantee (and no way to know ahead of time)
whether :code:`x` or :code:`y` will be returned as the :code:`t_name` value in each
result, as they are both valid results.

Users may apply the :code:`@output_source` directive on the last scope of
the query to alter this behavior:

.. code::

    {
        S {
            name @output(out_name: "s_name")
            out_E @output_source {
                name @output(out_name: "t_name")
            }
        }
    }

Rather than producing at most one result for each :code:`S`, the query will
now produce at most one result for each distinct value that can be found
at :code:`out_E`, where the directive is applied:

.. code:: python

    [
        {"s_name": "a", "t_name": "x"},
        {"s_name": "a", "t_name": "y"},
    ]

Conceptually, applying the :code:`@output_source` directive makes it as if
the query were written in the opposite order:

.. code::

    {
        T {
            name @output(out_name: "t_name")
            in_E {
                name @output(out_name: "s_name")
            }
        }
    }

SQL
---

Relational databases are supported by compiling to SQLAlchemy core as an intermediate
language, and then relying on SQLAlchemy's compilation of the dialect-specific SQL query. The
compiler does not return a string for SQL compilation, but instead a SQLAlchemy :code:`Query`
object that can be executed through a SQLAlchemy `engine
<https://docs.sqlalchemy.org/en/latest/core/engines.html>`__.

Our SQL backend supports basic traversals, filters, tags and outputs, but there are still some
pieces in development:

- Directives: :code:`@fold`
- Filter operators: :code:`has_edge_degree`
- Dialect-specific features, like Postgres array types, and use of filter operators
  specific to them: :code:`contains`, :code:`intersects`, :code:`name_or_alias`
- Meta fields: :code:`__typename`, :code:`_x_count`

End-to-End SQL Example
~~~~~~~~~~~~~~~~~~~~~~

To query a SQL backend simply reflect the needed schema data from the database using SQLAlchemy,
compile the GraphQL query to a SQLAlchemy :code:`Query`, and execute the query against the engine
as in the example below:

.. code:: python

    from graphql_compiler import get_sqlalchemy_schema_info_from_specified_metadata, graphql_to_sql
    from sqlalchemy import MetaData, create_engine

    engine = create_engine('<connection string>')

    # Reflect the default database schema. Each table must have a primary key.
    # See "Including tables without explicitly enforced primary keys" otherwise.
    metadata = MetaData(bind=engine)
    metadata.reflect()

    # Wrap the schema information into a SQLAlchemySchemaInfo object.
    sql_schema_info = get_sqlalchemy_schema_info_from_specified_metadata(
        metadata.tables, {}, engine.dialect)

    # Write GraphQL query.
    graphql_query = '''
    {
        Animal {
            name @output(out_name: "animal_name")
        }
    }
    '''
    parameters = {}

    # Compile and execute query.
    compilation_result = graphql_to_sql(sql_schema_info, graphql_query, parameters)
    query_results = [dict(row) for row in engine.execute(compilation_result.query)]

Advanced Features
~~~~~~~~~~~~~~~~~

SQL Edges
^^^^^^^^^^^^^^^^^^^^
Edges can be specified in SQL through the :code:`direct_edges` parameter as illustrated
below. SQL edges gets rendered as :code:`out_edgeName` and :code:`in_edgeName` in the source and
destination GraphQL objects respectively and edge traversals get compiled to SQL joins between the
source and destination tables using the specified columns. We use the term :code:`direct_edges`
below since the compiler may support other types of SQL edges in the future such as edges that are
backed by SQL `association tables <https://en.wikipedia.org/wiki/Associative_entity>`__.

.. code:: python

    from graphql_compiler import get_sqlalchemy_schema_info_from_specified_metadata, graphql_to_sql
    from graphql_compiler.schema_generation.sqlalchemy.edge_descriptors import DirectEdgeDescriptor
    from sqlalchemy import MetaData, create_engine

    # Set engine and reflect database metadata. (See example above for more details).
    engine = create_engine('<connection string>')
    metadata = MetaData(bind=engine)
    metadata.reflect()

    # Specify SQL edges.
    direct_edges = {
        'Animal_LivesIn': DirectEdgeDescriptor(
            from_vertex='Animal',  # Name of the source GraphQL object as specified.
            from_column='location',  # Name of the column of the underlying source table to join on.
            to_vertex='Location',  # Name of the destination GraphQL object as specified.
            to_column='uuid',   # Name of the column of the underlying destination table to join on.
         )
    }

    # Wrap the schema information into a SQLAlchemySchemaInfo object.
    sql_schema_info = get_sqlalchemy_schema_info_from_specified_metadata(
        metadata.tables, direct_edges, engine.dialect)

    # Write GraphQL query with edge traversal.
    graphql_query = '''
    {
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_LivesIn {
                name @output(out_name: "location_name")
            }
        }
    }
    '''

    # Compile query. Note that the edge traversal gets compiled to a SQL join.
    compilation_result = graphql_to_sql(sql_schema_info, graphql_query, {})


Including tables without explicitly enforced primary keys
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The compiler requires that each SQLAlchemy :code:`Table` object in the :code:`SQLALchemySchemaInfo`
has a primary key. However, the primary key in the :code:`Table` need not be the primary key in
the underlying table. It may simply be a non-null and unique identifier of each row. To override
the primary key of SQLAlchemy :code:`Table` objects reflected from a database please follow the
instructions in `this link
<https://docs.sqlalchemy.org/en/13/core/reflection.html#overriding-reflected-columns>`__.

Including tables from multiple schemas
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

SQLAlchemy and SQL database management systems support the concept of multiple `schemas
<https://docs.sqlalchemy.org/en/13/core/metadata.html?highlight=schema#specifying-the-schema-name>`__.
One can include :code:`Table` objects from multiple schemas in the same
:code:`SQLAlchemySchemaInfo`. However, when doing so, one cannot simply use table names as
GraphQL object names because two tables in different schemas can have the
same the name. A solution that is not quite guaranteed to work, but will likely work in practice
is to prepend the schema name as follows:

.. code:: python

    vertex_name_to_table = {}
    for table in metadata.values():
        # The schema field may be None if the database name is specified in the connection string
        # and the table is in the default schema, (e.g. 'dbo' for mssql and 'public' for postgres).
        if table.schema:
            vertex_name = 'dbo' + table.name
        else:
            # If the database name is not specified in the connection string, then
            # the schema field is of the form <databaseName>.<schemaName>.
            # Since dots are not allowed in GraphQL type names we must remove them here.
            vertex_name = table.schema.replace('.', '') + table.name

        if vertex_name in vertex_name_to_table:
            raise AssertionError('Found two tables with conflicting GraphQL object names.')

        vertex_name_to_table[vertex_name] = table

Including manually defined :code:`Table` objects
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :code:`Table` objects in the :code:`SQLAlchemySchemaInfo` do not need to be reflected from the
database. They also can be manually specified as in `this link
<https://docs.sqlalchemy.org/en/13/core/metadata.html#creating-and-dropping-database-tables>`__.
However, if specifying :code:`Table` objects manually, please make sure to include a primary key
for each table and to use only SQL types allowed for the dialect specified in the
:code:`SQLAlchemySchemaInfo`.

Macro system
------------

The macro system allows users to reshape how they *perceive* their data, without requiring changes
to the underlying database structures themselves.

In many real-life situations, the database schema does not fit the user's mental model of the data.
There are many causes of this, the most common one being database normalization.
The representation of the data that is convenient for storage within a database is rarely
the representation that makes for easy querying. As a result, users' queries frequently
include complex and repetitive query structures that work around the database's chosen data model.

The compiler's macro system empowers users *reshaping* their data's structure to fit
their mental model, minimizing query complexity and repetitiveness without requiring changes
to the shape of the data in the underlying data systems. The compiler achieves this by allowing
users to define **macros** -- type-safe rules for programmatic query rewriting
that transform user-provided queries on the *desired* data model into
queries on the *actual* data model in the underlying data systems.

When macros are defined, the compiler loads them into a `macro registry <Macro registry>`_ -- a
data structure that tracks all currently available macros, the resulting GraphQL schema
(accounting for macros), and any additional metadata needed by the compiler.
The compiler then leverages this registry to expand queries that rely on macros,
rewriting them into equivalent queries that do not contain any macros and therefore
reflect the actual underlying data model.

This makes macros somewhat similar to SQL's idea of non-materialized views,
though there are some key differences:

- SQL views require database access and special permissions; databases are
  completely oblivious to the use of macros since by the time the database gets the query,
  all macro uses have been already expanded.

- Macros can be stored and expanded client-side, so different users that query the same system may
  define their own personal macros which are not shared with other users or the server that executes
  the users' GraphQL queries. This is generally not achievable with SQL.

- Since macro expansion does not interact in any way with the underlying data system, it works
  seamlessly with all databases and even on schemas stitched together from multiple databases.
  In contrast, not all databases support SQL-like :code:`VIEW` functionality.

Currently, the compiler supports one type of macro: `macro edges <Macro edges>`_, which allow
the creation of "virtual" edges computed from existing ones.
More types of macros are coming in the future.

Macro registry
~~~~~~~~~~~~~~

The macro registry is where the definitions of all currently defined macros are stored,
together with the resulting GraphQL schema they form, as well as any associated metadata
that the compiler's macro system may need in order to expand any macros encountered in a query.

To create a macro registry object for a given GraphQL schema, use the :code:`create_macro_registry`
function:

.. code:: python

    from graphql_compiler.macros import create_macro_registry

    macro_registry = create_macro_registry(your_graphql_schema_object)

To retrieve the GraphQL schema object with all its macro-based additions, use
the :code:`get_schema_with_macros` function:

.. code:: python

    from graphql_compiler.macros import get_schema_with_macros

    graphql_schema = get_schema_with_macros(macro_registry)

Schema for defining macros
~~~~~~~~~~~~~~~~~~~~~~~~~~

Macro definitions rely on additional directives that are not normally defined in the schema
the GraphQL compiler uses for querying. We intentionally do not include these directives in
the schema used for querying, since defining macros and writing queries are different modes
of use of the compiler, and we believe that controlling which sets of directives
are available in which mode will minimize the potential for user confusion.

The :code:`get_schema_for_macro_definition()` function is able to transform a querying schema
into one that is suitable for defining macros. Getting such a schema may be useful, for example,
when setting up a GraphQL editor (such as GraphiQL) to create and edit macros.


Macro edges
~~~~~~~~~~~

Macro edges allow users to define new edges that become part of the GraphQL schema, using existing
edges as building blocks. They allow users to define shorthand for common querying operations,
encapsulating uses of existing query functionality (e.g., tags, filters, recursion,
type coercions, etc.) into a virtual edge with a user-specified name that exists only on a specific
GraphQL type (and all its subtypes). Both macro edge definitions and their uses are
fully type-checked, ensuring the soundness of both the macro definition and any queries that use it.

Overview and use of macro edges
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Let us explain the idea of macro edges through a simple example.

Consider the following query, which returns the list of grandchildren of a given animal:

.. code ::

    {
        Animal {
            name @filter(op_name: "=", value: ["$animal_name"])
            out_Animal_ParentOf {
                out_Animal_ParentOf {
                    name @output(out_name: "grandchild_name")
                }
            }
        }
    }

If operations on animals' grandchildren are common in our use case, we may wish that
an edge like :code:`out_Animal_GrandparentOf` had existed and saved us some repetitive typing.

One of our options is to materialize such an edge in the underlying database itself.
However, this causes denormalization of the database -- there are now two places where
an animal's grandchildren are written down -- requiring additional storage space,
and introducing potential for user confusion and data inconsistency between the two representations.

Another option is to introduce a non-materialized view within the database that *makes it appear*
that such an edge exists, and query this view via the GraphQL compiler. While this avoids some
of the drawbacks of the previous approach, not all databases support non-materialized views.
Also, querying users are not always able to add views to the database, and may require additional
permissions on the database system.

Macro edges give us the opportunity to define a new :code:`out_Animal_GrandparentOf` edge without
involving the underlying database systems at all. We simply state that such an edge
is constructed by composing two :code:`out_Animal_ParentOf` edges together:

.. code:: python

    from graphql_compiler.macros import register_macro_edge

    macro_edge_definition = '''{
        Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
            out_Animal_ParentOf {
                out_Animal_ParentOf @macro_edge_target {
                    uuid
                }
            }
        }
    }'''
    macro_edge_args = {}

    register_macro_edge(your_macro_registry_object, macro_edge_definition, macro_edge_args)

Let's dig into the GraphQL macro edge definition one step at a time:

- We know that the new macro edge is being defined on the :code:`Animal` GraphQL type, since that
  is the type where the definition begins.

- The :code:`@macro_edge_definition` directive specifies the name of the new macro edge.

- The newly-defined :code:`out_Animal_GrandparentOf` edge connects :code:`Animal` vertices
  to the vertices reachable after exactly two traversals along :code:`out_Animal_ParentOf` edges;
  this is what the :code:`@macro_edge_target` directive signifies.

- As the :code:`out_Animal_ParentOf` field containing the :code:`@macro_edge_target` directive
  is of type :code:`[Animal]` (we know this from our schema), the compiler will automatically infer
  that the :code:`out_Animal_GrandparentOf` macro edge also points to vertices
  of type :code:`Animal`.

- The :code:`uuid` within the inner :code:`out_Animal_ParentOf` scope is a "pro-forma" field -- it
  is there simply to satisfy the GraphQL parser, since per the GraphQL specification, each pair of
  curly braces must reference at least one field. The named field has no meaning in this definition,
  and the user may choose to use any field that exists within that pair of curly braces.
  The preferred convention for pro-forma fields is to use whichever field represents
  the primary key of the given type in the underlying database.

- This macro edge does not take arguments, so we set the :code:`macro_edge_args` value to an empty
  dictionary. We will cover macro edges with arguments later.

Having defined this macro edge, we are now able to rewrite our original query into a simpler
yet equivalent form:

.. code::

    {
        Animal {
            name @filter(op_name: "=", value: ["$animal_name"])
            out_Animal_GrandparentOf {
                name @output(out_name: "grandchild_name")
            }
        }
    }

We can now observe the process of macro expansion in action:

.. code:: python

    from graphql_compiler.macros import get_schema_with_macros, perform_macro_expansion

    query = '''{
        Animal {
            name @filter(op_name: "=", value: ["$animal_name"])
            out_Animal_GrandparentOf {
                name @output(out_name: "grandchild_name")
            }
        }
    }'''
    args = {
        'animal_name': 'Hedwig',
    }

    schema_with_macros = get_schema_with_macros(macro_registry)
    new_query, new_args = perform_macro_expansion(macro_registry, schema_with_macros, query, args)

    print(new_query)
    # Prints out the following query:
    # {
    #     Animal {
    #         name @filter(op_name: "=", value: ["$animal_name"])
    #         out_Animal_ParentOf {
    #             out_Animal_ParentOf {
    #                 name @output(out_name: "grandchild_name")
    #             }
    #         }
    #     }
    # }

    print(new_args)
    # Prints out the following arguments:
    # {'animal_name': 'Hedwig'}

Advanced macro edges use cases
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When defining macro edges, one may freely use other compiler query functionality,
such as :code:`@recurse`, :code:`@filter`, :code:`@tag`, and so on. Here is a more complex
macro edge definition that relies on such more advanced features to define an edge
that connects :code:`Animal` vertices to their siblings who are both older and have a
higher net worth:

.. code:: python

    from graphql_compiler.macros import register_macro_edge

    macro_edge_definition = '''
    {
        Animal @macro_edge_definition(name: "out_Animal_RicherOlderSiblings") {
            net_worth @tag(tag_name: "self_net_worth")
            out_Animal_BornAt {
                event_date @tag(tag_name: "self_birthday")
            }
            in_Animal_ParentOf {
                out_Animal_ParentOf @macro_edge_target {
                    net_worth @filter(op_name: ">", value: ["%self_net_worth"])
                    out_Animal_BornAt {
                        event_date @filter(op_name: "<", value: ["%self_birthday"])
                    }
                }
            }
        }
    }'''
    macro_edge_args = {}

    register_macro_edge(your_macro_registry_object, macro_edge_definition, macro_edge_args)

Similarly, macro edge definitions are also able to use runtime parameters in
their :code:`@filter` directives, by simply including the runtime parameters needed by
the macro edge in the call to :code:`register_macro_edge()`. The following example defines a
macro edge connecting :code:`Animal` vertices to their grandchildren that go by the name of "Nate".

.. code:: python

    macro_edge_definition = '''
    {
        Animal @macro_edge_definition(name: "out_Animal_GrandchildrenCalledNate") {
            out_Animal_ParentOf {
                out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$nate_name"])
                                    @macro_edge_target {
                    uuid
                }
            }
        }
    }'''
    macro_edge_args = {
        'nate_name': 'Nate',
    }

    register_macro_edge(your_macro_registry_object, macro_edge_definition, macro_edge_args)

When a GraphQL query uses this macro edge, the :code:`perform_macro_expansion()` function will
automatically ensure that the macro edge's arguments become part of the expanded query's arguments:

.. code:: python

    query = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_GrandchildrenCalledNate {
                uuid @output(out_name: "grandchild_id")
            }
        }
    }'''
    args = {}
    schema_with_macros = get_schema_with_macros(macro_registry)
    expanded_query, new_args = perform_macro_expansion(
          macro_registry, schema_with_macros, query, args)

    print(expanded_query)
    # Prints out the following query:
    # {
    #     Animal {
    #         name @output(out_name: "animal_name")
    #         out_Animal_ParentOf {
    #             out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$nate_name"]) {
    #                 uuid @output(out_name: "grandchild_id")
    #             }
    #         }
    #     }
    # }

    print(new_args)
    # Prints out the following arguments:
    # {'nate_name': 'Nate'}

Constraints and rules for macro edge definitions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- Macro edge definitions cannot use other macros as part of their definition.
- A macro definition contains exactly one :code:`@macro_edge_definition` and
  one :code:`@macro_edge_target` directive. These directives can only be used
  within macro edge definitions.
- The :code:`@macro_edge_target` cannot be at or within a scope
  marked :code:`@fold` or :code:`@optional`.
- The scope marked :code:`@macro_edge_target` cannot immediately contain a type coercion.
  Instead, place the :code:`@macro_edge_target` directive at the type coercion itself instead of
  on its enclosing scope.
- Macros edge definitions cannot contain uses of :code:`@output` or :code:`@output_source`.


Constraints and rules for macro edge usage
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- The :code:`@optional` and :code:`@recurse` directives cannot be used on macro edges.
- During the process of macro edge expansion, any directives applied on the vertex field belonging
  to the macro edge are applied to the vertex field marked with :code:`@macro_edge_target` in the
  macro edge's definition.

In the future, we hope to add support for using :code:`@optional` on macro edges. We have opened
a `GitHub issue <https://github.com/kensho-technologies/graphql-compiler/issues/586>`_ to track
this effort, and we welcome contributions!


Miscellaneous
-------------

Pretty-Printing GraphQL Queries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To pretty-print GraphQL queries, use the included pretty-printer:

::

    python -m graphql_compiler.tool <input_file.graphql >output_file.graphql

It's modeled after Python's :code:`json.tool`, reading from stdin and
writing to stdout.

Expanding :code:`@optional` vertex fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Including an optional statement in GraphQL has no performance issues on
its own, but if you continue expanding vertex fields within an optional
scope, there may be significant performance implications.

Going forward, we will refer to two different kinds of :code:`@optional`
directives.

-  A *"simple"* optional is a vertex with an :code:`@optional` directive
   that does not expand any vertex fields within it. For example:

   .. code::

       {
           Animal {
               name @output(out_name: "name")
               in_Animal_ParentOf @optional {
                   name @output(out_name: "parent_name")
               }
           }
       }

   OrientDB :code:`MATCH` currently allows the last step in any traversal to
   be optional. Therefore, the equivalent :code:`MATCH` traversal for the
   above :code:`GraphQL` is as follows:

   ::

       SELECT
       Animal___1.name as `name`,
       Animal__in_Animal_ParentOf___1.name as `parent_name`
       FROM (
       MATCH {
           class: Animal,
           as: Animal___1
       }.in('Animal_ParentOf') {
           as: Animal__in_Animal_ParentOf___1
       }
       RETURN $matches
       )

-  A *"compound"* optional is a vertex with an :code:`@optional` directive
   which does expand vertex fields within it. For example:

   .. code::

       {
           Animal {
               name @output(out_name: "name")
               in_Animal_ParentOf @optional {
                   name @output(out_name: "parent_name")
                   in_Animal_ParentOf {
                       name @output(out_name: "grandparent_name")
                   }
               }
           }
       }

   Currently, this cannot represented by a simple :code:`MATCH` query.
   Specifically, the following is *NOT* a valid :code:`MATCH` statement,
   because the optional traversal follows another edge:

   ::

       -- NOT A VALID QUERY
       SELECT
       Animal___1.name as `name`,
       Animal__in_Animal_ParentOf___1.name as `parent_name`
       FROM (
       MATCH {
           class: Animal,
           as: Animal___1
       }.in('Animal_ParentOf') {
           optional: true,
           as: Animal__in_Animal_ParentOf___1
       }.in('Animal_ParentOf') {
           as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
       }
       RETURN $matches
       )

Instead, we represent a *compound* optional by taking an union
(:code:`UNIONALL`) of two distinct :code:`MATCH` queries. For instance, the
:code:`GraphQL` query above can be represented as follows:

::

    SELECT EXPAND($final_match)
    LET
        $match1 = (
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {
                    class: Animal,
                    as: Animal___1,
                    where: (
                        (in_Animal_ParentOf IS null)
                        OR
                        (in_Animal_ParentOf.size() = 0)
                    ),
                }
            )
        ),
        $match2 = (
            SELECT
                Animal___1.name AS `name`,
                Animal__in_Animal_ParentOf___1.name AS `parent_name`
            FROM (
                MATCH {
                    class: Animal,
                    as: Animal___1
                }.in('Animal_ParentOf') {
                    as: Animal__in_Animal_ParentOf___1
                }.in('Animal_ParentOf') {
                    as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
                }
            )
        ),
        $final_match = UNIONALL($match1, $match2)

In the first case where the optional edge is not followed, we have to
explicitly filter out all vertices where the edge *could have been
followed*. This is to eliminate duplicates between the two :code:`MATCH`
selections.

The previous example is not *exactly* how we implement *compound*
optionals (we also have :code:`SELECT` statements within :code:`$match1` and
:code:`$match2`), but it illustrates the the general idea.

Performance Penalty
^^^^^^^^^^^^^^^^^^^

If we have many *compound* optionals in the given :code:`GraphQL`, the above
procedure results in the union of a large number of :code:`MATCH` queries.
Specifically, for :code:`n` compound optionals, we generate 2n different
:code:`MATCH` queries. For each of the 2n subsets :code:`S` of the :code:`n`
optional edges:

- We remove the :code:`@optional` restriction for each traversal in :code:`S`.
- For each traverse :code:`t` in the complement of :code:`S`, we entirely discard :code:`t` along
  with all the vertices and directives within it, and we add a filter on the previous traverse to
  ensure that the edge corresponding to :code:`t` does not exist.

Therefore, we get a performance penalty that grows exponentially with
the number of *compound* optional edges. This is important to keep in
mind when writing queries with many optional directives.

If some of those *compound* optionals contain :code:`@optional` vertex
fields of their own, the performance penalty grows since we have to
account for all possible subsets of :code:`@optional` statements that can be
satisfied simultaneously.

Optional :code:`type_equivalence_hints` parameter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This compilation parameter is a workaround for the limitations of the
GraphQL and Gremlin type systems:

- GraphQL does not allow :code:`type` to inherit from another :code:`type`, only to implement an
  :code:`interface`.
- Gremlin does not have first-class support for inheritance at all.

Assume the following GraphQL schema:

.. code::

    type Animal {
        name: String
    }

    type Cat {
        name: String
    }

    type Dog {
        name: String
    }

    union AnimalCatDog = Animal | Cat | Dog

    type Foo {
        adjacent_animal: AnimalCatDog
    }

An appropriate :code:`type_equivalence_hints` value here would be
:code:`{ Animal: AnimalCatDog }`. This lets the compiler know that the
:code:`AnimalCatDog` union type is implicitly equivalent to the :code:`Animal`
type, as there are no other types that inherit from :code:`Animal` in the
database schema. This allows the compiler to perform accurate type
coercions in Gremlin, as well as optimize away type coercions across
edges of union type if the coercion is coercing to the union's
equivalent type.

Setting :code:`type_equivalence_hints = { Animal: AnimalCatDog }` during
compilation would enable the use of a :code:`@fold` on the
:code:`adjacent_animal` vertex field of :code:`Foo`:

.. code::

    {
        Foo {
            adjacent_animal @fold {
                ... on Animal {
                    name @output(out_name: "name")
                }
            }
        }
    }

SchemaGraph
~~~~~~~~~~~

When building a GraphQL schema from the database metadata, we first
build a :code:`SchemaGraph` from the metadata and then, from the
:code:`SchemaGraph`, build the GraphQL schema. The :code:`SchemaGraph` is also a
representation of the underlying database schema, but it has three main
advantages that make it a more powerful schema introspection tool:

1. It's able to store and expose a schema's index information. The interface for accessing index
   information is provisional though and might change in the near future.
2. Its classes are  allowed to inherit from non-abstract classes.
3. It exposes many utility functions, such as :code:`get_subclass_set`, that make it easier to
   explore the schema.

See below for a mock example of how to build and use the
:code:`SchemaGraph`:

.. code:: python

    from graphql_compiler.schema_generation.orientdb.schema_graph_builder import (
        get_orientdb_schema_graph
    )
    from graphql_compiler.schema_generation.orientdb.utils import (
        ORIENTDB_INDEX_RECORDS_QUERY, ORIENTDB_SCHEMA_RECORDS_QUERY
    )

    # Get schema metadata from hypothetical Animals database.
    client = your_function_that_returns_an_orientdb_client()
    schema_records = client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
    schema_data = [record.oRecordData for record in schema_records]

    # Get index data.
    index_records = client.command(ORIENTDB_INDEX_RECORDS_QUERY)
    index_query_data = [record.oRecordData for record in index_records]

    # Build SchemaGraph.
    schema_graph = get_orientdb_schema_graph(schema_data, index_query_data)

    # Get all the subclasses of a class.
    print(schema_graph.get_subclass_set('Animal'))
    # {'Animal', 'Dog'}

    # Get all the outgoing edge classes of a vertex class.
    print(schema_graph.get_vertex_schema_element_or_raise('Animal').out_connections)
    # {'Animal_Eats', 'Animal_FedAt', 'Animal_LivesIn'}

    # Get the vertex classes allowed as the destination vertex of an edge class.
    print(schema_graph.get_edge_schema_element_or_raise('Animal_Eats').out_connections)
    # {'Fruit', 'Food'}

    # Get the superclass of all classes allowed as the destination vertex of an edge class.
    print(schema_graph.get_edge_schema_element_or_raise('Animal_Eats').base_out_connection)
    # Food

    # Get the unique indexes defined on a class.
    print(schema_graph.get_unique_indexes_for_class('Animal'))
    # [IndexDefinition(name='uuid', 'base_classname'='Animal', fields={'uuid'}, unique=True, ordered=False, ignore_nulls=False)]

In the future, we plan to add :code:`SchemaGraph` generation from SQLAlchemy
metadata. We also plan to add a mechanism where one can query a
:code:`SchemaGraph` using GraphQL queries.

Cypher query parameters
~~~~~~~~~~~~~~~~~~~~~~~

RedisGraph `doesn't support query
parameters <https://github.com/RedisGraph/RedisGraph/issues/544#issuecomment-507963576>`__,
so we perform manual parameter interpolation in the
:code:`graphql_to_redisgraph_cypher` function. However, for Neo4j, we can
use Neo4j's client to do parameter interpolation on its own so that we
don't reinvent the wheel.

The function :code:`insert_arguments_into_query` does so based on the query
language, which isn't fine-grained enough here-- for Cypher backends, we
only want to insert parameters if the backend is RedisGraph, but not if
it's Neo4j.

Instead, the correct approach for Neo4j Cypher is as follows, given a
Neo4j Python client called :code:`neo4j_client`:

.. code:: python

    compilation_result = compile_graphql_to_cypher(
        schema, graphql_query, type_equivalence_hints=type_equivalence_hints)
    with neo4j_client.driver.session() as session:
        result = session.run(compilation_result.query, parameters)

Amending Parsed Custom Scalar Types
-----------------------------------

Information about the description, serialization and parsing of custom
scalar type objects is lost when a GraphQL schema is parsed from a
string. This causes issues when working with custom scalar type objects.
In order to avoid these issues, one can use the code snippet below to
amend the definitions of the custom scalar types used by the compiler.

.. code:: python

    from graphql_compiler.schema import CUSTOM_SCALAR_TYPES
    from graphql_compiler.schema_generation.utils import amend_custom_scalar_types

    amend_custom_scalar_types(your_schema, CUSTOM_SCALAR_TYPES)

FAQ
---

**Q: Do you really use GraphQL, or do you just use GraphQL-like
syntax?**

A: We really use GraphQL. Any query that the compiler will accept is
entirely valid GraphQL, and we actually use the Python port of the
GraphQL core library for parsing and type checking. However, since the
database queries produced by compiling GraphQL are subject to the
limitations of the database system they run on, our execution model is
somewhat different compared to the one described in the standard GraphQL
specification. See the `Execution model <#execution-model>`__ section
for more details.

**Q: Does this project come with a GraphQL server implementation?**

A: No -- there are many existing frameworks for running a web server. We
simply built a tool that takes GraphQL query strings (and their
parameters) and returns a query string you can use with your database.
The compiler does not execute the query string against the database, nor
does it deserialize the results. Therefore, it is agnostic to the choice
of server framework and database client library used.

**Q: Do you plan to support other databases / more GraphQL features in
the future?**

A: We'd love to, and we could really use your help! Please consider
contributing to this project by opening issues, opening pull requests,
or participating in discussions.

**Q: I think I found a bug, what do I do?**

A: Please check if an issue has already been created for the bug, and
open a new one if not. Make sure to describe the bug in as much detail
as possible, including any stack traces or error messages you may have
seen, which database you're using, and what query you compiled.

**Q: I think I found a security vulnerability, what do I do?**

A: Please reach out to us at graphql-compiler-maintainer@kensho.com so
we can triage the issue and take appropriate action.

License
-------

Licensed under the Apache 2.0 License. Unless required by applicable law
or agreed to in writing, software distributed under the License is
distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied. See the License for the specific
language governing permissions and limitations under the License.

Copyright 2017-present Kensho Technologies, LLC. The present date is
determined by the timestamp of the most recent commit in the repository.

.. |Build Status| image:: https://travis-ci.org/kensho-technologies/graphql-compiler.svg?branch=master
   :target: https://travis-ci.org/kensho-technologies/graphql-compiler
.. |Coverage Status| image:: https://coveralls.io/repos/github/kensho-technologies/graphql-compiler/badge.svg?branch=master
   :target: https://coveralls.io/github/kensho-technologies/graphql-compiler?branch=master
.. |License| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
   :target: https://opensource.org/licenses/Apache-2.0
.. |PyPI Python| image:: https://img.shields.io/pypi/pyversions/graphql-compiler.svg
   :target: https://pypi.python.org/pypi/graphql-compiler
.. |PyPI Version| image:: https://img.shields.io/pypi/v/graphql-compiler.svg
   :target: https://pypi.python.org/pypi/graphql-compiler
.. |PyPI Status| image:: https://img.shields.io/pypi/status/graphql-compiler.svg
   :target: https://pypi.python.org/pypi/graphql-compiler
.. |PyPI Wheel| image:: https://img.shields.io/pypi/wheel/graphql-compiler.svg
   :target: https://pypi.python.org/pypi/graphql-compiler
