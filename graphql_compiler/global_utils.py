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


def generate_new_name(desired_name: str, taken_names: Sequence[str]) -> str:
    """Return a name similar to the desired one that is not already taken.

    If the desired name is not taken, it is returned. If it is, this method tries
    {desired_name}_0, then {desired_name}_1, etc.
    """
    if desired_name not in taken_names:
        return desired_name

    index = 0
    while "{}_{}".format(desired_name, index) in taken_names:
        index += 1
    return "{}_{}".format(desired_name, index)
