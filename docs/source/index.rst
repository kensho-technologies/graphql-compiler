GraphQL compiler
================

.. EDUCATIONAL: The toctree (Table Of Contents Tree) specifies the table of contents at the left
   side of the page. The maxdepth indicates which headers to include in the table of contents.
   :hidden: specifies not to include a table of contents in this page.

.. ISSUE: Tree doesn't include subsections for `self` in toctree.
          https://github.com/sphinx-doc/sphinx/issues/2103

.. TODO: Solve the issue above. There a number of ways to solve this. Each solution has its pros
         and cons:
         -  One way is to separate this document into a landing page, (the page you get when
            clicking the logo at the top left side), and a "Getting Started" which could be the top
            page in the table of contents. That way at least the "Getting Started" page would
            have its subsections included in the table of contents navigational bar at the left.
            I personally prefer the concept of one "Home" page so I am not completely in favor of
            this solution.
         -  Another way is to write "Home <index>" instead of "Home <self>". This is a hack
            that fixes the issue, but leads to some error messages that will be confusing for
            GraphQL compiler Readthedocs contributors.

.. toctree::
   :hidden:

   Home <self>

.. EDUCATIONAL: The meta field below is for search engine optimization.
.. meta::
   :description: Turn complex GraphQL queries into optimized database queries.
   :keywords: graphql compiler, database, orientdb, sql

GraphQL compiler is a library that simplifies data querying and exploration by exposing one
simple query language to target multiple database backends. The query language is:

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

.. _getting-started:

Getting Started
---------------

Generating the necessary schema info
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

..  TODO: Encapsulate all schema info in a SchemaInfo class.

To use GraphQL compiler the first thing one needs to do is to generate the schema info from the
underlying database as in the example below. Even though the example targets an OrientDB
database, it is meant as a generic schema info generation example. See the homepage of your target
database for more instructions on how to generate the necessary schema info.

.. code:: python

    from graphql_compiler import (
        get_graphql_schema_from_orientdb_schema_data
    )
    from graphql_compiler.schema_generation.orientdb.utils import ORIENTDB_SCHEMA_RECORDS_QUERY

    client = your_function_that_returns_a_pyorient_client()
    schema_records = client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
    schema_data = [record.oRecordData for record in schema_records]
    schema, type_equivalence_hints = get_graphql_schema_from_orientdb_schema_data(schema_data)

.. TODO: Add a more precise link for type equivalence hints once the schema types section is ready.

In the snippet above the are two pieces of schema info:

- :code:`schema` which represents the database using GraphQL's type system.
- :code:`type_equivalence_hints` which helps deal with GraphQL's lack of concrete inheritance,
  (see :doc:`schema types <language_specification/schema_types>` for more info).

When compiling, these will need to be bundled in a :code:`CommonSchemaInfo` object.

Besides representing the database schema, a GraphQL schema includes other metadata such as a list
of custom scalar types used by the compiler. We'll talk more about this metadata in
:doc:`schema types <language_specification/schema_types>`. For now let's focus on how a database
schema might be represented in a GraphQL schema:

.. code::

    type Animal {
        name: String
        out_Animal_LivesIn: [Continent]
    }

    type Continent {
        name: String
        in_AnimalLivesIn: [Animal]
    }

In the GraphQL schema above:

- :code:`Animal` represents a concrete, (non-abstract), vertex type. For relational databases, we
  think of tables as the concrete vertex types.
- :code:`name` is a **property field** which represents a property of the :code:`Animal` vertex
  type. Think of property fields as leaf fields that represent concrete data.
- :code:`out_Animal_LivesIn` is a **vertex field** which represents an outbound edge to a vertex
  type in the graph. For graph databases, edges can be automatically generated from the database
  schema. However, for relational databases, edges currently have to be manually specified. See
  :doc:`SQL <supported_databases/sql>` for more information.

Query Compilation and Execution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once we have the schema info we can write the following query to get the names of all the animals
that live in Africa:

.. code:: python

    graphql_query = """
    {
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_LivesIn {
                name @filter(op_name: "=", value: ["$continent"])
            }
        }
    }
    """
    parameters = {'continent': 'Africa'}

There are a couple of things to notice about queries:

- All queries start with a vertex type, (e.g. :code:`Animal`), and expand to other vertex types
  using vertex fields.
- **Directives** specify the semantics of a query. :code:`@output` indicates the properties whose
  values should be returned. :code:`@filter` specifies a filter operation.

Finally, with the GraphQL query and its parameters at hand, we can use the compiler to obtain a
query that we can directly execute against OrientDB.

.. code:: python

    from graphql_compiler import graphql_to_match

    compilation_result = graphql_to_match(
        schema, graphql_query, parameters, type_equivalence_hints)

    # Executing query assuming a pyorient client. Other clients may have a different interface.
    print([result.oRecordData for result in client.query(query)])
    # [{'animal_name': 'Elephant'}, {'animal_name': 'Lion'}, ...]

Features
--------

Language Specification
~~~~~~~~~~~~~~~~~~~~~~

.. TODO: We might want to get rid of the definitions section and introduce the terms more
         naturally.

To learn more about the language specification see:

- :doc:`Definitions <language_specification/definitions>`, for the definitions of key terms that we
  use to define the language.
- :doc:`Schema Types <language_specification/schema_types>`, for information about the full
  breadth of schema types that we use to represent database schemas and how to interact
  with them using GraphQL queries.
- :doc:`Query Directives <language_specification/query_directives>`, to learn more about the
  available directives and how to use them to create powerful queries.

.. toctree::
   :caption: Language Specification
   :hidden:

   Definitions <language_specification/definitions>
   Schema Types <language_specification/schema_types>
   Query Directives <language_specification/query_directives>

Supported Databases
~~~~~~~~~~~~~~~~~~~

Refer to this section to learn how the compiler integrates with the target database. The database
home pages include an end-to-end example, instruction for schema info generation, and any
limitations or intricacies related to working with said database. We currently support two
types of database backends:

- :doc:`OrientDB <supported_databases/orientdb>`
- :doc:`SQL Databases <supported_databases/sql>`, including SQL Server, Postgres and more.
- :doc:`Neo4j/Redisgraph <supported_databases/neo4j_and_redisgraph>`

.. toctree::
   :caption: Supported Databases
   :hidden:

   OrientDB <supported_databases/orientdb>
   SQL <supported_databases/sql>
   Neo4j/Redisgraph <supported_databases/neo4j_and_redisgraph>

Advanced Features
~~~~~~~~~~~~~~~~~

To learn more about the advanced features in the GraphQL compiler see:

- :doc:`Macro System <advanced_features/macro_system>` to learn how to write "macro edges",
  which allow users to define new edges that become part of the GraphQL schema, using existing
  edges as building blocks.
- :doc:`Schema Graph <advanced_features/schema_graph>` for an utility that makes it
  easy to explore the schema of a database, including the databases indexes.
- :doc:`Additional Tools <advanced_features/additional_tools>` for a list of additional tools
  included in the package, including a query pretty printer.

.. toctree::
   :caption: Advanced Features
   :hidden:

   Macro System <advanced_features/macro_system>
   Schema Graph <advanced_features/schema_graph>
   Additional Tools <advanced_features/additional_tools>

About GraphQL compiler
~~~~~~~~~~~~~~~~~~~~~~

To learn more about the GraphQL compiler project see:

- :doc:`Contributing <about/contributing>` for instructions on how you can contribute.
- :doc:`Code of Conduct <about/code_of_conduct>` for the contributor code of conduct.
- :doc:`Changelog <about/changelog>` for a history of changes.
- :doc:`FAQ <about/faq>` for a list of frequently asked questions.
- :doc:`Execution Model <about/execution_model>` to learn more about the design principles guiding
  the development of the compiler and the guarantees the compiler provides.

.. toctree::
   :caption: About GraphQL compiler
   :hidden:

   Contributing <about/contributing>
   Code of Conduct <about/code_of_conduct>
   Changelog <about/changelog>
   FAQ <about/faq>
   Execution Model <about/execution_model>
