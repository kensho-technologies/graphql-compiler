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
common query language written in GraphQL syntax to target multiple database backends. It currently
supports `OrientDB <https://graphql-compiler.readthedocs.io/en/latest/supported_databases/orientdb.html>`__.
and multiple `SQL <https://graphql-compiler.readthedocs.io/en/latest/supported_databases/sql.html>`__
database management systems such as Postgresql, MSSQL and MySQl.

For a more detailed overview and getting started guide, please see
`our ReadTheDocs documentation <https://graphql-compiler.readthedocs.io/en/latest/>`__
and `our blog post <https://blog.kensho.com/compiled-graphql-as-a-database-query-language-72e106844282>`__.
For contributing please see `our contributing guide <https://graphql-compiler.readthedocs.io/en/latest/about/contributing.html>`__.

Example
~~~~~~~

Even though this example specifically targets a SQL database, it is meant to be a generic end-to-end
example of how to use the GraphQL compiler.

.. HACK: To avoid duplicating the end-to-end SQL example, we use the `include` restructured text
         directive. We add the comments below to mark the start and end of the text that the
         `include` directive has to copy. An alternative here would be to add an examples directory
         and "include" the examples from there in both the README and ReadTheDocs. However, github
         does not support the `include` directive: https://github.com/github/markup/issues/172

.. end-to-end-sql-example-start

.. code:: python

    from graphql_compiler import get_sqlalchemy_schema_info, graphql_to_sql
    from sqlalchemy import MetaData, create_engine

    engine = create_engine('<connection string>')

    # Reflect the default database schema. Each table must have a primary key. Otherwise see:
    # https://graphql-compiler.readthedocs.io/en/latest/supported_databases/sql.html#including-tables-without-explicitly-enforced-primary-keys
    metadata = MetaData(bind=engine)
    metadata.reflect()

    # Wrap the schema information into a SQLAlchemySchemaInfo object.
    sql_schema_info = get_sqlalchemy_schema_info(metadata.tables, {}, engine.dialect)

    # Write GraphQL query.
    graphql_query = '''
    {
        Animal {
            name @output(out_name: "animal_name")
        }
    }
    '''
    parameters = {}

    # Compile and execute query.
    compilation_result = graphql_to_sql(sql_schema_info, graphql_query, parameters)
    query_results = [dict(row) for row in engine.execute(compilation_result.query)]

.. end-to-end-sql-example-end

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
