from collections import defaultdict

from graphql_compiler.compiler import blocks


class SqlQueryTree(object):
    def __init__(self, root, query_path_to_location_info):
        self.root = root
        self.query_path_to_location_info = query_path_to_location_info


class SqlNode(object):
    """
    Acts as a tree representation of a SQL query.
    """
    def __init__(self, block, query_path):
        self.query_path = query_path
        self.fields = {}
        self.fields_to_rename = defaultdict(lambda: False)
        self.block = block
        self.filters = []
        self.children_nodes = []
        self.recursions = []
        self.link_columns = []
        self.recursion_to_column = {}

    def add_child_node(self, child_node):
        if isinstance(child_node.block, blocks.Recurse):
            self.recursions.append(child_node)
        else:
            self.children_nodes.append(child_node)

    def add_recursive_link_column(self, recursion, recursion_in_column):
        self.recursion_to_column[recursion] = recursion_in_column
        self.link_columns.append(recursion_in_column)

    def __str__(self):
        return u'SqlNode({}, children={})'.format(self.query_path, self.children_nodes)

    def __repr__(self):
        return self.__str__()
