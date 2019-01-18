# Copyright 2018-present Kensho Technologies, LLC.
######
# Public API
######
from ..compiler.common import SQL_LANGUAGE


def insert_arguments_into_sql_query(compilation_result, arguments):
    """Insert the arguments into the compiled SQL query to form a complete query.

    Args:
        compilation_result: a CompilationResult object derived from the GraphQL compiler
        arguments: dict, mapping argument name to its value, for every parameter the query expects.

    Returns:
        SQLAlchemy Selectable, a SQL query with parameters bound.
    """
    if compilation_result.language != SQL_LANGUAGE:
        raise AssertionError(u'Unexpected query output language: {}'.format(compilation_result))
    base_query = compilation_result.query
    return base_query.params(**arguments)

######
