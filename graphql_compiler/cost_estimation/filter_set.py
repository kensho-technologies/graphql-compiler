# Copyright 2019-present Kensho Technologies, LLC.

def _binary_optional(op, a, b):
    if a is None:
        return b
    if b is None:
        return a
    return op(a, b)


class FilterSet(object):
    def __init__(self, op_name, args):
        self.lt = None
        self.lte = None
        self.gt = None
        self.gte = None
        self.other_filters = []
        if op_name == 'nothing':
            pass
        elif op_name == '<':
            self.lt = args[0]
        elif op_name == '<=':
            self.lte = args[0]
        elif op_name == '>':
            self.gt = args[0]
        elif op_name == '>=':
            self.gte = args[0]
        elif op_name == 'between':
            self.gt = args[0]
            self.lt = args[0]
        else:
            raise NotImplementedError()
        self._normalize()

    def _normalize(self):
        if self.lt is not None and self.lte is not None:
            if self.lt > self.lte:
                self.lt = None
            else:
                self.lte = None
        if self.gt is not None and self.gte is not None:
            if self.gt > self.gte:
                self.gt = None
            else:
                self.gte = None

    @staticmethod
    def empty():
        return FilterSet('nothing', [])

    def intersect(self, filter_set):
        self.lt = _binary_optional(max, self.lt, filter_set.lt)
        self.lte = _binary_optional(max, self.lte, filter_set.lte)
        self.gt = _binary_optional(min, self.gt, filter_set.gt)
        self.gte = _binary_optional(min, self.gte, filter_set.gte)
        self.other_filters.extend(filter_set.other_filters)
        self._normalize()

    def subdivide(self, pivot):
        raise NotImplementedError()

    def to_ast(self):
        raise NotImplementedError()
