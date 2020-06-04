Query Directives
================

@optional
---------

Without this directive, when a query includes a vertex field, any
results matching that query must be able to produce a value for that
vertex field. Applied to a vertex field, this directive prevents result
sets that are unable to produce a value for that field from being
discarded, and allowed to continue processing the remainder of the
query.

Example Use
~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~

-  :code:`@optional` can only be applied to vertex fields, except the root
   vertex field.
-  It is allowed to expand vertex fields within an :code:`@optional` scope.
   However, doing so is currently associated with a performance penalty
   in :code:`MATCH`.
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
-------

Denotes that the value of a property field should be included in the
output. Its :code:`out_name` argument specifies the name of the column in
which the output value should be returned.

Example Use
~~~~~~~~~~~

.. code::

    {
        Animal {
            name @output(out_name: "animal_name")
        }
    }

This query returns the name of each :code:`Animal` in the graph, in a column
named :code:`animal_name`.

Constraints and Rules
~~~~~~~~~~~~~~~~~~~~~

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
-----

Applying :code:`@fold` on a scope "folds" all outputs from within that
scope: rather than appearing on separate rows in the query result, the
folded outputs are coalesced into parallel lists starting at the scope
marked :code:`@fold`.

It is also possible to output or apply filters to the number of results
captured in a :code:`@fold`. The :code:`_x_count` meta field that is available
within :code:`@fold` scopes represents the number of elements in the fold,
and may be filtered or output as usual. As :code:`_x_count` represents a
count of elements, marking it :code:`@output` will produce an integer value.
See the :ref:`\_x\_count <x_count>` section for more details.

Example Use
~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~

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
   :code:`@fold` scope is actually a no-op, it may optimize it away.

Example
~~~~~~~

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
----

The :code:`@tag` directive enables filtering based on values encountered
elsewhere in the same query. Applied on a property field, it assigns a
name to the value of that property field, allowing that value to then be
used as part of a :code:`@filter` directive.

To supply a tagged value to a :code:`@filter` directive, place the tag name
(prefixed with a :code:`%` symbol) in the :code:`@filter`'s :code:`value` array. See
:ref:`Passing parameters <passing_parameters>` for more details.

Example Use
~~~~~~~~~~~

.. code::

    {
        Animal {
            limbs @tag(tag_name: "parent_limbs")
            out_Animal_ParentOf {
                limbs @filter(op_name: "<", value: ["%parent_limbs"])
                name @output(out_name: "child_name")
            }
        }
    }

Each result returned by this query contains the name of an :code:`Animal` who is a
child of another animal and has fewer limbs than its parent.

Constraints and Rules
~~~~~~~~~~~~~~~~~~~~~

-  :code:`@tag` can only be applied to property fields.
-  The value provided for :code:`tag_name` may only consist of upper or
   lower case letters (:code:`A-Z`, :code:`a-z`), or underscores (:code:`_`).
-  For any given query, all :code:`tag_name` values must be unique.
-  Cannot be applied to property fields within a scope marked :code:`@fold`.
-  Using a :code:`@tag` and a :code:`@filter` that references the tag within the
   same vertex is allowed, so long as the two do not appear on the exact
   same property field.

@filter
-------

Allows filtering of the data to be returned, based on any of a set of
filtering operations. Conceptually, it is the GraphQL equivalent of the
SQL :code:`WHERE` keyword.

See `Supported filtering operations <supported_filtering_operations>`__
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

.. _passing_parameters:

Passing Parameters
~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~

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
--------

Applied to a vertex field, specifies that the edge connecting that
vertex field to the current vertex should be visited repeatedly, up to
:code:`depth` times. The recursion always starts at :code:`depth = 0`, i.e. the
current vertex -- see the below sections for a more thorough
explanation.

Example Use
~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~

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

.. _output_source:

@output_source
--------------

:code:`@output_source` is a directive that can be used on the last vertex field in a query to
reverse the order in which vertex fields are visited. Currently, its primary function is to help
deal with the following known issue that occurs when compiling to :code:`gremlin`. When vertex
fields are visited in a certain order in a GraphQL query, the compiler returns a `gremlin` that
does not return the complete set of results promised by the query semantics. See the example use
section for more details.

Example use
~~~~~~~~~~~

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
produce. (:code:`MATCH` is our name for the SQL dialect that OrientDB uses). However, the
:code:`gremlin` compilation target does not guarantee a complete result list. Querying the
database using a query string generated by the :code:`gremlin` compilation target will produce
only a partial result list resembling the following:

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


Constraints and Rules
^^^^^^^^^^^^^^^^^^^^^

-  May exist at most once in any given GraphQL query.
-  Can exist only on a vertex field, and only on the last vertex field
   used in the query.
-  Cannot be used within a scope marked :code:`@optional` or :code:`@fold`.

.. _supported_filtering_operations:

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
~~~~~~~~~~~~

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
~~~~~~~~~~

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
