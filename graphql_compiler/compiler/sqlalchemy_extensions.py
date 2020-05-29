# Copyright 2019-present Kensho Technologies, LLC.
import sqlalchemy


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

    class BindparamCompiler(dialect.statement_compiler):
        def visit_bindparam(self, bindparam, **kwargs):
            # A bound parameter with name param is represented as ":param". However,
            # if the parameter is expanding (list-valued) it is represented as
            # "([EXPANDING_param])" by default. This is an internal sqlalchemy
            # representation that is not understood by databases, so we explicitly
            # make sure to print it as ":param".
            bindparam.expanding = False
            return super(BindparamCompiler, self).visit_bindparam(bindparam, **kwargs)

    return str(BindparamCompiler(dialect, query).process(query))
