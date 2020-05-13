Changelog
=========

Current development version
---------------------------

v2.0.0
------

- **BREAKING** Change the :code:`GraphQLDateTime` scalar type from being timezone-aware aware to
  being timezone-naive to follow the usual database convention of naming the timezone-naive
  type "datetime" and avoid confusion after we've added both timezone-aware and timezone-naive
  types.
  `#827 <https://github.com/kensho-technologies/graphql-compiler/pull/827>`__

v1.11.0
-------

-  Release automatic GraphQL schema generation from OrientDB schema
   metadata.
   `#204 <https://github.com/kensho-technologies/graphql-compiler/pull/204>`__
-  Release the SchemaGraph, a utility class designed for easy schema
   introspection.
   `#292 <https://github.com/kensho-technologies/graphql-compiler/pull/292>`__
-  Release :code:`not_contains` and :code:`not_in_collection` filter operations.
   `#349 <https://github.com/kensho-technologies/graphql-compiler/pull/349>`__
   `#350 <https://github.com/kensho-technologies/graphql-compiler/pull/350>`__
-  Allow out-of-order :code:`@tag` and :code:`@filter` when in the same scope.
   `#351 <https://github.com/kensho-technologies/graphql-compiler/pull/351>`__
-  Fix a bug causing MATCH queries to have missing type coercions.
   `#332 <https://github.com/kensho-technologies/graphql-compiler/pull/332>`__
-  Release functionality that is able to amend parsing and serialization
   of custom scalar types in schemas parsed from text form.
   `#398 <https://github.com/kensho-technologies/graphql-compiler/pull/398>`__
-  Improve validation error messages for output and parameter names.
   `#414 <https://github.com/kensho-technologies/graphql-compiler/pull/414>`__
   `#416 <https://github.com/kensho-technologies/graphql-compiler/pull/416>`__
-  Alpha (unstable) release of query cost estimation functionality.
   `#345 <https://github.com/kensho-technologies/graphql-compiler/pull/345>`__
-  Clean up README.md and update troubleshooting documentation.
-  Many maintainer quality-of-life improvements.

Thanks to :code:`0xflotus`, :code:`bojanserafimov`, :code:`evantey`,
:code:`LWProgramming`, :code:`pmantica1`, :code:`qqi0O0`, and :code:`Vlad` for their
contributions.

v1.10.1
-------

-  Fix :code:`_x_count` and optional filter creating duplicate
   GlobalOperationsStart IR blocks.
   `#253 <https://github.com/kensho-technologies/graphql-compiler/pull/253>`__.
-  Raise error for unused :code:`@tag` directives
   `#224 <https://github.com/kensho-technologies/graphql-compiler/pull/224>`__.
-  Much documentation cleanup and many maintainer quality-of-life
   improvements.

Thanks to :code:`bojanserafimov`, :code:`evantey14`, :code:`jeremy.meulemans`, and
:code:`pmantica1` for their contributions.

v1.10.0
-------

-  **BREAKING**: Rename the :code:`__count` meta field to :code:`_x_count`, to
   avoid GraphQL schema parsing issues with other GraphQL libraries.
   `#176 <https://github.com/kensho-technologies/graphql-compiler/pull/176>`__

v1.9.0
------

-  Add a :code:`__count` meta field that supports outputting and filtering
   on the size of a :code:`@fold` scope.
   `#158 <https://github.com/kensho-technologies/graphql-compiler/pull/158>`__
-  Add scaffolding for development and testing of SQL compiler backend,
   and a variety of development quality-of-life improvements.

Thanks to :code:`jmeulemans` for his contributions.

v1.8.3
------

-  Explicit support for Python 3.7. Earlier compiler versions also
   worked on 3.7, but now we also run tests in 3.7 to confirm.
   `#148 <https://github.com/kensho-technologies/graphql-compiler/pull/148>`__
-  Bug fix for compilation error when using :code:`has_edge_degree` and
   :code:`between` filtering in the same scope.
   `#146 <https://github.com/kensho-technologies/graphql-compiler/pull/146>`__
-  Exposed additional query metadata that describes :code:`@recurse` and
   :code:`@filter` directives encountered in the query.
   `#141 <https://github.com/kensho-technologies/graphql-compiler/pull/141/files>`__

Thanks to :code:`gurer-kensho` for the contribution.

v1.8.2
------

-  Fix overly strict type check on :code:`@recurse` directives involving a
   union type.
   `#131 <https://github.com/kensho-technologies/graphql-compiler/pull/131>`__

Thanks to :code:`cw6515` for the fix!

v1.8.1
------

-  Fix a bug that arose when using certain type coercions that the
   compiler optimizes away to a no-op.
   `#127 <https://github.com/kensho-technologies/graphql-compiler/pull/127>`__

Thanks to :code:`bojanserafimov` for the fix!

v1.8.0
------

-  Allow :code:`@optional` vertex fields nested inside other :code:`@optional`
   vertex fields.
   `#120 <https://github.com/kensho-technologies/graphql-compiler/pull/120>`__
-  Fix a bug that accidentally disallowed having two :code:`@recurse`
   directives within the same vertex field.
   `#115 <https://github.com/kensho-technologies/graphql-compiler/pull/115>`__
-  Enforce that all required directives are present in the schema.
   `#114 <https://github.com/kensho-technologies/graphql-compiler/pull/114>`__
-  Under the hood, made fairly major changes to how query metadata is
   tracked and processed.

Thanks to :code:`amartyashankha`, :code:`cw6515`, and :code:`yangsong97` for their
contributions!

v1.7.2
------

-  Fix possible incorrect query execution due to dropped type coercions.
   `#110 <https://github.com/kensho-technologies/graphql-compiler/pull/110>`__
   `#113 <https://github.com/kensho-technologies/graphql-compiler/pull/113>`__

v1.7.0
------

-  Add a new :code:`@filter` operator: :code:`intersects`.
   `#100 <https://github.com/kensho-technologies/graphql-compiler/pull/100>`__
-  Add an optimization that helps OrientDB choose a good starting point
   for query evaluation.
   `#102 <https://github.com/kensho-technologies/graphql-compiler/pull/102>`__

The new optimization pass manages what type information is visible at
different points in the generated query. By exposing additional type
information, or hiding existing type information, the compiler maximizes
the likelihood that OrientDB will start evaluating the query at the
location of lowest cardinality. This produces a massive performance
benefit -- up to 1000x on some queries!

Thanks to :code:`yangsong97` for making his first contribution with the
:code:`intersects` operator!

v1.6.2
------

-  Fix incorrect filtering in :code:`@optional` locations.
   `#95 <https://github.com/kensho-technologies/graphql-compiler/pull/95>`__

Thanks to :code:`amartyashankha` for the fix!

v1.6.1
------

-  Fix a bad compilation bug on :code:`@fold` and :code:`@optional` in the same
   scope.
   `#86 <https://github.com/kensho-technologies/graphql-compiler/pull/86>`__

Thanks to :code:`amartyashankha` for the fix!

v1.6.0
------

-  Add full support for :code:`Decimal` data, including both filtering and
   output.
   `#91 <https://github.com/kensho-technologies/graphql-compiler/pull/91>`__

v1.5.0
------

-  Allow expanding vertex fields within :code:`@optional` scopes.
   `#83 <https://github.com/kensho-technologies/graphql-compiler/pull/83>`__

This is a massive feature, totaling over 4000 lines of changes and
hundreds of hours of many engineers' time. Special thanks to
:code:`amartyashankha` for taking point on the implementation!

This feature implements a workaround for a limitation of OrientDB, where
:code:`MATCH` treats optional vertices as terminal and does not allow
subsequent traversals from them. To work around this issue, the compiler
rewrites the query into several disjoint queries whose union produces
the exact same results as a single query that allows optional
traversals. See this :ref:`link <compound_optional_performance_penalty>` for more details.

v1.4.1
------

-  Make MATCH use the :code:`BETWEEN` operator when possible, to avoid `an
   OrientDB performance
   issue <https://github.com/orientechnologies/orientdb/issues/8230>`__
   `#70 <https://github.com/kensho-technologies/graphql-compiler/pull/70>`__

Thanks to :code:`amartyashankha` for this contribution!

v1.4.0
------

-  Enable expanding vertex fields inside :code:`@fold`
   `#64 <https://github.com/kensho-technologies/graphql-compiler/pull/64>`__

Thanks to :code:`amartyashankha` for this contribution!

v1.3.1
------

-  Add a workaround for a bug in OrientDB related to :code:`@recurse` with
   type coercions
   `#55 <https://github.com/kensho-technologies/graphql-compiler/pull/55>`__
-  Exposed the package name and version in the root :code:`__init__.py` file
   `#57 <https://github.com/kensho-technologies/graphql-compiler/pull/57>`__

v1.3.0
------

-  Add a new :code:`@filter` operator: :code:`has_edge_degree`.
   `#52 <https://github.com/kensho-technologies/graphql-compiler/pull/52>`__
-  Lots of under-the-hood cleanup and improvements.

v1.2.1
------

-  Add workaround for `OrientDB type inconsistency when filtering
   lists <https://github.com/orientechnologies/orientdb/issues/7811>`__
   `#42 <https://github.com/kensho-technologies/graphql-compiler/pull/42>`__

v1.2.0
------

-  **BREAKING**: Requires OrientDB 2.2.28+, since it depends on two
   OrientDB bugs being fixed: `bug
   1 <https://github.com/orientechnologies/orientdb/issues/7225>`__ `bug
   2 <https://github.com/orientechnologies/orientdb/issues/7754>`__
-  Allow type coercions and filtering within :code:`@fold` scopes.
-  Fix bug where :code:`@filter` directives could end up ignored if more
   than two were in the same scope
-  Optimize type coercions in :code:`@optional` and :code:`@recurse` scopes.
-  Optimize multiple outputs from the same :code:`@fold` scope.
-  Allow having multiple :code:`@filter` directives on the same field
   `#33 <https://github.com/kensho-technologies/graphql-compiler/pull/33>`__
-  Allow using the :code:`name_or_alias` filtering operation on interface
   types
   `#37 <https://github.com/kensho-technologies/graphql-compiler/pull/37>`__

v1.1.0
------

-  Add support for Python 3
   `#31 <https://github.com/kensho-technologies/graphql-compiler/pull/31>`__
-  Make it possible to use :code:`@fold` together with union-typed vertex
   fields
   `#32 <https://github.com/kensho-technologies/graphql-compiler/pull/32>`__

Thanks to :code:`ColCarroll` for making the compiler support Python 3!

v1.0.3
------

-  Fix a minor bug in the GraphQL pretty-printer
   `#30 <https://github.com/kensho-technologies/graphql-compiler/pull/30>`__

v1.0.2
------

-  Make the :code:`graphql_to_ir()` easier to use by making it automatically
   add a new line to the end of the GraphQL query string. Works around
   an issue in the :code:`graphql-core`\ dependency library:
   `https://github.com/graphql-python/graphql-core/issues/98 <https://github.com/graphql-python/graphql-core/issues/98>`__
-  Robustness improvements for the pretty-printer
   `#27 <https://github.com/kensho-technologies/graphql-compiler/pull/27>`__

Thanks to :code:`benlongo` for their contributions.

v1.0.1
------

-  Add GraphQL pretty printer: :code:`python -m graphql_compiler.tool`
   `#23 <https://github.com/kensho-technologies/graphql-compiler/pull/23>`__
-  Raise errors if there are no :code:`@output` directives within a
   :code:`@fold` scope
   `#18 <https://github.com/kensho-technologies/graphql-compiler/pull/18>`__

Thanks to :code:`benlongo`, :code:`ColCarroll`, and :code:`cw6515` for their
contributions.

v1.0.0
------

Initial release.

Thanks to :code:`MichaelaShtilmanMinkin` for the help in putting the
documentation together.
