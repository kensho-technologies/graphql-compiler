# Copyright 2018-present Kensho Technologies, LLC.
from decimal import Decimal

import six

from ... import graphql_to_match, graphql_to_sql
from ...compiler.ir_lowering_sql.metadata import SqlMetadata
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER, BIT
from ...compiler.helpers import GraphQLCompilationError
from datetime import date, datetime
from sqlalchemy.dialects import mssql


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


def compile_and_run_match_query(schema, graphql_query, parameters, graph_client):
    """Compiles and runs a MATCH query against the supplied graph client."""
    # MATCH code emitted by the compiler expects Decimals to be passed in as strings
    converted_parameters = {
        name: try_convert_decimal_to_string(value)
        for name, value in six.iteritems(parameters)
    }
    compilation_result = graphql_to_match(schema, graphql_query, converted_parameters)

    query = compilation_result.query
    results = [row.oRecordData for row in graph_client.command(query)]
    return results


def compile_and_run_sql_query(schema, graphql_query, parameters, engine, sql_metadata):
    """Compiles and runs a SQL query against the supplied SQL backend."""
    dialect_name = engine.dialect.name
    compilation_result = graphql_to_sql(schema, graphql_query, parameters, sql_metadata, None)
    query = compilation_result.query
    results_with_query_string = []
    results_with_sqlalchemy_clause = []
    connection = engine.connect()
    with connection.begin() as trans:
        for result in connection.execute(printquery(query.params(parameters), mssql.dialect())):
            results_with_query_string.append(dict(result))
        for result in connection.execute(results_with_sqlalchemy_clause, parameters):
            results_with_sqlalchemy_clause.append(dict(result))
        trans.rollback()
    if results_with_query_string != results_with_sqlalchemy_clause:
        raise AssertionError('Expected results of query executed a string and as a ClauseElement '
                             'to be the same.')
    return results_with_query_string


def printquery(statement, dialect):
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
            return super(LiteralCompiler, self).render_literal_bindparam(
                    bindparam, within_columns_clause=within_columns_clause,
                    literal_binds=literal_binds, **kwargs
            )

        def render_literal_bindparam(self, bindparam, **kw):
            value = bindparam.effective_value
            if isinstance(value, list):
                for sub_value in value:
                    if isinstance(sub_value, list):
                        raise GraphQLCompilationError('Param {} is a nested list. No nested lists '
                                                      'allowed'.format(bindparam.key))
                    if not isinstance(sub_value, bindparam.type.python_object):
                        raise GraphQLCompilationError('Param {} is a list with a value {} that is '
                                                      'not of the expected type {}.'
                                                      .format(bindparam.key, sub_value,
                                                              str(bindparam.type.python_object)))
            else:
                # This SQLAlchemy type does not have a python_type implementation.
                if isinstance(bindparam.type, UNIQUEIDENTIFIER):
                    if not isinstance(value, str):
                        raise GraphQLCompilationError('Param {} is not of the expected type {}.'
                                                      .format(value, str))
                # This SQLAlchemy type does not have a python_type implementation.
                elif isinstance(bindparam.type, BIT):
                    if not isinstance(value, int):
                        raise GraphQLCompilationError('Param {} is not of the expected type {}.'
                                                      .format(value, int))
                elif not isinstance(value, bindparam.type.python_object):
                    raise GraphQLCompilationError('Param {} is not of the expected type {}.'
                          .format(value, str(bindparam.type.python_object)))
            return self.render_literal_value(value, bindparam.type)

        def render_literal_value(self, value, type_):
            if isinstance(value, (list, tuple)):
                return "(%s)" % (",".join([self.render_literal_value(x, type_) for x in value]))
            else:
                if isinstance(value, bool):
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
