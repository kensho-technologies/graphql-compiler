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


def print_sqlalchemy_query_string(statement, dialect):
    """
    Print a query, with values filled in for debugging purposes *only* for security, you should
    always separate queries from their values. Please also note that this function is quite slow.
    Inspiration from:
    https://stackoverflow.com/questions/5631078/sqlalchemy-print-the-actual-query/5698357
    """
    compiler = statement._compiler(dialect)
    class LiteralCompiler(compiler.__class__):
        def visit_bindparam(
                self, bindparam, within_columns_clause=False,
                literal_binds=False, **kwargs
        ):
            return self.render_literal_bindparam(
                    bindparam, within_columns_clause=within_columns_clause,
                    literal_binds=literal_binds, **kwargs
            )

        def render_literal_value(self, value, type_):
            if isinstance(value, (list, tuple)):
                return "(%s)" % (",".join([self.render_literal_value(x, type_) for x in value]))
            else:
                if value is None:
                    return 'NULL'
                elif isinstance(value, bool):
                    return '1' if value else '0'
                elif isinstance(value, (int, float, Decimal)):
                    return str(value)
                elif isinstance(value, str):
                    return "'%s'" % value.replace("'", "''")
                elif isinstance(value, datetime):
                    return "{ts '%04d-%02d-%02d %02d:%02d:%02d.%03d'}" % (
                        value.year, value.month, value.day,
                        value.hour, value.minute, value.second,
                        value.microsecond / 1000)
                elif isinstance(value, date):
                    return "{d '%04d-%02d-%02d'} " % (
                        value.year, value.month, value.day)
            return super(LiteralCompiler, self).render_literal_value(value, type_)

    compiler = LiteralCompiler(dialect, statement)
    return str(compiler.process(statement))
