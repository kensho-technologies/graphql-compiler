# Copyright 2019-present Kensho Technologies, LLC.
from uuid import UUID
import datetime

from .helpers import is_int_field_type, is_uuid4_type, is_datetime_field_type


# UUIDs are defined in RFC-4122 as a 128-bit identifier. This means that the minimum UUID value
# (represented as a natural number) is 0, and the maximal value is 2^128-1.
MIN_UUID_INT = 0
MAX_UUID_INT = 2**128 - 1


# This module is a utility for reasoning about intervals when computing filter selectivities,
# and generating parameters for pagination. Since integers are the easiest type to deal with
# in this context, when we encounter a different type we represent it as an int, do all the
# computation in the integer domain, and transfer the computation back into the original domain.
#
# In order to be able to reason about value intervals and successor/predecessor values, we
# make sure these mappings to integers are increasing bijective functions.
#
# This kind of mapping is easy to do for int, uuid and datetime types, but not possible for other
# types, like string. When the need for other types arises, the precise interface for range
# reasoning can be defined and implemented separately for each type.


def field_supports_range_reasoning(schema_info, vertex_class, property_field):
    return any((
        is_uuid4_type(schema_info, vertex_class, property_field),
        is_int_field_type(schema_info, vertex_class, property_field),
        is_datetime_field_type(schema_info, vertex_class, property_field),
    ))


def convert_int_to_field_value(schema_info, vertex_class, property_field, int_value):
    """Return the given integer's corresponding property field value.
    Note that the property field values need not be integers. For example, all UUID values can be
    converted to integers and vice versa, but they are provided in a string format (e.g.
    00000000-0000-0000-0000-000000000000).
    Example: If int_value is 9, and the property field is a uuid, then the resulting field
    value will be 00000000-0000-0000-0000-000000000009.
    Args:
        schema_graph: SchemaGraph instance.
        vertex_class: str, name of vertex class to which the property field belongs.
        property_field: str, name of property field for which the domain of values is computed.
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
        return datetime.datetime.fromtimestamp(int_value)
    elif is_uuid4_type(schema_info, vertex_class, property_field):
        if not MIN_UUID_INT <= int_value <= MAX_UUID_INT:
            raise AssertionError(u'Integer value {} could not be converted to UUID, as it'
                                 u' is not in the range of valid UUIDs {} - {}: {} {}'
                                 .format(int_value, MIN_UUID_INT, MAX_UUID_INT, vertex_class,
                                         property_field))

        return str(UUID(int=int(int_value)))
    elif field_supports_range_reasoning(schema_info, vertex_class, property_field):
        raise AssertionError(u'Could not represent int {} as {} {}, but should be able to.'
                             .format(int_value, vertex_class, property_field))
    else:
        raise AssertionError(u'Could not represent int {} as {} {}. Currently,'
                             u' only uniform uuid4 and int fields are supported.'
                             .format(int_value, vertex_class, property_field))


def convert_field_value_to_int(schema_info, vertex_class, property_field, value):
    """Return the integer representation of a property field value."""
    if is_int_field_type(schema_info, vertex_class, property_field):
        return value
    if is_datetime_field_type(schema_info, vertex_class, property_field):
        return int((value - datetime.datetime(1970, 1, 1)).total_seconds())
    elif is_uuid4_type(schema_info, vertex_class, property_field):
        return UUID(value).int
    elif field_supports_range_reasoning(schema_info, vertex_class, property_field):
        raise AssertionError(u'Could not represent {} {} value {} as int, but should be able to'
                             .format(vertex_class, property_field, value))
    else:
        raise AssertionError(u'Could not represent {} {} value {} as int. Currently,'
                             u' only uniform uuid4 and int fields are supported.'
                             .format(vertex_class, property_field, value))
