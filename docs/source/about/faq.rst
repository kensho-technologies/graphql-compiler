Frequently Asked Questions
==========================

**Q: Do you really use GraphQL, or do you just use GraphQL-like
syntax?**

A: We really use GraphQL. Any query that the compiler will accept is
entirely valid GraphQL, and we actually use the Python port of the
GraphQL core library for parsing and type checking. However, since the
database queries produced by compiling GraphQL are subject to the
limitations of the database system they run on, our execution model is
somewhat different compared to the one described in the standard GraphQL
specification.

.. TODO: Add a link to the execution model section. Once it is added.

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
