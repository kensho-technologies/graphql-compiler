Neo4j/Redisgraph
================

.. important

    Documentation on how to use the compiler to target cypher-based database backends is still a
    work in progress.

Cypher query parameters
~~~~~~~~~~~~~~~~~~~~~~~

RedisGraph `doesn't support query
parameters <https://github.com/RedisGraph/RedisGraph/issues/544#issuecomment-507963576>`__,
so we perform manual parameter interpolation in the
:code:`graphql_to_redisgraph_cypher` function. However, for Neo4j, we can
use Neo4j's client to do parameter interpolation on its own so that we
don't reinvent the wheel.

The function :code:`insert_arguments_into_query` does so based on the query
language, which isn't fine-grained enough here-- for Cypher backends, we
only want to insert parameters if the backend is RedisGraph, but not if
it's Neo4j.

Instead, the correct approach for Neo4j Cypher is as follows, given a
Neo4j Python client called :code:`neo4j_client`:

.. code:: python

    common_schema_info = CommonSchemaInfo(schema, type_equivalence_hints)
    compilation_result = compile_graphql_to_cypher(common_schema_info, graphql_query)
    with neo4j_client.driver.session() as session:
        result = session.run(compilation_result.query, parameters)
