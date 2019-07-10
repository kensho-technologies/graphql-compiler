# Copyright 2018-present Kensho Technologies, LLC.
from decimal import Decimal

import six

from ... import graphql_to_cypher_redisgraph, graphql_to_cypher_neo4j, graphql_to_match, graphql_to_sql
from ...compiler.ir_lowering_sql.metadata import SqlMetadata


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

    return sorted(results, key=sort_key)


def try_convert_decimal_to_string(value):
    """Return Decimals as string if value is a Decimal, return value otherwise."""
    if isinstance(value, list):
        return [try_convert_decimal_to_string(subvalue) for subvalue in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def compile_and_run_match_query(schema, graphql_query, parameters, orientdb_client):
    """Compiles and runs a MATCH query against the supplied graph client."""
    # MATCH code emitted by the compiler expects Decimals to be passed in as strings
    converted_parameters = {
        name: try_convert_decimal_to_string(value)
        for name, value in six.iteritems(parameters)
    }
    compilation_result = graphql_to_match(schema, graphql_query, converted_parameters)

    query = compilation_result.query
    results = [row.oRecordData for row in orientdb_client.command(query)]
    return results


def compile_and_run_sql_query(schema, graphql_query, parameters, engine, metadata):
    """Compiles and runs a SQL query against the supplied SQL backend."""
    dialect_name = engine.dialect.name
    sql_metadata = SqlMetadata(dialect_name, metadata)
    compilation_result = graphql_to_sql(schema, graphql_query, parameters, sql_metadata, None)
    query = compilation_result.query
    results = []
    connection = engine.connect()
    with connection.begin() as trans:
        for result in connection.execute(query):
            results.append(dict(result))
        trans.rollback()
    return results


def compile_and_run_neo4j_query(schema, graphql_query, parameters, neo4j_client):
    """Compiles and runs a Cypher query against the supplied graph client."""
    converted_parameters = {
        name: try_convert_decimal_to_string(value)
        for name, value in six.iteritems(parameters)
    }
    compilation_result = graphql_to_cypher_neo4j(schema, graphql_query, converted_parameters)
    query = compilation_result.query
    with neo4j_client.driver.session() as session:
        results = session.run(query, parameters)
    return results.data()


def compile_and_run_redisgraph_query(schema, graphql_query, parameters, redisgraph_client):
    """Compiles and runs a Cypher query against the supplied graph client."""
    converted_parameters = {
        name: try_convert_decimal_to_string(value)
        for name, value in six.iteritems(parameters)
    }
    compilation_result = graphql_to_cypher_redisgraph(schema, graphql_query, converted_parameters)
    query = compilation_result.query
    query = query.replace('CYPHER 3.5', '') # TODO Leon: hack-- need to remove version number
    result_set = redisgraph_client.query(query).result_set
    # redisgraph gives us back bytes, but we want strings.
    column_names = [column_name.decode('utf-8') for column_name in result_set[0]]
    rows = [[row_item.decode('utf-8') if type(row_item) in (bytes, bytearray) else row_item for row_item in row]
            for row in result_set[1:]] # decode the strings, leave the rest.
    # rows = [[row_item.decode('utf-8') for row_item in row] for row in result_set[1:]]
    # rows = result_set[1:]
    result = [dict(zip(column_names, row)) for row in rows]
    return result
