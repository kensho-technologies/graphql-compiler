from collections import defaultdict

from graphql_compiler.compiler import blocks


class SqlNode(object):
    """
    Acts as a tree representation of a SQL query.
    """
    def __init__(self, parent_node, block, location_info, parent_location_info, query_path):
        self.parent_node = parent_node
        self.query_path = query_path
        self.fields = {}
        self.fields_to_rename = defaultdict(lambda: False)
        self.location_info = location_info
        self.parent_location_info = parent_location_info
        self.outer_type = None if self.parent_location_info is None else self.parent_location_info.type.name
        self.relative_type = self.location_info.type.name
        self.block = block
        self.filters = []
        self.children = []
        self.children_nodes = []
        self.recursions = []
        self.link_columns = []
        self.recursion_to_column = {}
        self.link_column = None
        self.from_clause = None

    @property
    def in_optional(self):
        """
        Whether or not this block is optional itself, or in an optional scope.
        :return:
        """
        return (isinstance(self.block, (blocks.Traverse, blocks.Recurse))
                and (self.block.within_optional_scope or self.block.optional))

    def add_child_node(self, child_node):
        if isinstance(child_node.block, blocks.Recurse):
            self.recursions.append(child_node)
        else:
            self.children_nodes.append(child_node)
        self.children.append(child_node)

    def add_recursive_link_column(self, recursion, recursion_in_column):
        self.recursion_to_column[recursion] = recursion_in_column
        self.link_columns.append(recursion_in_column)

    def __str__(self):
        return 'SqlNode({}, children={})'.format(self.query_path, self.children_nodes)

    def __repr__(self):
        return self.__str__()
