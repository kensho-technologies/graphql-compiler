# Copyright 2017-present Kensho Technologies, LLC.
from graphql import GraphQLScalarType
import six


def merge_non_overlapping_dicts(merge_target, new_data):
    """Produce the merged result of two dicts that are supposed to not overlap."""
    result = dict(merge_target)

    for key, value in six.iteritems(new_data):
        if key in merge_target:
            raise AssertionError(u'Overlapping key "{}" found in dicts that are supposed '
                                 u'to not overlap. Values: {} {}'
                                 .format(key, merge_target[key], value))

        result[key] = value

    return result


def get_scalar_types(schema):
    """Return the scalar types in a GraphQLSchema."""
    return {
        type for type in
        schema.get_type_map().values()
        if isinstance(type, GraphQLScalarType)
    }
