# Copyright 2017-present Kensho Technologies, LLC.
from typing import Sequence

from graphql import GraphQLList, GraphQLNamedType, GraphQLNonNull
import six


def merge_non_overlapping_dicts(merge_target, new_data):
    """Produce the merged result of two dicts that are supposed to not overlap."""
    result = dict(merge_target)

    for key, value in six.iteritems(new_data):
        if key in merge_target:
            raise AssertionError(
                u'Overlapping key "{}" found in dicts that are supposed '
                u"to not overlap. Values: {} {}".format(key, merge_target[key], value)
            )

        result[key] = value

    return result


def is_same_type(left, right):
    """Determine if two GraphQL types are the same type."""
    if isinstance(left, GraphQLNamedType) and isinstance(right, GraphQLNamedType):
        return left.__class__ is right.__class__ and left.name == right.name
    elif isinstance(left, GraphQLList) and isinstance(right, GraphQLList):
        return is_same_type(left.of_type, right.of_type)
    elif isinstance(left, GraphQLNonNull) and isinstance(right, GraphQLNonNull):
        return is_same_type(left.of_type, right.of_type)
    else:
        return False


def generate_new_name(base_name: str, taken_names: Sequence[str]) -> str:
    """Return a name based on the provided string that is not already taken.

    This method tries the following names:
    {base_name}_0, then {base_name}_1, etc.
    and returns the first one that's not in taken_names
    """
    index = 0
    while "{}_{}".format(base_name, index) in taken_names:
        index += 1
    return "{}_{}".format(base_name, index)
