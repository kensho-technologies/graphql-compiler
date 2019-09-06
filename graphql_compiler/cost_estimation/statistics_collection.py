# Copyright 2019-present Kensho Technologies, LLC.
from .statistics import LocalStatistics


def _stream_class_counts(sql_schema_info, engine):
    raise NotImplementedError()


def _stream_vertex_edge_vertex_counts(sql_schema_info, engine):
    raise NotImplementedError()


def _stream_distinct_field_values_counts(sql_schema_info, engine):
    raise NotImplementedError()


##############
# Public API #
##############


# TODO not schema graph?
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
        dict(_distinct_field_values_counts(sql_schema_info, engine)),
    )


def write_mssql_statistics_to_csv_file(filename, sql_schema_info, engine):
    """Write a csv file containing statistics about the data under the specified schema.

    Args:
        filename: the filename to write the csv into.
        sql_schema_info: SqlSchemaInfo specifying the schema for which we want statistics.
        engine: sqlalchemy.Engine with an open connection pool to the database.
    """
    raise NotImplementedError()
