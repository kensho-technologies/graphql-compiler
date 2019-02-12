# Copyright 2018-present Kensho Technologies, LLC.


class SqlQueryTree(object):
    def __init__(self, root, query_path_to_location_info,
                 query_path_to_output_fields, query_path_to_filters, query_path_to_node):
        """Wrap a SqlNode root with additional location_info metadata."""
        self.root = root
        self.query_path_to_location_info = query_path_to_location_info
        self.query_path_to_output_fields = query_path_to_output_fields
        self.query_path_to_filters = query_path_to_filters
        self.query_path_to_node = query_path_to_node


class SqlNode(object):
    """Representation of a SQL Query as a tree."""

    def __init__(self, block, query_path):
        """Create a new SqlNode wrapping a QueryRoot block at a query_path."""
        self.query_path = query_path
        self.block = block
        self._children = []

    def add_child_node(self, value):
        if not isinstance(value, SqlNode):
            raise AssertionError(u'Cannot non-SqlNode child "{}" of type "{}" to SqlNode.'.format(
                value, type(value)))
        self._children.append(value)

    @property
    def children(self):
        return tuple(self._children)

    def __str__(self):
        """Return a string representation of a SqlNode."""
        return u'SqlNode({}, children={})'.format(self.query_path, self.children)

    def __repr__(self):
        """Return the repr of a SqlNode."""
        return self.__str__()
