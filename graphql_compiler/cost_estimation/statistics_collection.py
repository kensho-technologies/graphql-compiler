# Copyright 2019-present Kensho Technologies, LLC.


def collect_statistics_from_mssql(sql_schema_info, engine):
    """Make a Statistics object about the data under the specified schema.

    Args:
        engine: sqlalchemy.Engine with an open connection pool to the database.
        schema_wildcards: list of strings, the set of schemas to consider. '*' means all
                          schemas. 'Animals.*' means all schemas in the Animals database.
                          No schema should be specified twice.

    Returns:
        Statistics object that can be used for query cost estimation.
    """
    raise NotImplementedError()
