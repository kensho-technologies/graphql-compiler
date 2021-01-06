# Copyright 2019-present Kensho Technologies, LLC.
import re
import warnings

from sqlalchemy import Column, Table, text
from sqlalchemy.dialects.mssql.base import ischema_names


def fast_sql_server_reflect(engine, metadata, schema, primary_key_selector=None):
    """Reflect the metadata of a SQL Server in a quick but shallow manner.

    This function is roughly a faster, but shallower equivalent to the SQLAlchemy metadata.reflect()
    method. It currently only reflects: columns, column types and primary keys. Other information,
    like foreign key metadata, is currently ignored but might be inferred in the future.

    This function mutates the metadata object.

    Args:
        engine: SQLAlchemy Engine, engine connected to a SQL Server. In order to load metadata for
                arbitrary databases and schemas, make sure the "master" database is selected
                for use, for example via executing `engine.execute("USE master;")`.
                This is the core system database in the SQL Server where information about all other
                databases is available. If any other database is selected for use on the connection,
                only the data pertaining to that database can be reflected and loaded.
                More info on the "master" database can be found here:
                https://docs.microsoft.com/en-us/sql/relational-databases/databases/master-database
        metadata: MetaData object to reflect the metadata of the SQL Server to.
        schema: string in the format <databaseName>.<schemaName> specifying the schema
                to reflect into the metadata.
        primary_key_selector: optional function that takes in a table name and list of dicts
                              specifying column metadata and returns a set of column names to use
                              as the primary key for the corresponding SQLAlchemy Table object.
                              The compiler requires each SQLAlchemy Table to have a primary key.
                              The primary keys do not need to be the primary keys in the underlying
                              tables. They just need to be an unique and non-null identifier of
                              each row. This parameter should be used to amend SQLAlchemy Table
                              objects with such non-explicitly enforced primary keys.
    """
    database_name, schema_name = schema.split(".")

    name_pattern = re.compile(r"^[a-zA-Z][_\-a-zA-Z0-9]*")
    # Check to prevent against SQL injection.
    if not name_pattern.match(database_name):
        raise AssertionError("Invalid database name {}".format(database_name))
    if not name_pattern.match(schema_name):
        raise AssertionError("Invalid schema name {}".format(schema_name))

    table_to_column_metadata = _get_table_to_column_metadata(engine, database_name, schema_name)
    table_to_explicit_primary_key_columns = _get_table_to_explicit_primary_key_columns(
        engine, database_name, schema_name
    )
    table_to_primary_key_columns = _get_table_to_primary_key_columns(
        table_to_column_metadata, table_to_explicit_primary_key_columns, primary_key_selector
    )
    for table_name, column_metadata in table_to_column_metadata.items():
        primary_key_columns = table_to_primary_key_columns[table_name]
        sqlalchemy_columns = []
        for column in column_metadata:
            column_name = column["COLUMN_NAME"]
            data_type = column["DATA_TYPE"]
            # Ignore custom database types.
            maybe_sqlalchemy_type = ischema_names.get(data_type)
            if maybe_sqlalchemy_type:
                sqlalchemy_columns.append(
                    Column(
                        column_name,
                        maybe_sqlalchemy_type(),
                        primary_key=column_name in primary_key_columns,
                    )
                )
            else:
                warnings.warn(
                    "Ignoring column {} with custom data type {} in table {} "
                    "of schema {}.".format(column_name, data_type, table_name, schema)
                )
        # Insert specified table into MetaData object
        Table(table_name, metadata, *sqlalchemy_columns, schema=schema)


def get_first_column_in_table(table_name, column_metadata):
    """Return a string set with one element: the first column of the table.

    In the case where the first column of each table in a schema is a non-explicitly enforced
    primary key, this function can be used as the primary_key_selector parameter in
    fast_sql_server_reflect to amend Table objects with missing primary keys.

    Args:
        table_name: str, name of the table.
        column_metadata: list of dicts, str -> Any, specifying metadata about the columns in a
                         table. Uses the ORDINAL_POSITION and COLUMN_NAME keys of each dict
                         to determine the first column of the table.

    Returns:
        string set with one element: the first column of the table.
    """
    for column in column_metadata:
        if column["ORDINAL_POSITION"] == 1:
            return {column["COLUMN_NAME"]}

    raise AssertionError(f"Unreachable state reached: {table_name} {column_metadata}")


def _get_table_to_column_metadata(engine, database_name, schema_name):
    """Return a dict mapping the name of each table to a list of column metadata dicts."""
    columns_query = text(
        """
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{schema}';
        """.format(  # nosec
            database=database_name, schema=schema_name
        )
    )

    result_proxy = engine.execute(columns_query)
    table_to_column_metadata = {}
    for value in result_proxy:
        table_to_column_metadata.setdefault(value["TABLE_NAME"], []).append(value)
    return table_to_column_metadata


def _get_table_to_explicit_primary_key_columns(engine, database_name, schema_name):
    """Return a dict mapping each table to its set of explicit primary key columns."""
    primary_key_query = text(
        """
        SELECT KU.table_name as TABLE_NAME,column_name as PRIMARY_KEY_COLUMN
        FROM {database}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS TC
        INNER JOIN
            {database}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS KU
                  ON TC.CONSTRAINT_TYPE = 'PRIMARY KEY' AND
                     TC.CONSTRAINT_NAME = KU.CONSTRAINT_NAME
        WHERE KU.CONSTRAINT_SCHEMA = '{schema}'
        """.format(  # nosec
            database=database_name, schema=schema_name
        )
    )

    result_proxy = engine.execute(primary_key_query)
    table_to_explicit_primary_key_columns = {}
    for value in result_proxy:
        table_to_explicit_primary_key_columns.setdefault(value["TABLE_NAME"], set()).add(
            value["PRIMARY_KEY_COLUMN"]
        )
    return table_to_explicit_primary_key_columns


def _get_table_to_primary_key_columns(
    table_to_column_metadata, table_to_explicit_primary_key_columns, primary_key_selector
):
    """Return the set of primary key columns for each table."""
    table_to_primary_key_columns = {}
    for table_name in table_to_column_metadata:
        if table_name in table_to_explicit_primary_key_columns:
            table_to_primary_key_columns[table_name] = table_to_explicit_primary_key_columns[
                table_name
            ]
        else:
            if primary_key_selector is None:
                raise AssertionError(
                    "Table {} does not have a primary key nor a primary key "
                    "selector".format(table_name)
                )
            table_to_primary_key_columns[table_name] = primary_key_selector(
                table_name, table_to_column_metadata[table_name]
            )
    return table_to_primary_key_columns
