from graphql_compiler.compiler.ir_lowering_sql import SqlBlocks


class SqlNode(object):
    """
    Acts as a tree representation of a SQL query.

    More specifically, a SQL node is a SQL Relation block, with any corresponding Selection and
    Predicate SQL blocks. These are linked based on location. The node manages the reference to the
    underlying SQL alchemy table for these blocks, and manages the relationship to other nodes
    in the tree.
    """
    def __init__(self, parent_node, relation):
        self.parent_node = parent_node
        self.children_nodes = []
        self.recursions = []
        self.selections = []
        self.predicates = []
        self.link_columns = []
        self.recursion_to_column = {}
        self.link_column = None
        self.relation = relation
        self.from_clause = None
        self.table = None

    def is_tree_root(self):
        return self.parent_node is None

    def add_child_node(self, child_node):
        if child_node.relation.is_recursive:
            self.recursions.append(child_node)
        else:
            self.children_nodes.append(child_node)

    def add_selection(self, selection):
        if not isinstance(selection, SqlBlocks.Selection):
            raise AssertionError('Trying to add non-selection')
        self.selections.append(selection)

    def add_recursive_link_column(self, recursion, recursion_in_column):
        self.recursion_to_column[recursion] = recursion_in_column
        self.link_columns.append(recursion_in_column)

    def add_predicate(self, predicate):
        if not isinstance(predicate, SqlBlocks.Predicate):
            raise AssertionError('Trying to add non-predicate')
        self.predicates.append(predicate)

    def __repr__(self):
        return self.relation.__repr__()