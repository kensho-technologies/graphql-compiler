GraphQL Compiler
================

.. The meta field below is for search engine optimization.
.. meta::
   :description: Turn complex GraphQL queries into optimized database queries.
   :keywords: graphql compiler, database, orientdb, sql

The GraphQL Compiler simplifies database querying and exploration by exposing one common
query language for multiple database backends.  The query language is:

Written in valid GraphQL syntax
   Since it uses GraphQL syntax, the user get access to the entire GraphQL ecosystem,
   including the typeahead capabilities and query validation capabilities of `GraphiQL
   <https://github.com/graphql/graphiql>`__, user friendly error messages from the
   reference GraphQL python implementation, and more.

Directly compiled to the target database language
   By compiling instead of interpreting the query language, the compiler highly improves query
   performance and empowers the user with the ability to write deep and complex queries.
   Furthermore, by using schema information from the target database, the compiler is able to
   extensively validate queries, often more so than the DB-API, (e.g. :code:`pymssql`).

Ideal for cross-database querying
   Since the query language always has abstractly the same semantics regardless of the database
   of choice, it is quite feasible to use it as a means for cross-database querying and this is
   exactly what we have done in the Schema Stitching section.
