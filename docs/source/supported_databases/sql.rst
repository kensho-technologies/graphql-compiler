SQL
===

Relational databases are supported by compiling to SQLAlchemy core as an intermediate
language, and then relying on SQLAlchemy's compilation of the dialect-specific SQL query. The
compiler does not return a string for SQL compilation, but instead a SQLAlchemy :code:`Query`
object that can be executed through a SQLAlchemy `engine
<https://docs.sqlalchemy.org/en/latest/core/engines.html>`__.

Our SQL backend supports basic traversals, filters, tags and outputs, but there are still some
pieces in development:

- Directives: :code:`@fold`
- Filter operators: :code:`has_edge_degree`
- Dialect-specific features, like Postgres array types, and use of filter operators
  specific to them: :code:`contains`, :code:`intersects`, :code:`name_or_alias`
- Meta fields: :code:`__typename`, :code:`_x_count`

End-to-End SQL Example
----------------------

To query a SQL backend simply reflect the needed schema data from the database using SQLAlchemy,
compile the GraphQL query to a SQLAlchemy :code:`Query`, and execute the query against the engine
as in the example below:

.. code:: python

    from graphql_compiler import get_sql_schema_info, graphql_to_sql
    from sqlalchemy import MetaData, create_engine

    engine = create_engine('<connection string>')

    # Reflect the default database schema. Each table must have a primary key.
    # See "Including tables without explicitly enforced primary keys" otherwise.
    metadata = MetaData(bind=engine)
    metadata.reflect()

    # Wrap the schema information into a SQLSchemaInfo object.
    sql_schema_info = get_sql_schema_info(metadata.tables, {}, engine.dialect)

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

Advanced Features
-----------------

SQL Edges
~~~~~~~~~

Edges can be specified in SQL through the :code:`direct_edges` parameter as illustrated
below. SQL edges gets rendered as :code:`out_edgeName` and :code:`in_edgeName` in the source and
destination GraphQL objects respectively and edge traversals get compiled to SQL joins between the
source and destination tables using the specified columns. We use the term :code:`direct_edges`
below since the compiler may support other types of SQL edges in the future such as edges that are
backed by SQL `association tables <https://en.wikipedia.org/wiki/Associative_entity>`__.

.. code:: python

    from graphql_compiler import get_sql_schema_info, graphql_to_sql
    from graphql_compiler.schema_generation.sqlalchemy.edge_descriptors import DirectEdgeDescriptor
    from sqlalchemy import MetaData, create_engine

    # Set engine and reflect database metadata. (See example above for more details).
    engine = create_engine('<connection string>')
    metadata = MetaData(bind=engine)
    metadata.reflect()

    # Specify SQL edges.
    direct_edges = {
        'Animal_LivesIn': DirectEdgeDescriptor(
            from_vertex='Animal',  # Name of the source GraphQL object as specified.
            from_column='location',  # Name of the column of the underlying source table to join on.
            to_vertex='Location',  # Name of the destination GraphQL object as specified.
            to_column='uuid',   # Name of the column of the underlying destination table to join on.
         )
    }

    # Wrap the schema information into a SQLSchemaInfo object.
    sql_schema_info = get_sql_schema_info(metadata.tables, direct_edges, engine.dialect)

    # Write GraphQL query with edge traversal.
    graphql_query = '''
    {
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_LivesIn {
                name @output(out_name: "location_name")
            }
        }
    }
    '''

    # Compile query. Note that the edge traversal gets compiled to a SQL join.
    compilation_result = graphql_to_sql(sql_schema_info, graphql_query, {})


Including tables without explicitly enforced primary keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The compiler requires that each SQLAlchemy :code:`Table` object in the :code:`SQLALchemySchemaInfo`
has a primary key. However, the primary key in the :code:`Table` need not be the primary key in
the underlying table. It may simply be a non-null and unique identifier of each row. To override
the primary key of SQLAlchemy :code:`Table` objects reflected from a database please follow the
instructions in `this link
<https://docs.sqlalchemy.org/en/13/core/reflection.html#overriding-reflected-columns>`__.

Including tables from multiple schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SQLAlchemy and SQL database management systems support the concept of multiple `schemas
<https://docs.sqlalchemy.org/en/13/core/metadata.html?highlight=schema#specifying-the-schema-name>`__.
One can include :code:`Table` objects from multiple schemas in the same
:code:`SQLSchemaInfo`. However, when doing so, one cannot simply use table names as
GraphQL object names because two tables in different schemas can have the
same the name. A solution that is not quite guaranteed to work, but will likely work in practice
is to prepend the schema name as follows:

.. code:: python

    vertex_name_to_table = {}
    for table in metadata.values():
        # The schema field may be None if the database name is specified in the connection string
        # and the table is in the default schema, (e.g. 'dbo' for mssql and 'public' for postgres).
        if table.schema:
            vertex_name = 'dbo' + table.name
        else:
            # If the database name is not specified in the connection string, then
            # the schema field is of the form <databaseName>.<schemaName>.
            # Since dots are not allowed in GraphQL type names we must remove them here.
            vertex_name = table.schema.replace('.', '') + table.name

        if vertex_name in vertex_name_to_table:
            raise AssertionError('Found two tables with conflicting GraphQL object names.')

        vertex_name_to_table[vertex_name] = table

Including manually defined :code:`Table` objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :code:`Table` objects in the :code:`SQLSchemaInfo` do not need to be reflected from the
database. They also can be manually specified as in `this link
<https://docs.sqlalchemy.org/en/13/core/metadata.html#creating-and-dropping-database-tables>`__.
However, if specifying :code:`Table` objects manually, please make sure to include a primary key
for each table and to use only SQL types allowed for the dialect specified in the
:code:`SQLSchemaInfo`.
