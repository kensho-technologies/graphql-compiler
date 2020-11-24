# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy
from typing import Any, Dict, List, Union

from graphql.type.definition import GraphQLList, GraphQLType
import sqlalchemy
from sqlalchemy.dialects.mssql.pyodbc import MSDialect_pyodbc
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.selectable import Select


def contains_operator(collection, element):
    """Return a sqlalchemy BinaryExpression representing this operator.

    Args:
        collection: sqlalchemy BindParameter, a collection runtime parameter
        element: sqlalchemy Column that needs to be in the specified collection

    Returns:
        sqlalchemy BinaryExpression
    """
    if not isinstance(collection, sqlalchemy.sql.elements.BindParameter):
        raise AssertionError(
            "Argument collection was expected to be a {}, but was a {}.".format(
                sqlalchemy.sql.elements.BindParameter, type(collection)
            )
        )
    if not isinstance(element, sqlalchemy.sql.schema.Column):
        raise AssertionError(
            "Argument element was expected to be a {}, but was a {}.".format(
                sqlalchemy.sql.schema.Column, type(element)
            )
        )

    return element.in_(collection)


def not_contains_operator(collection, element):
    """Return a sqlalchemy BinaryExpression representing this operator.

    Args:
        collection: sqlalchemy BindParameter, a collection runtime parameter
        element: sqlalchemy Column that needs to be in the specified collection

    Returns:
        sqlalchemy BinaryExpression
    """
    if not isinstance(collection, sqlalchemy.sql.elements.BindParameter):
        raise AssertionError(
            "Argument collection was expected to be a {}, but was a {}.".format(
                sqlalchemy.sql.elements.BindParameter, type(collection)
            )
        )
    if not isinstance(element, sqlalchemy.sql.schema.Column):
        raise AssertionError(
            "Argument element was expected to be a {}, but was a {}.".format(
                sqlalchemy.sql.schema.Column, type(element)
            )
        )

    return element.notin_(collection)


def print_sqlalchemy_query_string(
    query: Select, dialect: Union[PGDialect_psycopg2, MSDialect_pyodbc]
) -> str:
    """Return a string form of the parameterized query.

    Args:
        query: sqlalchemy.sql.selectable.Select
        dialect: currently only postgres and mssql are supported because we have no
                 tests for the others, but chances are that this function would still work.

    Returns:
        string that can be ran using sqlalchemy.sql.text(result)
    """

    # The parameter style is one of the following:
    # {
    #     "pyformat": "%%(%(name)s)s",
    #     "qmark": "?",
    #     "format": "%%s",
    #     "numeric": ":[_POSITION]",
    #     "named": ":%(name)s",
    # }
    #
    # We use the named parameter style since that's the only one
    # that the regex parser in the sqlalchemy TextClause object
    # understands.
    printing_dialect = copy(dialect)
    printing_dialect.paramstyle = "named"

    # Silencing mypy here since it can't infer the type of dialect.statement_compiler
    class BindparamCompiler(printing_dialect.statement_compiler):  # type: ignore  # noqa
        def visit_bindparam(self, bindparam, **kwargs):
            # A bound parameter with name param is represented as ":param". However,
            # if the parameter is expanding (list-valued) it is represented as
            # "([EXPANDING_param])" by default. This is an internal sqlalchemy
            # representation that is not understood by databases, so we explicitly
            # make sure to print it as ":param".
            bindparam.expanding = False
            return super(BindparamCompiler, self).visit_bindparam(bindparam, **kwargs)

    return str(BindparamCompiler(printing_dialect, query).process(query))


def bind_parameters_to_query_string(
    query: str, input_metadata: Dict[str, GraphQLType], parameters: Dict[str, Any]
) -> TextClause:
    """Assign values to query parameters."""
    bound_parameters = []
    for parameter_name, parameter_value in parameters.items():
        parameter_type = input_metadata[parameter_name]
        is_list = isinstance(parameter_type, GraphQLList)
        bound_parameters.append(
            sqlalchemy.bindparam(parameter_name, value=parameter_value, expanding=is_list)
        )

    return sqlalchemy.text(query).bindparams(*bound_parameters)


def materialize_result_proxy(result: sqlalchemy.engine.result.ResultProxy) -> List[Dict[str, Any]]:
    """Drain the results from a result proxy into a list of dicts represenation."""
    return [dict(row) for row in result]
