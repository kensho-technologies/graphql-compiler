from .constants import Cardinality, OPERATORS


class SqlBlocks:
    """
    The core abstraction of the SQL backend, these are transformations of IR blocks, preserving
    the elements that are of importance, while mapping to a more natural domain and language for
    considering SQL queries.
    """
    class BaseBlock:
        def __init__(self, query_state, block):
            self.query_state = query_state
            self.block = block
            self.table = None

        @property
        def location(self):
            return self.query_state.location

        @property
        def edge_name(self):
            current_vertex = self.query_state.current_vertex
            if current_vertex.startswith('out_'):
                return current_vertex[4:]
            if current_vertex.startswith('in_'):
                return current_vertex[3:]
            raise AssertionError

        @property
        def relative_type(self):
            return self.query_state.current_type()

        @property
        def outer_type(self):
            return self.query_state.outer_type()

        @property
        def in_optional(self):
            return self.query_state.in_optional

        @property
        def is_recursive(self):
            return self.query_state.is_recursive

        @property
        def in_fold(self):
            return self.query_state.in_fold

    class Predicate(BaseBlock):

        class Operator:
            def __init__(self, name, cardinality):
                self.name = name
                self.cardinality = cardinality



        def __init__(self, field_name, param_names, operator_name, is_tag, tag_location, tag_field,
                     query_state, block):
            """Creates a new Predicate block."""
            self.field_name = field_name
            self.param_names = param_names
            self.is_tag = is_tag
            self.tag_location = tag_location
            self.tag_field = tag_field
            self.tag_node = None
            if operator_name not in OPERATORS:
                raise AssertionError(
                    'Invalid operator "{}" supplied to predicate.'.format(operator_name)
                )
            self.operator = OPERATORS[operator_name]
            super(SqlBlocks.Predicate, self).__init__(query_state, block)

    class Relation(BaseBlock):

        def __init__(self, query_state, block):
            super(SqlBlocks.Relation, self).__init__(query_state, block)

