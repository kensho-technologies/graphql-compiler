The GraphQL Compiler
====================

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
            GraphQL Compiler Readthedocs contributors.

.. toctree::
   :maxdepth: 2
   :hidden:

   Home <self>

.. EDUCATIONAL: The meta field below is for search engine optimization.
.. meta::
   :description: Turn complex GraphQL queries into optimized database queries.
   :keywords: graphql compiler, database, orientdb, sql

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

Designed for cross-database querying
   Since the query language always has the same semantics regardless of the underlying database,
   we have been able to build a :doc:`schema stitching <advanced_features/schema_stitching>` system
   that allows for seamless cross-database querying.

.. _getting-started:

Getting Started
---------------

Generating the necessary schema info
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

..  TODO: Encapsulate all schema info in a SchemaInfo class.

To use the GraphQL compiler the first thing one needs to do is to generate the schema info from the
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
  (see :doc:`schema types <core_specification/schema_types>` for more info).

Besides representing the database schema, a GraphQL schema includes other metadata such as a list
of custom scalar types used by the compiler. We'll talk more about this metadata in
:doc:`schema types <core_specification/schema_types>`. For now let's focus on how a database
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
  :doc:`SQL <databases/sql>` for more information.

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

Core Specification
~~~~~~~~~~~~~~~~~~

.. TODO: We might want to get rid of the definitions section and introduce the terms more
         naturally.

To learn more about the core specification of the GraphQL query language see:

- :doc:`Definitions <core_specification/definitions>`, for the definitions of key terms that we
  use to define the language.
- :doc:`Schema Types <core_specification/schema_types>`, for information about the full
  breadth of schema types that we use to represent database schemas and how to interact
  with them using GraphQL queries.
- :doc:`Query Directives <core_specification/query_directives>`, to learn more about the
  available directives and how to use them to create powerful queries.

.. toctree::
   :maxdepth: 2
   :caption: Core Specification
   :hidden:

   Definitions <core_specification/definitions>
   Schema Types <core_specification/schema_types>
   Query Directives <core_specification/query_directives>

Databases
~~~~~~~~~

Refer to this section to learn how the compiler integrates with the target database. The database
home pages include an end-to-end example, instruction for schema info generation, and any
limitations or intricacies related to working with said database. We currently support two
types of database backends:

- :doc:`OrientDB <databases/orientdb>`
- :doc:`SQL Databases <databases/sql>`, including SQL Server, Postgres and more.

.. toctree::
   :maxdepth: 2
   :caption: Databases
   :hidden:

   OrientDB <databases/orientdb>
   SQL <databases/sql>

Advanced Features
~~~~~~~~~~~~~~~~~

To learn more about the advanced features in the GraphQL compiler see:

- :doc:`Macro System <advanced_features/macro_system>`, to learn how to write "macro edges",
  which allow users to define new edges that become part of the GraphQL schema, using existing
  edges as building blocks.
- :doc:`Schema Stitching <advanced_features/schema_stitching>`, to learn how to stitch-schemas
  together and execute cross-database queries.
- :doc:`Schema Transformations <advanced_features/schema_transformations>`, to learn how to
  rename objects and prevent schema collisions when stitching schemas.
- :doc:`Schema Graph <advanced_features/schema_graph>`, for an utility that makes it
  easy to explore the schema of a database, including the databases indexes.

.. toctree::
   :maxdepth: 2
   :caption: Advanced Features
   :hidden:

   Macro System <advanced_features/macro_system>
   Schema Stitching <advanced_features/schema_stitching>
   Schema Transformations <advanced_features/schema_transformations>
   Schema Graph <advanced_features/schema_graph>
