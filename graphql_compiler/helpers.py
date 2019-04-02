# Copyright 2019-present Kensho Technologies, LLC.
import funcy


def get_only_element_from_collection(one_element_collection):
    """Assert that the collection has exactly one element, then return that element."""
    if len(one_element_collection) != 1:
        raise AssertionError(u'Expected a collection with exactly one element, but got: {}'
                             .format(one_element_collection))
    return funcy.first(one_element_collection)
