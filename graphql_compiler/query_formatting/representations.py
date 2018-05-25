# Copyright 2017-present Kensho Technologies, LLC.
"""Common representations of various types in Gremlin and MATCH (SQL)."""
import decimal

from ..exceptions import GraphQLInvalidArgumentError


def represent_float_as_str(value):
    """Represent a float as a string without losing precision."""
    # In Python 2, calling str() on a float object loses precision:
    #
    # In [1]: 1.23456789012345678
    # Out[1]: 1.2345678901234567
    #
    # In [2]: 1.2345678901234567
    # Out[2]: 1.2345678901234567
    #
    # In [3]: str(1.2345678901234567)
    # Out[3]: '1.23456789012'
    #
    # The best way to ensure precision is not lost is to convert to string via Decimal:
    # https://github.com/mogui/pyorient/pull/226/files
    if not isinstance(value, float):
        raise GraphQLInvalidArgumentError(u'Attempting to represent a non-float as a float: '
                                          u'{}'.format(value))

    with decimal.localcontext() as ctx:
        ctx.prec = 20  # floats are max 80-bits wide = 20 significant digits
        return u'{:f}'.format(decimal.Decimal(value))


def type_check_and_str(python_type, value):
    """Type-check the value, and then just return str(value)."""
    if not isinstance(value, python_type):
        raise GraphQLInvalidArgumentError(u'Attempting to represent a non-{type} as a {type}: '
                                          u'{value}'.format(type=python_type, value=value))

    return str(value)


def coerce_to_decimal(value):
    """Attempt to coerce the value to a Decimal, or raise an error if unable to do so."""
    if isinstance(value, decimal.Decimal):
        return value
    else:
        try:
            return decimal.Decimal(value)
        except decimal.InvalidOperation as e:
            raise GraphQLInvalidArgumentError(e)
