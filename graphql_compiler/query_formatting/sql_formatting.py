# Copyright 2018-present Kensho Technologies, LLC.
from ..compiler.common import SQL_LANGUAGE


######
# Public API
######


def insert_arguments_into_sql_query(compilation_result, arguments):
    """Insert the arguments into the compiled SQL query to form a complete query.

    Args:
        compilation_result: CompilationResult, compilation result from the GraphQL compiler.
        arguments: Dict[str, Any], parameter name -> value, for every parameter the query expects.

    Returns:
        SQLAlchemy Selectable, a executable SQL query with parameters bound.
    """
    if compilation_result.language != SQL_LANGUAGE:
        raise AssertionError("Unexpected query output language: {}".format(compilation_result))
    base_query = compilation_result.query
    return base_query.params(**arguments)


######
