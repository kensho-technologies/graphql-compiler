# Copyright 2019-present Kensho Technologies, LLC.


def create_local_statistics_from_mssql(sql_schema_info, engine):
    """Make a Statistics object about the data under the specified schema.

    Args:
        sql_schema_info: SqlSchemaInfo specifying the schema for which we want statistics.
        engine: sqlalchemy.Engine with an open connection pool to the database.

    Returns:
        LocalStatistics object that can be used for query cost estimation.
    """
    raise NotImplementedError()


def write_mssql_statistics_to_csv_file(sql_schema_info, engine, filename):
    """Write a csv file containing statistics about the data under the specified schema.

    Args:
        sql_schema_info: SqlSchemaInfo specifying the schema for which we want statistics.
        engine: sqlalchemy.Engine with an open connection pool to the database.
        filename: the filename to write the csv into
    """
    raise NotImplementedError()
