# Copyright 2019-present Kensho Technologies, LLC.
"""Int value conversion.

This module is a utility for reasoning about intervals when computing filter selectivities,
and generating parameters for pagination. Since integers are the easiest type to deal with
in this context, when we encounter a different type we represent it as an int, do all the
computation in the integer domain, and transfer the computation back into the original domain.

In order to be able to reason about value intervals and successor/predecessor values, we
make sure these mappings to integers are increasing bijective functions.

This kind of mapping is easy to do for int, uuid and datetime types, but not possible for other
types, like string. When the need for other types arises, the precise interface for range
reasoning can be defined and implemented separately for each type.
"""
import datetime
from uuid import UUID

import pytz

from .helpers import is_date_field_type, is_datetime_field_type, is_int_field_type, is_uuid4_type


# UUIDs are defined in RFC-4122 as a 128-bit identifier. This means that the minimum UUID value
# (represented as a natural number) is 0, and the maximal value is 2^128-1.
MIN_UUID_INT = 0
MAX_UUID_INT = 2**128 - 1


DATETIME_1970 = datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)


def field_supports_range_reasoning(schema_info, vertex_class, property_field):
    """Return whether range reasoning is supported. See module docstring for definition."""
    return any((
        is_uuid4_type(schema_info, vertex_class, property_field),
        is_int_field_type(schema_info, vertex_class, property_field),
        is_datetime_field_type(schema_info, vertex_class, property_field),
        is_date_field_type(schema_info, vertex_class, property_field),
    ))


def convert_int_to_field_value(schema_info, vertex_class, property_field, int_value):
    """Return the given integer's corresponding property field value.

    See module docstring for details.

    Args:
        schema_info: QueryPlanningSchemaInfo
        vertex_class: str, name of vertex class to which the property field belongs.
        property_field: str, name of property field that the value refers to.
        int_value: int, integer value which will be represented as a property field value.

    Returns:
        Any, the given integer's corresponding property field value.

    Raises:
        ValueError, if the given int_value is outside the range of valid values for the given
        property field.
    """
    if is_int_field_type(schema_info, vertex_class, property_field):
        return int_value
    if is_datetime_field_type(schema_info, vertex_class, property_field):
        return DATETIME_1970 + datetime.timedelta(microseconds=int_value)
    if is_date_field_type(schema_info, vertex_class, property_field):
        return datetime.date.fromordinal(int_value)
    elif is_uuid4_type(schema_info, vertex_class, property_field):
        if not MIN_UUID_INT <= int_value <= MAX_UUID_INT:
            raise ValueError(u'Integer value {} could not be converted to UUID, as it'
                             u' is not in the range of valid UUIDs {} - {}: {} {}'
                             .format(int_value, MIN_UUID_INT, MAX_UUID_INT, vertex_class,
                                     property_field))

        return str(UUID(int=int(int_value)))
    elif field_supports_range_reasoning(schema_info, vertex_class, property_field):
        raise AssertionError(u'Could not represent int {} as {} {}, but should be able to.'
                             .format(int_value, vertex_class, property_field))
    else:
        raise NotImplementedError(u'Could not represent int {} as {} {}.'
                                  .format(int_value, vertex_class, property_field))


def convert_field_value_to_int(schema_info, vertex_class, property_field, value):
    """Return the integer representation of a property field value."""
    if is_int_field_type(schema_info, vertex_class, property_field):
        return value
    if is_datetime_field_type(schema_info, vertex_class, property_field):
        if value.tzinfo != pytz.utc:
            raise ValueError(u'Invalid datetime value {}. Expected utc timezone, got {}'
                             .format(value, value.tzinfo))
        return int(DATETIME_1970 / datetime.timedelta(microseconds=1))
    if is_date_field_type(schema_info, vertex_class, property_field):
        return value.toordinal()
    elif is_uuid4_type(schema_info, vertex_class, property_field):
        return UUID(value).int
    elif field_supports_range_reasoning(schema_info, vertex_class, property_field):
        raise AssertionError(u'Could not represent {} {} value {} as int, but should be able to'
                             .format(vertex_class, property_field, value))
    else:
        raise NotImplementedError(u'Could not represent {} {} value {} as int.'
                                  .format(vertex_class, property_field, value))