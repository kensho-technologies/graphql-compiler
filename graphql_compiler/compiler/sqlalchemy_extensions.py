# Copyright 2019-present Kensho Technologies, LLC.
import sqlalchemy
from sqlalchemy.dialects.mssql.pyodbc import MSDialect_pyodbc
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2


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


def print_sqlalchemy_query_string(query, dialect):
    """Return a string form of the parameterized query.

    Args:
        query: sqlalchemy.sql.selectable.Select
        dialect: sqlalchemy.engine.interfaces.Dialect

    Returns:
        string that can be ran using sqlalchemy.sql.text(result)
    """
    supported_dialects = (PGDialect_psycopg2, MSDialect_pyodbc)
    if isinstance(dialect, supported_dialects):
        class BindparamCompiler(dialect.statement_compiler):
            def visit_bindparam(self, bindparam, **kwargs):
                # A bound parameter with name param is represented as ":param". However,
                # if the parameter is expanding (list-valued) it is represented as
                # "([EXPANDING_param])" by default. This is an internal sqlalchemy
                # representation that is not understood by databases, so we explicitly
                # make sure to print it as ":param".
                return f":{bindparam.key}"

        return str(BindparamCompiler(dialect, query).process(query))
    else:
        raise AssertionError(f"Unsupported dialect {dialect}. "
                             f"Only {supported_dialects} are supported.")


def bind_parameters_to_query_string(query, parameters):
    bound_parameters = [
        sqlalchemy.bindparam(
            parameter_name,
            value=parameter_value,
            expanding=isinstance(parameter_value, (list, tuple)),
        )
        for parameter_name, parameter_value in parameters.items()
    ]

    return sqlalchemy.text(query).bindparams(*bound_parameters)
