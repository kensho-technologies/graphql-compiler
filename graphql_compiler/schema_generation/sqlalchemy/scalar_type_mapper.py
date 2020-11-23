# Copyright 2019-present Kensho Technologies, LLC.
from functools import reduce
from typing import Any, Callable, Dict, Optional
import warnings

from graphql.type import GraphQLBoolean, GraphQLFloat, GraphQLID, GraphQLScalarType, GraphQLString
import sqlalchemy.dialects.mssql.base as mssqltypes
import sqlalchemy.dialects.mysql.base as mysqltypes
import sqlalchemy.dialects.oracle as oracletypes
import sqlalchemy.dialects.postgresql as postgrestypes
import sqlalchemy.sql.sqltypes as sqltypes
from sqlalchemy.sql.type_api import TypeEngine

from ...global_utils import merge_non_overlapping_dicts
from ...schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal, GraphQLInt


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
    sqltypes.TIMESTAMP: GraphQLDateTime,
    sqltypes.Unicode: GraphQLString,
    sqltypes.UnicodeText: GraphQLString,
    sqltypes.VARCHAR: GraphQLString,
}

# We do not currently plan to add a mapping for JSON and Binary objects.
UNSUPPORTED_GENERIC_SQL_TYPES = frozenset(
    {
        sqltypes.ARRAY,
        sqltypes.Binary,
        sqltypes.BINARY,
        sqltypes.BLOB,
        sqltypes.Interval,
        sqltypes.JSON,
        sqltypes.LargeBinary,
        sqltypes.PickleType,
        sqltypes.Time,
        sqltypes.TIME,
        sqltypes.VARBINARY,
    }
)

MSSQL_CLASS_TO_GRAPHQL_TYPE = {
    mssqltypes.BIT: GraphQLBoolean,
    mssqltypes.DATETIME2: GraphQLDateTime,
    mssqltypes.REAL: GraphQLFloat,
    mssqltypes.NTEXT: GraphQLString,
    mssqltypes.SMALLDATETIME: GraphQLDateTime,
    mssqltypes.TINYINT: GraphQLInt,
    mssqltypes.UNIQUEIDENTIFIER: GraphQLID,
}

UNSUPPORTED_MSSQL_TYPES = frozenset(
    {
        mssqltypes.DATETIMEOFFSET,
        mssqltypes.IMAGE,
        mssqltypes.MONEY,
        mssqltypes.ROWVERSION,
        mssqltypes.SQL_VARIANT,
        mssqltypes.SMALLMONEY,
        mssqltypes.TIME,
        # The mssqltypes.TIMESTAMP class inherits from SQL._Binary class, which is not supported.
        # TIMESTAMP docstring:
        #     Note this is completely different than the SQL Standard
        #     TIMESTAMP type, which is not supported by SQL Server.  It
        #     is a read-only datatype that does not support INSERT of values.
        mssqltypes.TIMESTAMP,
        mssqltypes.VARBINARY,
        mssqltypes.XML,
    }
)


POSTGRES_CLASS_TO_GRAPHQL_TYPES = {
    postgrestypes.UUID: GraphQLID,
    postgrestypes.DOUBLE_PRECISION: GraphQLFloat,
    postgrestypes.TIMESTAMP: GraphQLDateTime,
    postgrestypes.ENUM: GraphQLString,
}

UNSUPPORTED_POSTGRES_TYPES = frozenset(
    {
        # We shouldn't map the Postgresql bit type to the GraphQLBoolean type.
        # The Postgresql bit type is used to represent a bit string of variable length.
        # https://www.postgresql.org/docs/8.1/datatype-bit.html
        postgrestypes.BIT,
        postgrestypes.TIME,
        postgrestypes.INET,
        postgrestypes.CIDR,
        postgrestypes.MACADDR,
        postgrestypes.MONEY,
        postgrestypes.OID,
        postgrestypes.REGCLASS,
        postgrestypes.BYTEA,
        postgrestypes.INTERVAL,
        postgrestypes.ARRAY,
        postgrestypes.INT4RANGE,
        postgrestypes.INT8RANGE,
        postgrestypes.NUMRANGE,
        postgrestypes.DATERANGE,
        postgrestypes.TSVECTOR,
        postgrestypes.TSTZRANGE,
        postgrestypes.TSTZRANGE,
        postgrestypes.JSON,
        postgrestypes.JSONB,
    }
)

# TODO: Show unsupported types for mysql.
MYSQL_CLASS_TO_GRAPHQL_TYPE = {
    mysqltypes.BIGINT: GraphQLInt,
    mysqltypes.CHAR: GraphQLString,
    mysqltypes.DATETIME: GraphQLDateTime,
    mysqltypes.DECIMAL: GraphQLDecimal,
    mysqltypes.FLOAT: GraphQLFloat,
    mysqltypes.DOUBLE: GraphQLFloat,
    mysqltypes.VARBINARY: GraphQLString,
    mysqltypes.INTEGER: GraphQLInt,
    mysqltypes.LONGTEXT: GraphQLString,
    mysqltypes.MEDIUMTEXT: GraphQLString,
    mysqltypes.NCHAR: GraphQLString,
    mysqltypes.NVARCHAR: GraphQLString,
    mysqltypes.NUMERIC: GraphQLDecimal,
    mysqltypes.SMALLINT: GraphQLInt,
    mysqltypes.REAL: GraphQLFloat,
    mysqltypes.TEXT: GraphQLString,
    mysqltypes.TIMESTAMP: GraphQLDateTime,
    mysqltypes.TINYINT: GraphQLInt,
    mysqltypes.TINYTEXT: GraphQLString,
    mysqltypes.VARCHAR: GraphQLString,
}


# Based on info from https://docs.oracle.com/cd/B28359_01/server.111/b28318/datatype.htm
ORACLE_CLASS_TO_GRAPHQL_TYPE = {
    oracletypes.BINARY_DOUBLE: GraphQLFloat,
    oracletypes.BINARY_FLOAT: GraphQLFloat,
    oracletypes.DATE: GraphQLDate,
    oracletypes.DOUBLE_PRECISION: GraphQLFloat,
}


UNSUPPORTED_ORACLE_TYPES = frozenset(
    {
        oracletypes.BFILE,
        oracletypes.BLOB,
        oracletypes.CLOB,
        oracletypes.LONG,
        oracletypes.NCLOB,
        oracletypes.RAW,
        oracletypes.ROWID,
    }
)


def _deduce_graphql_type_for_oracle_number_type(number_type: TypeEngine) -> GraphQLScalarType:
    """Figure out whether Float, Int, or Decimal is the best representation of this NUMBER type.

    Based on info from https://docs.oracle.com/cd/B28359_01/server.111/b28318/datatype.htm#i22289

    Args:
        number_type: the specific NUMBER type (containing precision and scale info) which we are
                     converting to a suitable GraphQL scalar type

    Returns:
        the appropriate GraphQL type (Float, Int, or Decimal) that is best suited to representing
        this NUMBER database type
    """
    if not isinstance(number_type, oracletypes.NUMBER):
        raise AssertionError(
            "Unreachable code reached: expected an Oracle NUMBER data type object, but "
            "got {} instead: ".format(number_type)
        )

    if number_type.asdecimal:
        # SQLAlchemy has decided that this number is a decimal. No reason for us to disagree.
        return GraphQLDecimal

    if number_type.scale is None:
        # This number has no explicit scale. The default in Oracle appears to be a scale of 0.
        significant_figures = number_type.precision
    elif number_type.scale > 0:
        # This number type has decimal places. It has to be either a decimal or a float.
        if number_type.precision >= 15:
            # This number type can hold more digits than a 64-bit float would support:
            # a 64-bit float has a 53-bit mantissa, but 2^53 - 1 < 10^16 i.e. not all 15-digit
            # integers are representable as a 64-bit float without loss of precision.
            # Therefore, this data can only be properly represented as a Decimal,
            # the arbitrary-precision numeric data type.
            return GraphQLDecimal
        else:
            return GraphQLFloat
    elif number_type.scale < 0:
        # Negative scale means rounding integer places in base 10, starting with the "ones" place.
        # For example, a scale of -2 means "round to nearest hundred".
        significant_figures = number_type.precision - number_type.scale
    else:
        significant_figures = number_type.precision

    if significant_figures is None or significant_figures >= 19:
        # If significant_figures is None, Oracle's default "maximum precision" is used, which
        # as of November 2020 is 38 digits, i.e. more significant figures than a signed 64-bit
        # integer could hold. Since 2^63 - 1 < 10^19, 64-bit signed ints can only hold
        # up to 18-digit integers. The best type here is the Decimal type, which is our
        # arbitrary-precision numeric data type.
        return GraphQLDecimal
    else:
        return GraphQLInt


SPECIAL_ORACLE_TYPES: Dict[TypeEngine, Callable[[TypeEngine], GraphQLScalarType]] = {
    oracletypes.NUMBER: _deduce_graphql_type_for_oracle_number_type,
}


SQL_CLASS_TO_GRAPHQL_TYPE: Dict[Any, GraphQLScalarType] = reduce(
    merge_non_overlapping_dicts,
    (
        GENERIC_SQL_CLASS_TO_GRAPHQL_TYPE,
        MSSQL_CLASS_TO_GRAPHQL_TYPE,
        POSTGRES_CLASS_TO_GRAPHQL_TYPES,
        MYSQL_CLASS_TO_GRAPHQL_TYPE,
        ORACLE_CLASS_TO_GRAPHQL_TYPE,
    ),
    {},
)


def try_get_graphql_scalar_type(
    column_name: str, column_type: TypeEngine
) -> Optional[GraphQLScalarType]:
    """Return the matching GraphQLScalarType for the SQL datatype or None if none is found."""
    if isinstance(column_type, sqltypes.DateTime) and column_type.timezone:
        warnings.warn(
            f'Ignoring column "{column_name}". Timezone aware datetime types are '
            f"currently not supported."
        )
        return None
    else:
        maybe_graphql_type = SQL_CLASS_TO_GRAPHQL_TYPE.get(type(column_type), None)
        if maybe_graphql_type is not None:
            return maybe_graphql_type

        maybe_special_handler = SPECIAL_ORACLE_TYPES.get(type(column_type), None)
        if maybe_special_handler is not None:
            # This type is mapped to a GraphQL type on a case-by-case basis.
            # Invoke its handler function and let it decide on the appropriate type.
            return maybe_special_handler(column_type)

        # We were not able to deduce an appropriate GraphQL type for this column.
        warnings.warn(
            f'Ignoring column "{column_name}" with unsupported SQL datatype: '
            f"{type(column_type).__name__}"
        )
        return None
