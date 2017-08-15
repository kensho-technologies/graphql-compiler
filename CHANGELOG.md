# Changelog

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
