# Copyright 2018-present Kensho Technologies, LLC.
from graphql import GraphQLString
import six
from sqlalchemy import text

from ... import CompilationResult, OutputMetadata, graphql_to_match
from ...compiler import SQL_LANGUAGE


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


def compile_and_run_match_query(schema, graphql_query, parameters, graph_client):
    """Compiles and runs a MATCH query against the supplied graph client."""
    compilation_result = graphql_to_match(schema, graphql_query, parameters)
    query = compilation_result.query
    results = [row.oRecordData for row in graph_client.command(query)]
    return results


def compile_and_run_sql_query(schema, graphql_query, parameters, engine):
    """Compiles and runs a SQL query against the supplied SQL backend."""
    # TODO: un-mock the SQL compilation once the SQL backend can run queries.
    def mock_sql_compilation(schema, graphql_query, parameters, compiler_metadata):
        """Mock out SQL backend compilation for unimplemented SQL backend."""
        mock_compilation_result = CompilationResult(
            query=text('SELECT name AS animal_name FROM animal'),
            language=SQL_LANGUAGE,
            input_metadata={},
            output_metadata={'animal_name': OutputMetadata(GraphQLString, False)}
        )
        return mock_compilation_result

    compilation_result = mock_sql_compilation(schema, graphql_query, parameters, None)
    query = compilation_result.query
    results = []
    connection = engine.connect()
    with connection.begin() as trans:
        for result in connection.execute(query):
            results.append(dict(result))
        trans.rollback()
    return results
