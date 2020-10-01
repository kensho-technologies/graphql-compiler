Execution model
===============

Since the GraphQL compiler can target multiple different query languages, each with its own
behaviors and limitations, the execution model must also be defined as a function of the
compilation target language. While we strive to minimize the differences between compilation
targets, some differences are unavoidable.

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
- The returned list of results is **not** guaranteed to be complete! (This currently only applies
  to Gremlin - please follow this :ref:`link <output_source>` for more information on the issue).

  - In other words, there may have been additional result sets that satisfy all directives and
    types in the corresponding GraphQL query, but were not returned by the database.
  - However, compilation target implementations are encouraged to return complete results if at all
    practical. The :code:`MATCH` compilation target is guaranteed to produce complete results.
