# Copyright 2018-present Kensho Technologies, LLC.
from decimal import Decimal
from typing import Any, Dict, List, Tuple, TypeVar, Union

from pyorient.orient import OrientDB
from redisgraph.client import Graph
import six
from sqlalchemy.engine.base import Engine

from ... import graphql_to_match, graphql_to_redisgraph_cypher, graphql_to_sql
from ...compiler import compile_graphql_to_cypher, compile_graphql_to_sql
from ...compiler.compiler_frontend import OutputMetadata
from ...compiler.sqlalchemy_extensions import (
    bind_parameters_to_query_string,
    materialize_result_proxy,
    print_sqlalchemy_query_string,
)
from ...schema.schema_info import CommonSchemaInfo, SQLAlchemySchemaInfo
from ..test_data_tools.neo4j_graph import Neo4jClient


T = TypeVar("T")


def sort_db_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deterministically sort DB results.

    Args:
        results: List[Dict], results from a DB.

    Returns:
        List[Dict], sorted DB results.
    """
    sort_order: List[str] = []
    if len(results) > 0:
        sort_order = sorted(six.iterkeys(results[0]))

    def sort_key(result: Dict[str, Any]) -> Tuple[Tuple[bool, Any], ...]:
        """Convert None/Not None to avoid comparisons of None to a non-None type."""
        return tuple((result[col] is not None, result[col]) for col in sort_order)

    def sorted_value(value: T) -> Union[List[Any], T]:
        """Return a sorted version of a value, if it is a list."""
        if isinstance(value, list):
            return sorted(value)
        return value

    return sorted(
        [{k: sorted_value(v) for k, v in six.iteritems(row)} for row in results], key=sort_key
    )


def try_convert_decimal_to_string(value: T) -> Any:
    """Return Decimals as string if value is a Decimal, return value otherwise."""
    if isinstance(value, list):
        return [try_convert_decimal_to_string(subvalue) for subvalue in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def compile_and_run_match_query(
    common_schema_info: CommonSchemaInfo,
    graphql_query: str,
    parameters: Dict[str, Any],
    orientdb_client: OrientDB,
) -> List[Dict[str, Any]]:
    """Compile and run a MATCH query against the supplied graph client."""
    # MATCH code emitted by the compiler expects Decimals to be passed in as strings
    converted_parameters = {
        name: try_convert_decimal_to_string(value) for name, value in six.iteritems(parameters)
    }
    compilation_result = graphql_to_match(common_schema_info, graphql_query, converted_parameters)

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


def _compile_print_and_run_sql_query(
    sql_schema_info: SQLAlchemySchemaInfo,
    graphql_query: str,
    parameters: Dict[str, Any],
    engine: Engine,
) -> List[Dict[str, Any]]:
    """Compile, print, bind the arguments, then execute the query."""
    compilation_result = compile_graphql_to_sql(sql_schema_info, graphql_query)
    printed_query = print_sqlalchemy_query_string(compilation_result.query, sql_schema_info.dialect)
    query_with_parameters = bind_parameters_to_query_string(
        printed_query, compilation_result.input_metadata, parameters
    )
    return materialize_result_proxy(engine.execute(query_with_parameters))


def compile_and_run_sql_query(
    sql_schema_info: SQLAlchemySchemaInfo,
    graphql_query: str,
    parameters: Dict[str, Any],
    engine: Engine,
) -> Tuple[List[Dict[str, Any]], Dict[str, OutputMetadata]]:
    """Compile and run a SQL query against the SQL engine, return result and output metadata."""
    compilation_result = graphql_to_sql(sql_schema_info, graphql_query, parameters)
    query = compilation_result.query
    results = materialize_result_proxy(engine.execute(query))

    # Check that when printed the query produces the same result
    printed_query_results = _compile_print_and_run_sql_query(
        sql_schema_info, graphql_query, parameters, engine
    )
    if sort_db_results(results) != sort_db_results(printed_query_results):
        raise AssertionError(
            f"Query {graphql_query} with args {parameters} produces different "
            f"results when the compiled SQL query is printed before execution."
        )

    # Output metadata is needed for MSSQL fold postprocessing.
    return results, compilation_result.output_metadata


def compile_and_run_neo4j_query(
    common_schema_info: CommonSchemaInfo,
    graphql_query: str,
    parameters: Dict[str, Any],
    neo4j_client: Neo4jClient,
) -> List[Dict[str, Any]]:
    """Compile and run a Cypher query against the supplied graph client."""
    compilation_result = compile_graphql_to_cypher(common_schema_info, graphql_query)
    query = compilation_result.query
    with neo4j_client.driver.session() as session:
        results = session.run(query, parameters)
    return results.data()


def compile_and_run_redisgraph_query(
    common_schema_info: CommonSchemaInfo,
    graphql_query: str,
    parameters: Dict[str, Any],
    redisgraph_client: Graph,
) -> List[Dict[str, Any]]:
    """Compile and run a Cypher query against the supplied graph client."""
    compilation_result = graphql_to_redisgraph_cypher(common_schema_info, graphql_query, parameters)
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
    decoded_column_names = [column_name.decode("utf-8") for column_name in column_names]
    decoded_records = []
    for record in records:
        # decode if bytes, leave alone otherwise. For more info see here:
        # https://oss.redislabs.com/redisgraph/result_structure/#top-level-members
        decoded_record = [
            field.decode("utf-8") if type(field) in (bytes, bytearray) else field
            for field in record
        ]
        decoded_records.append(decoded_record)
    result = [dict(zip(decoded_column_names, record)) for record in decoded_records]
    return result
