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
        raise AssertionError(u'Argument collection was expected to be a {}, but was a {}.'
                             .format(sqlalchemy.sql.elements.BindParameter, type(collection)))
    if not isinstance(element, sqlalchemy.sql.schema.Column):
        raise AssertionError(u'Argument element was expected to be a {}, but was a {}.'
                             .format(sqlalchemy.sql.schema.Column, type(element)))

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
        raise AssertionError(u'Argument collection was expected to be a {}, but was a {}.'
                             .format(sqlalchemy.sql.elements.BindParameter, type(collection)))
    if not isinstance(element, sqlalchemy.sql.schema.Column):
        raise AssertionError(u'Argument element was expected to be a {}, but was a {}.'
                             .format(sqlalchemy.sql.schema.Column, type(element)))

    return element.notin_(collection)
