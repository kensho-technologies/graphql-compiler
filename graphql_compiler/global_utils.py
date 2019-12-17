# Copyright 2017-present Kensho Technologies, LLC.
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


def is_same_type(to_compare1, to_compare2):
    """Determine if two GraphQL types are of the same type."""
    if isinstance(to_compare1, GraphQLNamedType) and isinstance(to_compare2, GraphQLNamedType):
        return (
            to_compare1.__class__ is to_compare2.__class__ and to_compare1.name == to_compare2.name
        )
    elif isinstance(to_compare1, GraphQLList) and isinstance(to_compare2, GraphQLList):
        return is_same_type(to_compare1.of_type, to_compare2.of_type)
    elif isinstance(to_compare1, GraphQLNonNull) and isinstance(to_compare2, GraphQLNonNull):
        return is_same_type(to_compare1.of_type, to_compare2.of_type)
    else:
        return False
