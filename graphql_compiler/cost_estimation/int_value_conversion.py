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
from typing import Any
from uuid import UUID

from ..schema import is_meta_field
from ..schema.schema_info import QueryPlanningSchemaInfo, UUIDOrdering
from .helpers import (
    get_uuid_ordering,
    is_date_field_type,
    is_datetime_field_type,
    is_int_field_type,
    is_uuid4_type,
)


# UUIDs are defined in RFC-4122 as a 128-bit identifier. This means that the minimum UUID value
# (represented as a natural number) is 0, and the maximal value is 2^128-1.
MIN_UUID_INT = 0
MAX_UUID_INT = 2 ** 128 - 1


DATETIME_EPOCH_TZ_NAIVE = datetime.datetime(1970, 1, 1)


def swap_uuid_prefix_and_suffix(uuid_string: str) -> str:
    """Swap the first 12 and last 12 hex digits of a uuid string.

    Different databases implement uuid comparison differently (see UUIDOrdering). This function
    is useful as a helper method to implement the LastSixBytesFirst ordering method based on the
    LeftToRight ordering method.

    args:
        uuid_string: uuid string

    Returns:
        the input with the first and last 12 hex digits swapped
    """
    segments = uuid_string.split("-")
    segment_lengths = tuple(len(segment) for segment in segments)
    expected_segment_lengths = (8, 4, 4, 4, 12)
    if expected_segment_lengths != segment_lengths:
        raise AssertionError(f"Unexpected segment lengths {segment_lengths} in {uuid_string}")

    new_segments = [
        segments[4][:8],
        segments[4][8:],
        segments[2],
        segments[3],
        segments[0] + segments[1],
    ]
    return "-".join(new_segments)


def field_supports_range_reasoning(
    schema_info: QueryPlanningSchemaInfo, vertex_class: str, property_field: str
) -> bool:
    """Return whether range reasoning is supported. See module docstring for definition."""
    if is_meta_field(property_field):
        return False
    return (
        is_uuid4_type(schema_info, vertex_class, property_field)
        or is_int_field_type(schema_info, vertex_class, property_field)
        or is_datetime_field_type(schema_info, vertex_class, property_field)
        or is_date_field_type(schema_info, vertex_class, property_field)
    )


def convert_int_to_field_value(
    schema_info: QueryPlanningSchemaInfo, vertex_class: str, property_field: str, int_value: int
) -> Any:
    """Return the given integer's corresponding property field value.

    See module docstring for details. The int_value is expected to be in the range of
    convert_field_value_to_int.

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
    elif is_datetime_field_type(schema_info, vertex_class, property_field):
        return DATETIME_EPOCH_TZ_NAIVE + datetime.timedelta(microseconds=int_value)
    elif is_date_field_type(schema_info, vertex_class, property_field):
        return datetime.date.fromordinal(int_value)
    elif is_uuid4_type(schema_info, vertex_class, property_field):
        if not MIN_UUID_INT <= int_value <= MAX_UUID_INT:
            raise AssertionError(
                "Integer value {} could not be converted to UUID, as it "
                "is not in the range of valid UUIDs {} - {}: {} {}".format(
                    int_value, MIN_UUID_INT, MAX_UUID_INT, vertex_class, property_field
                )
            )

        uuid_string = str(UUID(int=int(int_value)))
        ordering = get_uuid_ordering(schema_info, vertex_class, property_field)
        if ordering == UUIDOrdering.LeftToRight:
            return uuid_string
        elif ordering == UUIDOrdering.LastSixBytesFirst:
            return swap_uuid_prefix_and_suffix(uuid_string)
        else:
            raise AssertionError(
                f"Unexpected ordering for {vertex_class}.{property_field}: {ordering}"
            )
    elif field_supports_range_reasoning(schema_info, vertex_class, property_field):
        raise AssertionError(
            "Could not represent int {} as {} {}, but should be able to.".format(
                int_value, vertex_class, property_field
            )
        )
    else:
        raise NotImplementedError(
            "Could not represent int {} as {} {}.".format(int_value, vertex_class, property_field)
        )


def convert_field_value_to_int(
    schema_info: QueryPlanningSchemaInfo, vertex_class: str, property_field: str, value: Any
) -> int:
    """Return the integer representation of a property field value."""
    if is_int_field_type(schema_info, vertex_class, property_field):
        return value
    elif is_datetime_field_type(schema_info, vertex_class, property_field):
        return (value.replace(tzinfo=None) - DATETIME_EPOCH_TZ_NAIVE) // datetime.timedelta(
            microseconds=1
        )
    elif is_date_field_type(schema_info, vertex_class, property_field):
        return value.toordinal()
    elif is_uuid4_type(schema_info, vertex_class, property_field):
        ordering = get_uuid_ordering(schema_info, vertex_class, property_field)
        if ordering == UUIDOrdering.LeftToRight:
            return UUID(value).int
        elif ordering == UUIDOrdering.LastSixBytesFirst:
            return UUID(swap_uuid_prefix_and_suffix(value)).int
        else:
            raise AssertionError(
                f"Unexpected ordering for {vertex_class}.{property_field}: {ordering}"
            )
    elif field_supports_range_reasoning(schema_info, vertex_class, property_field):
        raise AssertionError(
            "Could not represent {} {} value {} as int, but should be able to".format(
                vertex_class, property_field, value
            )
        )
    else:
        raise NotImplementedError(
            "Could not represent {} {} value {} as int.".format(vertex_class, property_field, value)
        )
