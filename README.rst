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
common query language to target multiple database backends.

For a more detailed overview and getting started guide, please see
`our ReadTheDocs documentation <https://graphql-compiler.readthedocs.io/en/latest/>`__
and `our blog post <https://blog.kensho.com/compiled-graphql-as-a-database-query-language-72e106844282>`__.
For contributing please see `our contributing guide <https://graphql-compiler.readthedocs.io/en/latest/about/contributing.html>`__.

Example
~~~~~~~

Even though this example specifically targets a SQL database, it is meant to be a generic end-to-end
example of how to use the GraphQL compiler.

.. include:: examples/end_to_end_sql.py
   :code: python


License
-------

`Apache 2.0`_ © 2017-present Kensho Technologies, LLC.

.. _Apache 2.0: LICENSE.txt

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
