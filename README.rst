graphql-compiler
================

|Build Status| |Coverage Status| |License| |PyPI Python| |PyPI Version|
|PyPI Status| |PyPI Wheel| |Code Style|

Turn complex GraphQL queries into optimized database queries.

::

    pip install graphql-compiler

Quick Overview
--------------

The GraphQL Compiler is a library that simplifies database querying and exploration by exposing one
common query language for multiple database backends. The query language is:

.. EDUCATIONAL: The pattern below is what you would call a definition list in restructuredtext.
   The "terms" get special rendering in the readthedocs html file.

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

For a more detailed overview and getting started guide, please see
`our ReadTheDocs documentation <https://graphql-compiler.readthedocs.io/en/latest/>`__
and `our blog post <https://blog.kensho.com/compiled-graphql-as-a-database-query-language-72e106844282>`__.

License
-------

Licensed under the Apache 2.0 License. Unless required by applicable law
or agreed to in writing, software distributed under the License is
distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied. See the License for the specific
language governing permissions and limitations under the License.

Copyright 2017-present Kensho Technologies, LLC. The present date is
determined by the timestamp of the most recent commit in the repository.

.. |Build Status| image:: https://travis-ci.org/kensho-technologies/graphql-compiler.svg?branch=main
   :target: https://travis-ci.org/kensho-technologies/graphql-compiler
.. |Coverage Status| image:: https://codecov.io/gh/kensho-technologies/graphql-compiler/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/kensho-technologies/graphql-compiler
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
.. |Code Style| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: Code style: black
