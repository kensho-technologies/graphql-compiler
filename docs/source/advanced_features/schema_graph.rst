Schema Graph
============

When building a GraphQL schema from the database metadata, we first
build a :code:`SchemaGraph` from the metadata and then, from the
:code:`SchemaGraph`, build the GraphQL schema. The :code:`SchemaGraph` is also a
representation of the underlying database schema, but it has three main
advantages that make it a more powerful schema introspection tool:

1. It's able to store and expose a schema's index information. The interface for accessing index
   information is provisional though and might change in the near future.
2. Its classes are  allowed to inherit from non-abstract classes.
3. It exposes many utility functions, such as :code:`get_subclass_set`, that make it easier to
   explore the schema.

See below for a mock example of how to build and use the
:code:`SchemaGraph`:

.. code:: python

    from graphql_compiler.schema_generation.orientdb.schema_graph_builder import (
        get_orientdb_schema_graph
    )
    from graphql_compiler.schema_generation.orientdb.utils import (
        ORIENTDB_INDEX_RECORDS_QUERY, ORIENTDB_SCHEMA_RECORDS_QUERY
    )

    # Get schema metadata from hypothetical Animals database.
    client = your_function_that_returns_a_pyorient_client()
    schema_records = client.command(ORIENTDB_SCHEMA_RECORDS_QUERY)
    schema_data = [record.oRecordData for record in schema_records]

    # Get index data.
    index_records = client.command(ORIENTDB_INDEX_RECORDS_QUERY)
    index_query_data = [record.oRecordData for record in index_records]

    # Build SchemaGraph.
    schema_graph = get_orientdb_schema_graph(schema_data, index_query_data)

    # Get all the subclasses of a class.
    print(schema_graph.get_subclass_set('Animal'))
    # {'Animal', 'Dog'}

    # Get all the outgoing edge classes of a vertex class.
    print(schema_graph.get_vertex_schema_element_or_raise('Animal').out_connections)
    # {'Animal_Eats', 'Animal_FedAt', 'Animal_LivesIn'}

    # Get the vertex classes allowed as the destination vertex of an edge class.
    print(schema_graph.get_edge_schema_element_or_raise('Animal_Eats').out_connections)
    # {'Fruit', 'Food'}

    # Get the superclass of all classes allowed as the destination vertex of an edge class.
    print(schema_graph.get_edge_schema_element_or_raise('Animal_Eats').base_out_connection)
    # Food

    # Get the unique indexes defined on a class.
    print(schema_graph.get_unique_indexes_for_class('Animal'))
    # [IndexDefinition(name='uuid', 'base_classname'='Animal', fields={'uuid'}, unique=True, ordered=False, ignore_nulls=False)]

We currently support :code:`SchemaGraph` auto-generation for both OrientDB and SQL database
backends. In the future, we plan to add a mechanism where one can query a :code:`SchemaGraph` using
GraphQL queries.
