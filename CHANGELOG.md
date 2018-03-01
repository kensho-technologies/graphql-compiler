# Changelog

## Current development version

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
