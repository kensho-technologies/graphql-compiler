# graphql-compiler

[![Build Status](https://travis-ci.org/kensho-technologies/graphql-compiler.svg?branch=master)](https://travis-ci.org/kensho-technologies/graphql-compiler)
[![Coverage Status](https://coveralls.io/repos/github/kensho-technologies/graphql-compiler/badge.svg?branch=master)](https://coveralls.io/github/kensho-technologies/graphql-compiler?branch=master)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI Python](https://img.shields.io/pypi/pyversions/graphql-compiler.svg)](https://pypi.python.org/pypi/graphql-compiler)
[![PyPI Version](https://img.shields.io/pypi/v/graphql-compiler.svg)](https://pypi.python.org/pypi/graphql-compiler)
[![PyPI Status](https://img.shields.io/pypi/status/graphql-compiler.svg)](https://pypi.python.org/pypi/graphql-compiler)
[![PyPI Wheel](https://img.shields.io/pypi/wheel/graphql-compiler.svg)](https://pypi.python.org/pypi/graphql-compiler)

Turn complex GraphQL queries into optimized database queries.

```
pip install graphql-compiler
```

For a more detailed overview and getting started guide, please see
[our blog post](https://blog.kensho.com/compiled-graphql-as-a-database-query-language-72e106844282).

To pretty-print GraphQL queries, use the included pretty-printer:
```
python -m graphql_compiler.tool <input_file.graphql >output_file.graphql
```
It's modeled after Python's `json.tool`, reading from stdin and writing to stdout.

## Table of contents
  * [FAQ](#faq)
  * [Definitions](#definitions)
  * [Directives](#directives)
     * [@optional](#optional)
     * [@output](#output)
     * [@fold](#fold)
     * [@tag](#tag)
     * [@filter](#filter)
     * [@recurse](#recurse)
     * [@output_source](#output_source)
  * [Supported filtering operations](#supported-filtering-operations)
     * [Comparison operators](#comparison-operators)
     * [name_or_alias](#name_or_alias)
     * [between](#between)
     * [in_collection](#in_collection)
     * [has_substring](#has_substring)
     * [contains](#contains)
     * [has_edge_degree](#has_edge_degree)
  * [Type coercions](#type-coercions)
  * [Meta fields](#meta-fields)
  * [The GraphQL schema](#the-graphql-schema)
  * [Execution model](#execution-model)
  * [Miscellaneous](#miscellaneous)
     * [Expanding `@optional` vertex fields](#expanding-optional-vertex-fields)
     * [Optional `type_equivalence_hints` compilation parameter](#optional-type_equivalence_hints-parameter)
  * [License](#license)

## FAQ

**Q: Does the compiler support all GraphQL language features?**

A: No. We prioritized and implemented a subset of all functionality supported by the
   GraphQL language. We hope to add more functionality over time.

**Q: Do you really use GraphQL, or do you just use GraphQL-like syntax?**

A: We really use GraphQL. Any query that the compiler will accept is entirely valid GraphQL,
   and we actually use the Python port of the GraphQL core library for parsing and type checking.
   However, since the database queries produced by compiling GraphQL are subject to the limitations
   of the database system they run on, our execution model is somewhat different compared to
   the one described in the standard GraphQL specification. See the
   [Execution model](#execution-model) section for more details.

**Q: Does this project come with a GraphQL server implementation?**

A: No -- there are many existing frameworks for running a web server. We simply built a tool
   that takes GraphQL query strings (and their parameters) and returns a query string you can
   use with your database. The compiler does not execute the query string against the database,
   nor does it deserialize the results. Therefore, it is agnostic to the choice of
   server framework and database client library used.

**Q: What databases and query languages does the compiler support?**

A: We currently support a single database, OrientDB version 2.2.28+, and two query languages
   that OrientDB supports: the OrientDB dialect of `gremlin`, and OrientDB's own custom SQL-like
   query language that we refer to as `MATCH`, after the name of its graph traversal operator.
   With OrientDB, `MATCH` should be the preferred choice for most users, since it tends to run
   faster than `gremlin`, and has other desirable properties. See the
   [Execution model](#execution-model) section for more details.

**Q: Do you plan to support other databases / more GraphQL features in the future?**

A: We'd love to, and we could really use your help! Please consider contributing to this project
   by opening issues, opening pull requests, or participating in discussions.

**Q: I think I found a bug, what do I do?**

A: Please check if an issue has already been created for the bug, and open a new one if not.
   Make sure to describe the bug in as much detail as possible, including any stack traces or
   error messages you may have seen, which database you're using, and what query you compiled.

**Q: I think I found a security vulnerability, what do I do?**

A: Please reach out to us at
[graphql-compiler-maintainer@kensho.com](mailto:graphql-compiler-maintainer@kensho.com)
so we can triage the issue and take appropriate action.

## Definitions

- **Vertex field**: A field corresponding to a vertex in the graph. In the below example, `Animal`
  and `out_Entity_Related` are vertex fields. The `Animal` field is the field at which querying
  starts, and is therefore the **root vertex field**. In any scope, fields with the prefix `out_`
  denote vertex fields connected by an outbound edge, whereas ones with the prefix `in_` denote
  vertex fields connected by an inbound edge.
```
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
```
- **Property field**: A field corresponding to a property of a vertex in the graph. In the
  above example, the `name` and `description` fields are property fields. In any given scope,
  **property fields must appear before vertex fields**.
- **Result set**: An assignment of vertices in the graph to scopes (locations) in the query.
  As the database processes the query, new result sets may be created (e.g. when traversing edges),
  and result sets may be discarded when they do not satisfy filters or type coercions. After all
  parts of the query are processed by the database, all remaining result sets are used to form the
  query result, by taking their values at all properties marked for output.
- **Scope**: The part of a query between any pair of curly braces. The compiler infers the type
  of each scope. For example, in the above query, the scope beginning with `Animal {` is of
  type `Animal`, the one beginning with `out_Entity_Related {` is of type `Entity`, and the one
  beginning with `... on Species {` is of type `Species`.
- **Type coercion**: An operation that produces a new scope of narrower type than the
  scope in which it exists. Any result sets that cannot satisfy the narrower type are filtered out
  and not returned. In the above query, `... on Species` is a type coercion which takes
  its enclosing scope of type `Entity`, and coerces it into a narrower scope of
  type `Species`. This is possible since `Entity` is an interface, and `Species` is a type
  that implements the `Entity` interface.

## Directives

### @optional

Without this directive, when a query includes a vertex field, any results matching that query
must be able to produce a value for that vertex field. Applied to a vertex field,
this directive prevents result sets that are unable to produce a value for that field from
being discarded, and allowed to continue processing the remainder of the query.

#### Example Use
```
{
    Animal {
        name @output(out_name: "name")
        out_Animal_ParentOf @optional {
            name @output(out_name: "child_name")
        }
    }
}
```
For each `Animal`:
- if it is a parent of another animal, at least one row containing the
  parent and child animal's names, in the `name` and `child_name` columns respectively;
- if it is not a parent of another animal, a row with its name in the `name` column,
  and a `null` value in the `child_name` column.

#### Constraints and Rules
- `@optional` can only be applied to vertex fields, except the root vertex field.
- It is allowed to expand vertex fields within an `@optional` scope.
  However, doing so is currently associated with a performance penalty in `MATCH`.
  For more detail, see: [Expanding `@optional` vertex fields](#expanding-optional-vertex-fields).
- `@recurse`, `@fold`, or `@output_source` may not be used at the same vertex field as `@optional`.
- `@optional`, `@output_source` and `@fold` may not be used anywhere within a scope
  marked `@optional`.

If a given result set is unable to produce a value for a vertex field marked `@optional`,
any fields marked `@output` within that vertex field return the `null` value.

When filtering (via `@filter`) or type coercion (via e.g. `... on Animal`) are applied
at or within a vertex field marked `@optional`, the `@optional` is given precedence:
- If a given result set cannot produce a value for the optional vertex field, it is preserved:
the `@optional` directive is applied first, and no filtering or type coercion can happen.
- If a given result set is able to produce a value for the optional vertex field,
the `@optional` does not apply, and that value is then checked against the filtering or type
coercion. These subsequent operations may then cause the result set to be discarded if it does
not match.

### @output

Denotes that the value of a property field should be included in the output.
Its `out_name` argument specifies the name of the column in which the
output value should be returned.

#### Example Use
```
{
    Animal {
        name @output(out_name: "animal_name")
    }
}
```
This query returns the name of each `Animal` in the graph, in a column named `animal_name`.

#### Constraints and Rules
- `@output` can only be applied to property fields.
- The value provided for `out_name` may only consist of upper or lower case letters
  (`A-Z`, `a-z`), or underscores (`_`).
- For any given query, all `out_name` values must be unique. In other words, output columns must
  have unique names.

If the property field marked `@output` exists within a scope marked `@optional`, result sets that
are unable to assign a value to the optional scope return the value `null` as the output
of that property field.

### @fold

Applying `@fold` on a scope "folds" all outputs from within that scope: rather than appearing
on separate rows in the query result, the folded outputs are coalesced into lists starting
at the scope marked `@fold`.

#### Example Use
```
{
    Animal {
        name @output(out_name: "animal_name")
        out_Animal_ParentOf @fold {
            name @output(out_name: "child_names")
        }
    }
}
```
Each returned row has two columns: `animal_name` with the name of each `Animal` in the graph,
and `child_names` with a list of the names of all children of the `Animal` named `animal_name`.
If a given `Animal` has no children, its `child_names` list is empty.

#### Constraints and Rules
- `@fold` can only be applied to vertex fields, except the root vertex field.
- May not exist at the same vertex field as `@recurse`, `@optional`, or `@output_source`.
- Any scope that is either marked with `@fold` or is nested within a `@fold` marked scope,
  may expand at most one vertex field.
- There must be at least one `@output` field within a `@fold` scope.
- All `@output` fields within a `@fold` traversal must be present at the innermost scope.
  It is invalid to expand vertex fields within a `@fold` after encountering an `@output` directive.
- `@tag`, `@recurse`, `@optional`, `@output_source` and `@fold` may not be used anywhere
  within a scope marked `@fold`.
- Use of type coercions or `@filter` at or within the vertex field marked `@fold` is allowed.
  Only data that satisfies the given type coercions and filters is returned by the `@fold`.
- If the compiler is able to prove that the type coercion in the `@fold` scope is actually a no-op,
  it may optimize it away. See the
  [Optional `type_equivalence_hints` compilation parameter](#optional-type_equivalence_hints-parameter)
  section for more details.

#### Example
The following GraphQL is *not allowed* and will produce a `GraphQLCompilationError`.
This query is *invalid* for two separate reasons:
- It expands vertex fields after an `@output` directive (outputting `animal_name`)
- The `in_Animal_ParentOf` scope, which is within a scope marked `@fold`,
  expands two vertex fields instead of at most one.
```
{
    Animal {
        out_Animal_ParentOf @fold {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf {
                out_Animal_OfSpecies {
                    uuid @output(out_name: "species_id")
                }
                out_Animal_RelatedTo {
                    name @output(out_name: "relative_name")
                }
            }
        }
    }
}
```
The following is a valid use of `@fold`:
```
{
    Animal {
        out_Animal_ParentOf @fold {
            in_Animal_ParentOf {
                in_Animal_ParentOf {
                    out_Animal_RelatedTo {
                        name @output(out_name: "final_name")
                    }
                }
            }
        }
    }
}
```

### @tag

The `@tag` directive enables filtering based on values encountered elsewhere in the same query.
Applied on a property field, it assigns a name to the value of that property field, allowing that
value to then be used as part of a `@filter` directive.

To supply a tagged value to a `@filter` directive, place the tag name (prefixed with a `%` symbol)
in the `@filter`'s `value` array. See [Passing parameters](#passing-parameters)
for more details.

#### Example Use
```
{
    Animal {
        name @tag(tag_name: "parent_name")
        out_Animal_ParentOf {
            name @filter(op_name: "<", value: ["%parent_name"])
                 @output(out_name: "child_name")
        }
    }
}
```
Each row returned by this query contains, in the `child_name` column, the name of an `Animal`
that is the child of another `Animal`, and has a name that is lexicographically smaller than
the name of its parent.

#### Constraints and Rules
- `@tag` can only be applied to property fields.
- The value provided for `tag_name` may only consist of upper or lower case letters
  (`A-Z`, `a-z`), or underscores (`_`).
- For any given query, all `tag_name` values must be unique.
- Cannot be applied to property fields within a scope marked `@fold`.

### @filter

Allows filtering of the data to be returned, based on any of a set of filtering operations.
Conceptually, it is the GraphQL equivalent of the SQL `WHERE` keyword.

See [Supported filtering operations](#supported-filtering-operations)
for details on the various types of filtering that the compiler currently supports.
These operations are currently hardcoded in the compiler; in the future,
we may enable the addition of custom filtering operations via compiler plugins.

Multiple `@filter` directives may be applied to the same field at once. Conceptually,
it is as if the different `@filter` directives were joined by SQL `AND` keywords.

#### Passing Parameters

The `@filter` directive accepts two types of parameters: runtime parameters and tagged parameters.

**Runtime parameters** are represented with a `$` prefix (e.g. `$foo`), and denote parameters
whose values will be known at runtime. The compiler will compile the GraphQL query leaving a
spot for the value to fill at runtime. After compilation, the user will have to supply values for
all runtime parameters, and their values will be inserted into the final query before it can be
executed against the database.

Consider the following query:
```
{
    Animal {
        name @output(out_name: "animal_name")
        color @filter(op_name: "=", value: ["$animal_color"])
    }
}
```
It returns one row for every `Animal` that has a color equal to `$animal_color`,
containing the animal's name in a column named `animal_name`. The parameter `$animal_color` is
a runtime parameter -- the user must pass in a value (e.g. `{"$animal_color": "blue"}`) that
will be inserted into the query before querying the database.

**Tagged parameters** are represented with a `%` prefix (e.g. `%foo`) and denote parameters
whose values are derived from a property field encountered elsewhere in the query.
If the user marks a property field with a `@tag` directive and a suitable name,
that value becomes available to use as a tagged parameter in all subsequent `@filter` directives.

Consider the following query:
```
{
    Animal {
        name @tag(out_name: "parent_name")
        out_Animal_ParentOf {
            name @filter(op_name: "has_substring", value: ["%parent_name"])
                 @output(out_name: "child_name")
        }
    }
}
```
It returns the names of animals that contain their parent's name as a substring of their own.
The database captures the value of the parent animal's name as the `parent_name` tag, and this
value is then used as the `%parent_name` tagged parameter in the child animal's `@filter`.

We considered and **rejected** the idea of allowing literal values (e.g. `123`)
as `@filter` parameters, for several reasons:
- The GraphQL type of the `@filter` directive's `value` field cannot reasonably encompass
  all the different types of arguments that people might supply. Even counting scalar types only,
  there's already `ID, Int, Float, Boolean, String, Date, DateTime...` -- way too many to include.
- Literal values would be used when the parameter's value is known to be fixed. We can just as
  easily accomplish the same thing by using a runtime parameter with a fixed value. That approach
  has the added benefit of potentially reducing the number of different queries that have to be
  compiled: two queries with different literal values would have to be compiled twice, whereas
  using two different sets of runtime arguments only requires the compilation of one query.
- We were concerned about the potential for accidental misuse of literal values. SQL systems have
  supported stored procedures and parameterized queries for decades, and yet ad-hoc SQL query
  construction via simple string interpolation is still a serious problem and is the source of
  many SQL injection vulnerabilities. We felt that disallowing literal values in the query will
  drastically reduce both the use and the risks of unsafe string interpolation,
  at an acceptable cost.

#### Constraints and Rules
- The value provided for `op_name` may only consist of upper or lower case letters
  (`A-Z`, `a-z`), or underscores (`_`).
- Values provided in the `value` list must start with either `$`
  (denoting a runtime parameter) or `%` (denoting a tagged parameter),
  followed by exclusively upper or lower case letters (`A-Z`, `a-z`) or underscores (`_`).
- The `@tag` directives corresponding to any tagged parameters in a given `@filter` query
  must be applied to fields that appear strictly before the field with the `@filter` directive.
- "Can't compare apples and oranges" -- the GraphQL type of the parameters supplied to the `@filter`
  must match the GraphQL types the compiler infers based on the field the `@filter` is applied to.
- If the `@tag` corresponding to a tagged parameter originates from within a vertex field
  marked `@optional`, the emitted code for the `@filter` checks if the `@optional` field was
  assigned a value. If no value was assigned to the `@optional` field, comparisons against the
  tagged parameter from within that field return `True`.
  - For example, assuming `%from_optional` originates from an `@optional` scope, when no value is
    assigned to the `@optional` field:
    - using `@filter(op_name: "=", value: ["%from_optional"])` is equivalent to not
      having the filter at all;
    - using `@filter(op_name: "between", value: ["$lower", "%from_optional"])` is equivalent to
      `@filter(op_name: ">=", value: ["$lower"])`.

### @recurse

Applied to a vertex field, specifies that the edge connecting that vertex field to the current
vertex should be visited repeatedly, up to `depth` times. The recursion always starts
at `depth = 0`, i.e. the current vertex -- see the below sections for a more thorough explanation.

#### Example Use
Say the user wants to fetch the names of the children and grandchildren of each `Animal`.
That could be accomplished by running the following two queries and concatenating their results:
```
{
    Animal {
        name @output(out_name: "ancestor")
        out_Animal_ParentOf {
            name @output(out_name: "descendant")
        }
    }
}
```
```
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
```
If the user then wanted to also add great-grandchildren to the `descendants` output, that would
require yet another query, and so on. Instead of concatenating the results of multiple queries,
the user can simply use the `@recurse` directive. The following query returns the child and
grandchild descendants:
```
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
```
Each row returned by this query contains the name of an `Animal` in the `ancestor` column
and the name of its child or grandchild in the `descendant` column.
The `out_Animal_ParentOf` vertex field marked `@recurse` is already enclosed within
another `out_Animal_ParentOf` vertex field, so the recursion starts at the
"child" level (the `out_Animal_ParentOf` not marked with `@recurse`).
Therefore, the `descendant` column contains the names of an `ancestor`'s
children (from `depth = 0` of the recursion) and the names of its grandchildren (from `depth = 1`).

Recursion using this directive is possible since the types of the enclosing scope and the recursion
scope work out: the `@recurse` directive is applied to a vertex field of type `Animal` and
its vertex field is enclosed within a scope of type `Animal`.
Additional cases where recursion is allowed are described in detail below.

The `descendant` column cannot have the name of the `ancestor` animal since the `@recurse`
is already within one `out_Animal_ParentOf` and not at the root `Animal` vertex field.
Similarly, it cannot have descendants that are more than two steps removed
(e.g., great-grandchildren), since the `depth` parameter of `@recurse` is set to `1`.

Now, let's see what happens when we eliminate the outer `out_Animal_ParentOf` vertex field
and simply have the `@recurse` applied on the `out_Animal_ParentOf` in the root vertex field scope:
```
{
    Animal {
        name @output(out_name: "ancestor")
        out_Animal_ParentOf @recurse(depth: 1) {
            name @output(out_name: "self_or_descendant")
        }
    }
}
```
In this case, when the recursion starts at `depth = 0`, the `Animal` within the recursion scope
will be the same `Animal` at the root vertex field, and therefore, in the `depth = 0` step of
the recursion, the value of the `self_or_descendant` field will be equal to the value of
the `ancestor` field.

#### Constraints and Rules
- "The types must work out" -- when applied within a scope of type `A`,
  to a vertex field of type `B`, at least one of the following must be true:
  - `A` is a GraphQL union;
  - `B` is a GraphQL interface, and `A` is a type that implements that interface;
  - `A` and `B` are the same type.
- `@recurse` can only be applied to vertex fields other than the root vertex field of a query.
- Cannot be used within a scope marked `@optional` or `@fold`.
- The `depth` parameter of the recursion must always have a value greater than or equal to 1.
  Using `depth = 1` produces the current vertex and its neighboring vertices along the
  specified edge.
- Type coercions and `@filter` directives within a scope marked `@recurse` do not limit the
  recursion depth. Conceptually, recursion to the specified depth happens first,
  and then type coercions and `@filter` directives eliminate some of the locations reached
  by the recursion.
- As demonstrated by the examples above, the recursion always starts at depth 0,
  so the recursion scope always includes the vertex at the scope that encloses
  the vertex field marked `@recurse`.

### @output_source

See the [Completeness of returned results](#completeness-of-returned-results) section
for a description of the directive and examples.

#### Constraints and Rules
- May exist at most once in any given GraphQL query.
- Can exist only on a vertex field, and only on the last vertex field used in the query.
- Cannot be used within a scope marked `@optional` or `@fold`.

## Supported filtering operations

### Comparison operators

Supported comparison operators:
- Equal to: `=`
- Not equal to: `!=`
- Greater than: `>`
- Less than: `<`
- Greater than or equal to: `>=`
- Less than or equal to: `<=`

#### Example Use

##### Equal to (`=`):
```
{
    Species {
        name @filter(op_name: "=", value: ["$species_name"])
        uuid @output(out_name: "species_uuid")
    }
}
```
This returns one row for every `Species` whose name is equal to the value of the `$species_name`
parameter, containing the `uuid` of the `Species` in a column named `species_uuid`.

##### Greater than or equal to (`>=`):
```
{
    Animal {
        name @output(out_name: "name")
        birthday @output(out_name: "birthday")
                 @filter(op_name: ">=", value: ["$point_in_time"])
    }
}
```
This returns one row for every `Animal` that was born after or on a `$point_in_time`,
containing the animal's name and birthday in columns named `name` and `birthday`, respectively.

#### Constraints and Rules
- All comparison operators must be on a property field.

### name_or_alias

Allows you to filter on vertices which contain the exact string `$wanted_name_or_alias` in their
`name` or `alias` fields.

#### Example Use
```
{
    Animal @filter(op_name: "name_or_alias", value: ["$wanted_name_or_alias"]) {
        name @output(out_name: "name")
    }
}
```
This returns one row for every `Animal` whose name and/or alias is equal to `$wanted_name_or_alias`,
containing the animal's name in a column named `name`.

The value provided for `$wanted_name_or_alias` must be the full name and/or alias of the `Animal`.
Substrings will not be matched.

#### Constraints and Rules
- Must be on a vertex field that has `name` and `alias` properties.

### between
#### Example Use
```
{
    Animal {
        name @output(out_name: "name")
        birthday @filter(op_name: "between", value: ["$lower", "$upper"])
                 @output(out_name: "birthday")
    }
}
```
This returns:
- One row for every `Animal` whose birthday is in between `$lower` and `$upper` dates (inclusive),
containing the animal's name in a column named `name`.

#### Constraints and Rules
- Must be on a property field.
- The lower and upper bounds represent an inclusive interval, which means that the output may
  contain values that match them exactly.

### in_collection
#### Example Use
```
{
    Animal {
        name @output(out_name: "animal_name")
        color @output(out_name: "color")
              @filter(op_name: "in_collection", value: ["$colors"])
    }
}
```
This returns one row for every `Animal` which has a color contained in a list of colors,
containing the `Animal`'s name and color in columns named `animal_name` and `color`, respectively.

#### Constraints and Rules
- Must be on a property field that is not of list type.

### has_substring
#### Example Use
```
{
    Animal {
        name @filter(op_name: "has_substring", value: ["$substring"])
             @output(out_name: "animal_name")
    }
}
```
This returns one row for every `Animal` whose name contains the value supplied
for the `$substring` parameter. Each row contains the matching `Animal`'s name
in a column named `animal_name`.

#### Constraints and Rules
- Must be on a property field of string type.

### contains
#### Example Use
```
{
    Animal {
        alias @filter(op_name: "contains", value: ["$wanted"])
        name @output(out_name: "animal_name")
    }
}
```
This returns one row for every `Animal` whose list of aliases contains the value supplied
for the `$wanted` parameter. Each row contains the matching `Animal`'s name
in a column named `animal_name`.

#### Constraints and Rules
- Must be on a property field of list type.

### has_edge_degree
#### Example Use
```
{
    Animal {
        name @output(out_name: "animal_name")

        out_Animal_ParentOf @filter(op_name: "has_edge_degree", value: ["$child_count"]) @optional {
            uuid
        }
    }
}
```
This returns one row for every `Animal` that has exactly `$child_count` children
(i.e. where the `out_Animal_ParentOf` edge appears exactly `$child_count` times).
Each row contains the matching `Animal`'s name, in a column named `animal_name`.

The `uuid` field within the `out_Animal_ParentOf` vertex field is added simply to satisfy
the GraphQL syntax rule that requires at least one field to exist within any `{}`.
Since this field is not marked with any directive, it has no effect on the query.

*N.B.:* Please note the `@optional` directive on the vertex field being filtered above.
If in your use case you expect to set `$child_count` to 0, you must also mark that
vertex field `@optional`. Recall that absence of `@optional` implies that at least one
such edge must exist. If the `has_edge_degree` filter is used with a parameter set to 0,
that requires the edge to not exist. Therefore, if the `@optional` is not present in this situation,
no valid result sets can be produced, and the resulting query will return no results.

#### Constraints and Rules
- Must be on a vertex field that is not the root vertex of the query.
- Tagged values are not supported as parameters for this filter.
- If the runtime parameter for this operator can be `0`, it is *strongly recommended* to also apply
`@optional` to the vertex field being filtered (see N.B. above for details).

## Type coercions

Type coercions are operations that create a new scope whose type is different than the type of the
enclosing scope of the coercion -- they coerce the enclosing scope into a different type.
Type coercions are represented with GraphQL inline fragments.

#### Example Use
```
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
```
Here, the `out_Species_Eats` vertex field is of the `FoodOrSpecies` union type. To proceed
with the query, the user must choose which of the types in the `FoodOrSpecies` union to use.
In this example, `... on Food` indicates that the `Food` type was chosen, and any vertices
at that scope that are not of type `Food` are filtered out and discarded.

```
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
```
In this query, the `out_Entity_Related` is of `Entity` type. However, the query only wants to
return results where the related entity is a `Species`, which `... on Species` ensures is the case.

## Meta fields

The compiler supports the standard GraphQL meta field `__typename`, which returns the runtime type
of the scope where the field is found. Assuming the GraphQL schema matches the database's schema,
the runtime type will always be a subtype of (or exactly equal to) the static type of the scope
determined by the GraphQL type system. Below, we provide an example query in which
the runtime type is a subtype of the static type, but is not equal to it.

The `__typename` field is treated as a property field of type `String`, and supports
all directives that can be applied to any other property field.

#### Example Use

```
{
    Entity {
        __typename @output(out_name: "entity_type")
        name @output(out_name: "entity_name")
    }
}
```
This query returns one row for each `Entity` vertex. The scope in which `__typename` appears is
of static type `Entity`. However, `Animal` is a type of `Entity`, as are `Species`, `Food`,
and others. Vertices of all subtypes of `Entity` will therefore be returned, and the `entity_type`
column that outputs the `__typename` field will show their runtime type: `Animal`, `Species`,
`Food`, etc.

## The GraphQL schema

This section assumes that the reader is familiar with the way schemas work in the
[reference implementation of GraphQL](http://graphql.org/learn/schema/).

The GraphQL schema used with the compiler must contain the custom directives and custom `Date`
and `DateTime` scalar types defined by the compiler:
```
directive @recurse(depth: Int!) on FIELD

directive @filter(value: [String!]!, op_name: String!) on FIELD | INLINE_FRAGMENT

directive @tag(tag_name: String!) on FIELD

directive @output(out_name: String!) on FIELD

directive @output_source on FIELD

directive @optional on FIELD

directive @fold on FIELD

scalar DateTime

scalar Date
```
If constructing the schema programmatically, one can simply import the the Python object
representations of the custom directives and the custom types:
```
from graphql_compiler import DIRECTIVES  # the list of custom directives
from graphql_compiler import GraphQLDate, GraphQLDateTime  # the custom types
```

Since the GraphQL and OrientDB type systems have different rules, there is no one-size-fits-all
solution to writing the GraphQL schema for a given database schema.
However, the following rules of thumb are useful to keep in mind:
- Generally, represent OrientDB abstract classes as GraphQL interfaces. In GraphQL's type system,
  GraphQL interfaces cannot inherit from other GraphQL interfaces.
- Generally, represent OrientDB non-abstract classes as GraphQL types,
  listing the GraphQL interfaces that they implement. In GraphQL's type system, GraphQL types
  cannot inherit from other GraphQL types.
- Inheritance relationships between two OrientDB non-abstract classes,
  or between two OrientDB abstract classes, introduce some difficulties in GraphQL.
  When modelling your data in OrientDB, it's best to avoid such inheritance if possible.
- If it is impossible to avoid having two non-abstract OrientDB classes `A` and `B` such that
  `B` inherits from `A`, you have two options:
    - You may choose to represent the `A` OrientDB class as a GraphQL interface,
      which the GraphQL type corresponding to `B` can implement.
      In this case, the GraphQL schema preserves the inheritance relationship
      between `A` and `B`, but sacrifices the representation of any inheritance relationships
      `A` may have with any OrientDB superclasses.
    - You may choose to represent both `A` and `B` as GraphQL types. The tradeoff in this case is
      exactly the opposite from the previous case: the GraphQL schema
      sacrifices the inheritance relationship between `A` and `B`, but preserves the
      inheritance relationships of `A` with its superclasses.
      In this case, it is recommended to create a GraphQL union type `A | B`,
      and to use that GraphQL union type for any vertex fields that
      in OrientDB would be of type `A`.
- If it is impossible to avoid having two abstract OrientDB classes `A` and `B` such that
  `B` inherits from `A`, you similarly have two options:
    - You may choose to represent `B` as a GraphQL type that can implement the GraphQL interface
      corresponding to `A`. This makes the GraphQL schema preserve the inheritance relationship
      between `A` and `B`, but sacrifices the ability for other GraphQL types to inherit from `B`.
    - You may choose to represent both `A` and `B` as GraphQL interfaces, sacrificing the schema's
      representation of the inheritance between `A` and `B`, but allowing GraphQL types
      to inherit from both `A` and `B`. If necessary, you can then create a GraphQL
      union type `A | B` and use it for any vertex fields that in OrientDB would be of type `A`.
- It is legal to fully omit classes and fields that are not representable in GraphQL. The compiler
  currently does not support OrientDB's `EmbeddedMap` type nor embedded non-primitive typed fields,
  so such fields can simply be omitted in the GraphQL representation of their classes.
  Alternatively, the entire OrientDB class and all edges that may point to it may be omitted
  entirely from the GraphQL schema.

## Execution model

Since the GraphQL compiler can target multiple different query languages, each with its own
behaviors and limitations, the execution model must also be defined as a function of the
compilation target language. While we strive to minimize the differences between
compilation targets, some differences are unavoidable.

The compiler abides by the following principles:
- When the database is queried with a compiled query string, its response must always be in the
  form of a list of results.
- The precise format of each such result is defined by each compilation target separately.
  - Both `gremlin` and `MATCH` return data in a tabular format, where each result is
    a row of the table, and fields marked for output are columns.
  - However, future compilation targets may have a different format. For example, each result
    may appear in the nested tree format used by the standard GraphQL specification.
- Each such result must satisfy all directives and types in its corresponding GraphQL query.
- The returned list of results is **not** guaranteed to be complete!
  - In other words, there may have been additional result sets that satisfy all directives and
    types in the corresponding GraphQL query, but were not returned by the database.
  - However, compilation target implementations are encouraged to return complete results
    if at all practical. The `MATCH` compilation target is guaranteed to produce complete results.

### Completeness of returned results

To explain the completeness of returned results in more detail, assume the database contains
the following example graph:
```
a  ---->_ x
|____   /|
    _|_/
   / |____
  /      \/
b  ----> y
```
Let `a, b, x, y` be the values of the `name` property field of four vertices.
Let the vertices named `a` and `b` be of type `S`, and let `x` and `y` be of type `T`.
Let vertex `a` be connected to both `x` and `y` via directed edges of type `E`.
Similarly, let vertex `b` also be connected to both `x` and `y` via directed edges of type `E`.

Consider the GraphQL query:
```
{
    S {
        name @output(out_name: "s_name")
        out_E {
            name @output(out_name: "t_name")
        }
    }
}
```

Between the data in the database and the query's structure, it is clear that combining any of
`a` or `b` with any of `x` or `y` would produce a valid result. Therefore,
the complete result list, shown here in JSON format, would be:
```
[
    {"s_name": "a", "t_name": "x"},
    {"s_name": "a", "t_name": "y"},
    {"s_name": "b", "t_name": "x"},
    {"s_name": "b", "t_name": "y"},
]
```

This is precisely what the `MATCH` compilation target is guaranteed to produce.
The remainder of this section is only applicable to the `gremlin` compilation target. If using
`MATCH`, all of the queries listed in the remainder of this section will produce the same, complete
result list.

Since the `gremlin` compilation target does not guarantee a complete result list,
querying the database using a query string generated by the `gremlin` compilation target
will produce only a partial result list resembling the following:
```
[
    {"s_name": "a", "t_name": "x"},
    {"s_name": "b", "t_name": "x"},
]
```

Due to limitations in the underlying query language, `gremlin` will by default produce at most one
result for each of the starting locations in the query. The above GraphQL query started at
the type `S`, so each `s_name` in the returned result list is therefore distinct. Furthermore,
there is no guarantee (and no way to know ahead of time) whether `x` or `y` will be returned as
the `t_name` value in each result, as they are both valid results.

Users may apply the `@output_source` directive on the last scope of the query
to alter this behavior:
```
{
    S {
        name @output(out_name: "s_name")
        out_E @output_source {
            name @output(out_name: "t_name")
        }
    }
}
```

Rather than producing at most one result for each `S`, the query will now produce
at most one result for each distinct value that can be found at `out_E`, where the directive
is applied:
```
[
    {"s_name": "a", "t_name": "x"},
    {"s_name": "a", "t_name": "y"},
]
```

Conceptually, applying the `@output_source` directive makes it as if the query were written in
the opposite order:
```
{
    T {
        name @output(out_name: "t_name")
        in_E {
            name @output(out_name: "s_name")
        }
    }
}
```

## Miscellaneous

### Expanding [`@optional`](#optional) vertex fields
Including an optional statement in GraphQL has no performance issues on its own,
but if you continue expanding vertex fields within an optional scope,
there may be significant performance implications.

Going forward, we will refer to two different kinds of `@optional` directives.

- A *"simple"* optional is a vertex with an `@optional` directive that does not expand
any vertex fields within it.
For example:
```
{
    Animal {
        name @output(out_name: "name")
        in_Animal_ParentOf @optional {
            name @output(out_name: "parent_name")
        }
    }
}
```
OrientDB `MATCH` currently allows the last step in any traversal to be optional.
Therefore, the equivalent `MATCH` traversal for the above `GraphQL` is as follows:
```
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
```

- A *"compound"* optional is a vertex with an `@optional` directive which does expand
vertex fields within it.
For example:
```
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
```
Currently, this cannot represented by a simple `MATCH` query.
Specifically, the following is *NOT* a valid `MATCH` statement,
because the optional traversal follows another edge:
```
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
```

Instead, we represent a *compound* optional by taking an union (`UNIONALL`) of two distinct
`MATCH` queries. For instance, the `GraphQL` query above can be represented as follows:
```
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
```
In the first case where the optional edge is not followed,
we have to explicitly filter out all vertices where the edge *could have been followed*.
This is to eliminate duplicates between the two `MATCH` selections.

The previous example is not *exactly* how we implement *compound* optionals
(we also have `SELECT` statements within `$match1` and `$match2`),
but it illustrates the the general idea.

#### Performance Penalty

If we have many *compound* optionals in the given `GraphQL`,
the above procedure results in the union of a large number of `MATCH` queries.
Specifically, for `n` compound optionals, we generate 2<sup>n</sup> different `MATCH` queries.
For each of the 2<sup>n</sup> subsets `S` of the `n` optional edges:
- We remove the `@optional` restriction for each traversal in `S`.
- For each traverse `t` in the complement of `S`, we entirely discard `t`
  along with all the vertices and directives within it, and we add a filter
  on the previous traverse to ensure that the edge corresponding to `t` does not exist.

Therefore, we get a performance penalty that grows exponentially
with the number of *compound* optional edges.
This is important to keep in mind when writing queries with many optional directives.


### Optional `type_equivalence_hints` parameter

This compilation parameter is a workaround for the limitations of the GraphQL and Gremlin
type systems:
- GraphQL does not allow `type` to inherit from another `type`, only to implement an `interface`.
- Gremlin does not have first-class support for inheritance at all.

Assume the following GraphQL schema:
```
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
```

An appropriate `type_equivalence_hints` value here would be `{ Animal: AnimalCatDog }`.
This lets the compiler know that the `AnimalCatDog` union type is implicitly equivalent to
the `Animal` type, as there are no other types that inherit from `Animal` in the database schema.
This allows the compiler to perform accurate type coercions in Gremlin, as well as optimize away
type coercions across edges of union type if the coercion is coercing to the
union's equivalent type.

Setting `type_equivalence_hints = { Animal: AnimalCatDog }` during compilation
would enable the use of a `@fold` on the `adjacent_animal` vertex field of `Foo`:
```
{
    Foo {
        adjacent_animal @fold {
            ... on Animal {
                name @output(out_name: "name")
            }
        }
    }
}
```

## License

Licensed under the Apache 2.0 License. Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language
governing permissions and limitations under the License.

Copyright 2017 Kensho Technologies, LLC.
