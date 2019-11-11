# Copyright 2019-present Kensho Technologies, LLC.
import warnings

from graphql.type import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLString
import sqlalchemy.dialects.mssql.base as mssqltypes
import sqlalchemy.dialects.postgresql as postgrestypes
import sqlalchemy.sql.sqltypes as sqltypes

from ...global_utils import merge_non_overlapping_dicts
from functools import reduce
from ...schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal, GraphQLInt
from

# The following quote from https://docs.sqlalchemy.org/en/13/core/type_basics.html
# explains what makes all-caps classes particular:
# "This category of types refers to types that are either part of the SQL standard, or are
# potentially found within a subset of database backends. Unlike the "generic" types, the SQL
# standard/multi-vendor types have no guarantee of working on all backends, and will only work
# on those backends that explicitly support them by name. That is, the type will always emit its
# exact name in DDL with CREATE TABLE is issued."
# TODO(pmantica1): Add scalar mapping for the following classes: Interval.
GENERIC_SQL_CLASS_TO_GRAPHQL_TYPE = {
    sqltypes.BIGINT: GraphQLInt,
    sqltypes.BigInteger: GraphQLInt,
    sqltypes.BOOLEAN: GraphQLBoolean,
    sqltypes.Boolean: GraphQLBoolean,
    sqltypes.CHAR: GraphQLString,
    sqltypes.CLOB: GraphQLString,
    sqltypes.Date: GraphQLDate,
    sqltypes.DATE: GraphQLDate,
    sqltypes.DECIMAL: GraphQLDecimal,
    sqltypes.DateTime: GraphQLDateTime,
    sqltypes.DATETIME: GraphQLDateTime,
    sqltypes.Enum: GraphQLString,
    sqltypes.Float: GraphQLFloat,
    sqltypes.FLOAT: GraphQLFloat,
    sqltypes.INT: GraphQLInt,
    sqltypes.Integer: GraphQLInt,
    sqltypes.INTEGER: GraphQLInt,
    sqltypes.NCHAR: GraphQLString,
    sqltypes.Numeric: GraphQLDecimal,
    sqltypes.NUMERIC: GraphQLDecimal,
    sqltypes.NVARCHAR: GraphQLString,
    sqltypes.REAL: GraphQLFloat,
    sqltypes.SMALLINT: GraphQLInt,
    sqltypes.SmallInteger: GraphQLInt,
    sqltypes.String: GraphQLString,
    sqltypes.Text: GraphQLString,
    sqltypes.TEXT: GraphQLString,
    sqltypes.Time: GraphQLDateTime,
    sqltypes.TIME: GraphQLDateTime,
    sqltypes.TIMESTAMP: GraphQLDateTime,
    sqltypes.Unicode: GraphQLString,
    sqltypes.UnicodeText: GraphQLString,
    sqltypes.VARCHAR: GraphQLString,
}

# We do not currently plan to add a mapping for JSON and Binary objects.
UNSUPPORTED_GENERIC_SQL_TYPES = frozenset({
    sqltypes.ARRAY,
    sqltypes.Binary,
    sqltypes.BINARY,
    sqltypes.BLOB,
    sqltypes.Interval,
    sqltypes.JSON,
    sqltypes.LargeBinary,
    sqltypes.PickleType,
    sqltypes.VARBINARY,
})

MSSQL_CLASS_TO_GRAPHQL_TYPE = {
    mssqltypes.BIT: GraphQLBoolean,
    mssqltypes.DATETIME2: GraphQLDateTime,
    mssqltypes.REAL: GraphQLFloat,
    mssqltypes.NTEXT: GraphQLString,
    mssqltypes.SMALLDATETIME: GraphQLDateTime,
    mssqltypes.TIME: GraphQLDateTime,
    mssqltypes.TINYINT: GraphQLInt,
    mssqltypes.UNIQUEIDENTIFIER: GraphQLID,
}

UNSUPPORTED_MSSQL_TYPES = frozenset({
    mssqltypes.DATETIMEOFFSET,
    mssqltypes.IMAGE,
    mssqltypes.MONEY,
    mssqltypes.ROWVERSION,
    mssqltypes.SQL_VARIANT,
    mssqltypes.SMALLMONEY,
    # The mssqltypes.TIMESTAMP class inherits from SQL._Binary class, which is not supported.
    # TIMESTAMP docstring:
    #     Note this is completely different than the SQL Standard
    #     TIMESTAMP type, which is not supported by SQL Server.  It
    #     is a read-only datatype that does not support INSERT of values.
    mssqltypes.TIMESTAMP,
    mssqltypes.VARBINARY,
    mssqltypes.XML,
})


POSTGRES_CLASS_TO_GRAPHQL_TYPES = {
    postgrestypes.INTEGER: GraphQLInt,
    postgrestypes.BIGINT: GraphQLInt,
    postgrestypes.SMALLINT: GraphQLInt,
    postgrestypes.VARCHAR: GraphQLString,
    postgrestypes.CHAR: GraphQLString,
    postgrestypes.TEXT: GraphQLString,
    postgrestypes.NUMERIC: GraphQLDecimal,
    postgrestypes.FLOAT: GraphQLFloat,
    postgrestypes.REAL: GraphQLFloat,
    postgrestypes.UUID: GraphQLID,
    postgrestypes.DOUBLE_PRECISION: GraphQLFloat,
    postgrestypes.TIMESTAMP: GraphQLDateTime,
    postgrestypes.TIME: GraphQLDateTime,
    postgrestypes.DATE: GraphQLDate,
    postgrestypes.BOOLEAN: GraphQLBoolean,
}

UNSUPPORTED_POSTGRES_TYPES = frozenset({
    postgrestypes.INET,
    postgrestypes.CIDR,
    postgrestypes.MACADDR,
    postgrestypes.MONEY,
    postgrestypes.OID,
    postgrestypes.REGCLASS,
    postgrestypes.BYTEA
    postgrestypes.INTERVAL,
    postgrestypes.ARRAY,
    postgrestypes.ENUM,
    postgrestypes.INT4RANGE,
    postgrestypes.INT8RANGE,
    postgrestypes.NUMRANGE,
    postgrestypes.DATERANGE,
    postgrestypes.TSVECTOR,
    postgrestypes.TSTZRANGE,
    postgrestypes.TSTZRANGE,
    postgrestypes.JSON,
    postgrestypes.JSONB,
})


SQL_CLASS_TO_GRAPHQL_TYPE = reduce(
    merge_non_overlapping_dicts,
    (
        GENERIC_SQL_CLASS_TO_GRAPHQL_TYPE,
        MSSQL_CLASS_TO_GRAPHQL_TYPE,
        POSTGRES_CLASS_TO_GRAPHQL_TYPES,
    ),
    {}
)


def try_get_graphql_scalar_type(column_name, column_type):
    """Return the matching GraphQLScalarType for the SQL datatype or None if none is found."""
    maybe_graphql_type = SQL_CLASS_TO_GRAPHQL_TYPE.get(type(column_type), None)
    if maybe_graphql_type is None:
        # Trying to get the string representation of the SQLAlchemy JSON and ARRAY types
        # will lead to an error. We therefore use repr instead.
        warnings.warn(u'Ignoring column "{}" with unsupported SQL datatype: {}'
                      .format(column_name, type(column_type).__name__))
    return maybe_graphql_type
