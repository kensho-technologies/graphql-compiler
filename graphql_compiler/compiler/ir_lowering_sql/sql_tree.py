from graphql_compiler.compiler import blocks
from graphql_compiler.compiler.ir_lowering_sql import SqlBlocks


class SqlNode(object):
    """
    Acts as a tree representation of a SQL query.

    More specifically, a SQL node is a SQL Relation block, with any corresponding Selection and
    Predicate SQL blocks. These are linked based on location. The node manages the reference to the
    underlying SQL alchemy table for these blocks, and manages the relationship to other nodes
    in the tree.
    """
    def __init__(self, parent_node, relation, location_info, parent_location_info):
        self.parent_node = parent_node
        self.query_state = relation.query_state
        self.location = self.query_state.location
        self.location_info = location_info
        self.parent_location_info = parent_location_info
        self.outer_type = None if self.parent_location_info is None else self.parent_location_info.type.name
        self.relative_type = self.location_info.type.name
        self.block = relation.block
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