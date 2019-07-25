# Changelog

## Current development version

## v1.10.1

- Fix `_x_count` and optional filter creating duplicate GlobalOperationsStart IR blocks. [#253](https://github.com/kensho-technologies/graphql-compiler/pull/253).
- Raise error for unused @tag directives [#224](https://github.com/kensho-technologies/graphql-compiler/pull/224).
- Much documentation cleanup and many maintainer quality-of-life improvements.

Thanks to `bojanserafimov`, `evantey14`, `jeremy.meulemans`, and `pmantica1` for their contributions.

## v1.10.0

- **BREAKING**: Rename the `__count` meta field to `_x_count`, to avoid GraphQL schema parsing issues with other GraphQL libraries. [#176](https://github.com/kensho-technologies/graphql-compiler/pull/176)

## v1.9.0

- Add a `__count` meta field that supports outputting and filtering on the size of a `@fold` scope. [#158](https://github.com/kensho-technologies/graphql-compiler/pull/158)
- Add scaffolding for development and testing of SQL compiler backend, and a variety of development quality-of-life improvements.

Thanks to `jmeulemans` for his contributions.

## v1.8.3

- Explicit support for Python 3.7. Earlier compiler versions also worked on 3.7, but now we also run tests in 3.7 to confirm. [#148](https://github.com/kensho-technologies/graphql-compiler/pull/148)
- Bug fix for compilation error when using `has_edge_degree` and `between` filtering in the same scope. [#146](https://github.com/kensho-technologies/graphql-compiler/pull/146)
- Exposed additional query metadata that describes `@recurse` and `@filter` directives encountered in the query. [#141](https://github.com/kensho-technologies/graphql-compiler/pull/141/files)

Thanks to `gurer-kensho` for the contribution.

## v1.8.2

- Fix overly strict type check on `@recurse` directives involving a union type. [#131](https://github.com/kensho-technologies/graphql-compiler/pull/131)

Thanks to `cw6515` for the fix!

## v1.8.1

- Fix a bug that arose when using certain type coercions that the compiler optimizes away to a no-op. [#127](https://github.com/kensho-technologies/graphql-compiler/pull/127)

Thanks to `bojanserafimov` for the fix!

## v1.8.0

- Allow `@optional` vertex fields nested inside other `@optional` vertex fields. [#120](https://github.com/kensho-technologies/graphql-compiler/pull/120)
- Fix a bug that accidentally disallowed having two `@recurse` directives within the same vertex field. [#115](https://github.com/kensho-technologies/graphql-compiler/pull/115)
- Enforce that all required directives are present in the schema. [#114](https://github.com/kensho-technologies/graphql-compiler/pull/114)
- Under the hood, made fairly major changes to how query metadata is tracked and processed.

Thanks to `amartyashankha`, `cw6515`, and `yangsong97` for their contributions!

## v1.7.2

- Fix possible incorrect query execution due to dropped type coercions. [#110](https://github.com/kensho-technologies/graphql-compiler/pull/110) [#113](https://github.com/kensho-technologies/graphql-compiler/pull/113)

## v1.7.0

- Add a new `@filter` operator: `intersects`. [#100](https://github.com/kensho-technologies/graphql-compiler/pull/100)
- Add an optimization that helps OrientDB choose a good starting point for query evaluation. [#102](https://github.com/kensho-technologies/graphql-compiler/pull/102)

The new optimization pass manages what type information is visible at different points in
the generated query. By exposing additional type information, or hiding existing type information,
the compiler maximizes the likelihood that OrientDB will start evaluating the query at the
location of lowest cardinality. This produces a massive performance benefit -- up to 1000x
on some queries!

Thanks to `yangsong97` for making his first contribution with the `intersects` operator!

## v1.6.2

- Fix incorrect filtering in `@optional` locations. [#95](https://github.com/kensho-technologies/graphql-compiler/pull/95)

Thanks to `amartyashankha` for the fix!

## v1.6.1

- Fix a bad compilation bug on `@fold` and `@optional` in the same scope. [#86](https://github.com/kensho-technologies/graphql-compiler/pull/86)

Thanks to `amartyashankha` for the fix!

## v1.6.0

- Add full support for `Decimal` data, including both filtering and output. [#91](https://github.com/kensho-technologies/graphql-compiler/pull/91)

## v1.5.0

- Allow expanding vertex fields within `@optional` scopes. [#83](https://github.com/kensho-technologies/graphql-compiler/pull/83)

This is a massive feature, totaling over 4000 lines of changes and hundreds of hours of
many engineers' time. Special thanks to `amartyashankha` for taking point on the implementation!

This feature implements a workaround for a limitation of OrientDB, where `MATCH` treats
optional vertices as terminal and does not allow subsequent traversals from them.
To work around this issue, the compiler rewrites the query into several disjoint queries
whose union produces the exact same results as a single query that allows optional traversals.
See [the documentation in the README](https://github.com/kensho-technologies/graphql-compiler/blob/3c79cd97744b7f3f842c2d32ddc2a072c7fa7898/README.md#expanding-optional-vertex-fields)
for more details.

## v1.4.1

- Make MATCH use the `BETWEEN` operator when possible, to avoid [an OrientDB performance issue](https://github.com/orientechnologies/orientdb/issues/8230) [#70](https://github.com/kensho-technologies/graphql-compiler/pull/70)

Thanks to `amartyashankha` for this contribution!

## v1.4.0

- Enable expanding vertex fields inside `@fold` [#64](https://github.com/kensho-technologies/graphql-compiler/pull/64)

Thanks to `amartyashankha` for this contribution!

## v1.3.1

- Add a workaround for a bug in OrientDB related to `@recurse` with type coercions [#55](https://github.com/kensho-technologies/graphql-compiler/pull/55)
- Exposed the package name and version in the root `__init__.py` file [#57](https://github.com/kensho-technologies/graphql-compiler/pull/57)

## v1.3.0

- Add a new `@filter` operator: `has_edge_degree`. [#52](https://github.com/kensho-technologies/graphql-compiler/pull/52)
- Lots of under-the-hood cleanup and improvements.

## v1.2.1

- Add workaround for [OrientDB type inconsistency when filtering lists](https://github.com/orientechnologies/orientdb/issues/7811) [#42](https://github.com/kensho-technologies/graphql-compiler/pull/42)

## v1.2.0

- **BREAKING**: Requires OrientDB 2.2.28+, since it depends on two OrientDB bugs being fixed: [bug 1](https://github.com/orientechnologies/orientdb/issues/7225) [bug 2](https://github.com/orientechnologies/orientdb/issues/7754)
- Allow type coercions and filtering within `@fold` scopes.
- Fix bug where `@filter` directives could end up ignored if more than two were in the same scope
- Optimize type coercions in `@optional` and `@recurse` scopes.
- Optimize multiple outputs from the same `@fold` scope.
- Allow having multiple `@filter` directives on the same field [#33](https://github.com/kensho-technologies/graphql-compiler/pull/33)
- Allow using the `name_or_alias` filtering operation on interface types [#37](https://github.com/kensho-technologies/graphql-compiler/pull/37)

## v1.1.0

- Add support for Python 3 [#31](https://github.com/kensho-technologies/graphql-compiler/pull/31)
- Make it possible to use `@fold` together with union-typed vertex fields [#32](https://github.com/kensho-technologies/graphql-compiler/pull/32)

Thanks to `ColCarroll` for making the compiler support Python 3!

## v1.0.3

- Fix a minor bug in the GraphQL pretty-printer [#30](https://github.com/kensho-technologies/graphql-compiler/pull/30)

## v1.0.2

- Make the `graphql_to_ir()` easier to use by making it automatically add a
  new line to the end of the GraphQL query string. Works around an issue in
  the `graphql-core`dependency library: https://github.com/graphql-python/graphql-core/issues/98
- Robustness improvements for the pretty-printer [#27](https://github.com/kensho-technologies/graphql-compiler/pull/27)

Thanks to `benlongo` for their contributions.

## v1.0.1

- Add GraphQL pretty printer: `python -m graphql_compiler.tool` [#23](https://github.com/kensho-technologies/graphql-compiler/pull/23)
- Raise errors if there are no `@output` directives within a `@fold` scope [#18](https://github.com/kensho-technologies/graphql-compiler/pull/18)

Thanks to `benlongo`, `ColCarroll`, and `cw6515` for their contributions.

## v1.0.0

Initial release.

Thanks to `MichaelaShtilmanMinkin` for the help in putting the documentation together.
