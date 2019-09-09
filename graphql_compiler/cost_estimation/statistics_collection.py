# Copyright 2019-present Kensho Technologies, LLC.
from graphql import GraphQLUnionType
import six
import sqlalchemy

from .statistics import LocalStatistics


def _stream_vertex_edge_vertex_counts(sql_schema_info, engine):
    for from_vertex, joins in six.iteritems(sql_schema_info.join_descriptors):
        for vertex_field_name, join_descriptor in six.iteritems(joins):
            if vertex_field_name.startswith('out_'):
                edge_name = vertex_field_name[4:]
                to_type = sql_schema_info.schema.get_type(from_vertex)
                if isinstance(to_type, GraphQLUnionType):
                    continue

                to_vertex = sql_schema_info.schema.get_type(from_vertex).fields[
                    vertex_field_name].type.of_type.name

                try:
                    from_table = sql_schema_info.vertex_name_to_table[from_vertex].alias()
                    to_table = sql_schema_info.vertex_name_to_table[to_vertex].alias()
                    on_clause = (from_table.c[join_descriptor.from_column] ==
                                 to_table.c[join_descriptor.to_column])
                except KeyError:
                    continue

                query = sqlalchemy.select([sqlalchemy.func.count().label('count')]).select_from(
                    from_table.join(to_table, onclause=on_clause))

                result = [dict(row) for row in engine.execute(query)]
                if len(result) != 1:
                    raise AssertionError()
                yield (from_vertex, edge_name, to_vertex), result[0]['count']

            elif vertex_field_name.startswith('in_'):
                pass  # All direct joins are symmetric, no need to analyze both ways
            else:
                raise AssertionError()


def _stream_class_counts(sql_schema_info, engine):
    # Yield vertex counts
    for vertex_name, table in six.iteritems(sql_schema_info.vertex_name_to_table):
        query = sqlalchemy.select([sqlalchemy.func.count().label('count')]).select_from(table)

        result = [dict(row) for row in engine.execute(query)]
        if len(result) != 1:
            raise AssertionError()
        yield vertex_name, result[0]['count']

    # Yield direct edge counts
    for vertex_edge_vertex, count in _stream_vertex_edge_vertex_counts(sql_schema_info, engine):
        # There's no inheritance in SQL
        _, edge_name, _ = vertex_edge_vertex
        yield edge_name, count


def _stream_distinct_field_values_counts(sql_schema_info, engine):
    for vertex_name, table in six.iteritems(sql_schema_info.vertex_name_to_table):
        vertex_type = sql_schema_info.schema.get_type(vertex_name)
        for field in vertex_type.fields:
            if field == '_x_count':
                continue

            query = sqlalchemy.select([sqlalchemy.func.count().label('count')]).distinct().select_from(table)
            result = [dict(row) for row in engine.execute(query)]
            if len(result) != 1:
                raise AssertionError()
            yield (vertex_name, field), result[0]['count']


##############
# Public API #
##############


def create_local_statistics_from_mssql(sql_schema_info, engine):
    """Make a Statistics object about the data under the specified schema.

    Args:
        sql_schema_info: SqlSchemaInfo specifying the schema for which we want statistics.
        engine: sqlalchemy.Engine with an open connection pool to the database.

    Returns:
        LocalStatistics object that can be used for query cost estimation.
    """
    return LocalStatistics(
        dict(_stream_class_counts(sql_schema_info, engine)),
        dict(_stream_vertex_edge_vertex_counts(sql_schema_info, engine)),
        dict(_stream_distinct_field_values_counts(sql_schema_info, engine)),
    )


def write_mssql_statistics_to_csv_file(filename, sql_schema_info, engine):
    """Write a csv file containing statistics about the data under the specified schema.

    Args:
        filename: the filename to write the csv into.
        sql_schema_info: SqlSchemaInfo specifying the schema for which we want statistics.
        engine: sqlalchemy.Engine with an open connection pool to the database.
    """
    raise NotImplementedError()
