# Copyright 2019-present Kensho Technologies, LLC.
def partition(iterable, pred):
    """Partition set iterable into two lists based on predicate."""
    trues = []
    falses = []
    for item in iterable:
        if pred(item):
            trues.append(item)
        else:
            falses.append(item)
    return trues, falses
