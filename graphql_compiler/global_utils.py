# Copyright 2017-present Kensho Technologies, LLC.
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


def find_new_name(desired_name, taken_names, try_original=False):
    if try_original and desired_name not in taken_names:
        return desired_name

    index = 0
    while '{}_{}'.format(desired_name, index) in taken_names:
        index += 1
    return '{}_{}'.format(desired_name, index)
