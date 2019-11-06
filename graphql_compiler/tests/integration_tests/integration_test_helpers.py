# Copyright 2018-present Kensho Technologies, LLC.
from decimal import Decimal

import six

from ... import graphql_to_match, graphql_to_redisgraph_cypher, graphql_to_sql
from ...compiler import compile_graphql_to_cypher


def sort_db_results(results):
    """Deterministically sort DB results.

    Args:
        results: List[Dict], results from a DB.

    Returns:
        List[Dict], sorted DB results.
    """
    sort_order = []
    if len(results) > 0:
        sort_order = sorted(six.iterkeys(results[0]))

    def sort_key(result):
        """Convert None/Not None to avoid comparisons of None to a non-None type."""
        return tuple((result[col] is not None, result[col]) for col in sort_order)

    def sorted_value(value):
        """Return a sorted version of a value, if it is a list."""
        if isinstance(value, list):
            return sorted(value)
        return value

    return sorted([
        {k: sorted_value(v) for k, v in six.iteritems(row)}
        for row in results
    ], key=sort_key)


def try_convert_decimal_to_string(value):
    """Return Decimals as string if value is a Decimal, return value otherwise."""
    if isinstance(value, list):
        return [try_convert_decimal_to_string(subvalue) for subvalue in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def compile_and_run_match_query(schema, graphql_query, parameters, orientdb_client):
    """Compile and run a MATCH query against the supplied graph client."""
    # MATCH code emitted by the compiler expects Decimals to be passed in as strings
    converted_parameters = {
        name: try_convert_decimal_to_string(value)
        for name, value in six.iteritems(parameters)
    }
    compilation_result = graphql_to_match(schema, graphql_query, converted_parameters)

    # Get results, adding None for optional columns with no matches
    query = compilation_result.query
    results = []
    for row in orientdb_client.command(query):
        row_dict = row.oRecordData
        for output_name in compilation_result.output_metadata:
            if output_name not in row_dict:
                row_dict[output_name] = None
        results.append(row.oRecordData)
    return results


def compile_and_run_sql_query(sql_schema_info, graphql_query, parameters, engine):
    """Compile and run a SQL query against the supplied SQL backend."""
    compilation_result = graphql_to_sql(sql_schema_info, graphql_query, parameters)
    query = compilation_result.query
    results = []
    for result in engine.execute(query):
        results.append(dict(result))
    return results


def compile_and_run_neo4j_query(schema, graphql_query, parameters, neo4j_client):
    """Compile and run a Cypher query against the supplied graph client."""
    compilation_result = compile_graphql_to_cypher(
        schema, graphql_query, type_equivalence_hints=None)
    query = compilation_result.query
    with neo4j_client.driver.session() as session:
        results = session.run(query, parameters)
    return results.data()


def compile_and_run_redisgraph_query(schema, graphql_query, parameters, redisgraph_client):
    """Compile and run a Cypher query against the supplied graph client."""
    compilation_result = graphql_to_redisgraph_cypher(schema, graphql_query, parameters)
    query = compilation_result.query
    result_set = redisgraph_client.query(query).result_set

    # result_set is a list containing two items. The first is a list of property names that a
    # given query returns (roughly analogous to the names of the columns returned by a SQL query)
    # and the second is the returned data itself.
    #
    # result_set formatting for this version of RedisGraph (version 1.2.2) can be found here [0]
    # Note this differs from the official documentation on the Redis Labs website [1] because the
    # docs on the website are for the newer version 1.9.9 [2]. We expect a new version to be
    # released in Q3 2019.
    #
    # [0] https://github.com/RedisGraph/RedisGraph/blob/v1.2.2/docs/design.md#querying-the-graph
    # [1] https://oss.redislabs.com/redisgraph/result_structure/
    # [2] https://github.com/RedisGraph/RedisGraph/issues/557
    column_names = result_set[0]
    records = result_set[1:]

    # redisgraph gives us back bytes, but we want strings.
    decoded_column_names = [column_name.decode('utf-8') for column_name in column_names]
    decoded_records = []
    for record in records:
        # decode if bytes, leave alone otherwise. For more info see here:
        # https://oss.redislabs.com/redisgraph/result_structure/#top-level-members
        decoded_record = [
            field.decode('utf-8') if type(field) in (bytes, bytearray) else field
            for field in record
        ]
        decoded_records.append(decoded_record)
    result = [dict(zip(decoded_column_names, record)) for record in decoded_records]
    return result
