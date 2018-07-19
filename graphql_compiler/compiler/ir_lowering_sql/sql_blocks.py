from .constants import Cardinality


class SqlBlocks:
    """
    The core abstraction of the SQL backend, these are transformations of IR blocks, preserving
    the elements that are of importance, while mapping to a more natural domain and language for
    considering SQL queries.
    """
    class BaseBlock:
        def __init__(self, query_state):
            self.query_state = query_state
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

    class Selection(BaseBlock):
        def __init__(self, field_name, alias, query_state):
            self.field_name = field_name
            self.alias = alias
            self.renamed = False
            super(SqlBlocks.Selection, self).__init__(query_state)

        def rename(self):
            if self.alias is None:
                self.alias = self.field_name
            self.renamed = True

    class Predicate(BaseBlock):

        class Operator:
            def __init__(self, name, cardinality):
                self.name = name
                self.cardinality = cardinality

        operators = {
            "contains": Operator('in_', Cardinality.MANY),
            "=": Operator('__eq__', Cardinality.SINGLE),
            "<": Operator('__lt__', Cardinality.SINGLE),
            ">": Operator('__gt__', Cardinality.SINGLE),
            "<=": Operator('__le__', Cardinality.SINGLE),
            ">=": Operator('__ge__', Cardinality.SINGLE),
            "between": Operator('between', Cardinality.DUAL),
            'has_substring': Operator('contains', Cardinality.SINGLE),
        }

        def __init__(self, field_name, param_names, operator_name, is_tag, tag_location, tag_field,
                     query_state):
            """Creates a new Predicate block."""
            self.field_name = field_name
            self.param_names = param_names
            self.is_tag = is_tag
            self.tag_location = tag_location
            self.tag_field = tag_field
            self.tag_node = None
            if operator_name not in self.operators:
                raise AssertionError(
                    'Invalid operator "{}" supplied to predicate.'.format(operator_name)
                )
            self.operator = self.operators[operator_name]
            super(SqlBlocks.Predicate, self).__init__(query_state)

    class Relation(BaseBlock):

        def __init__(self, query_state, recursion_depth=None, direction=None):
            self.recursion_depth = recursion_depth
            self.direction = direction
            super(SqlBlocks.Relation, self).__init__(query_state)

        def __repr__(self):
            return self.location.query_path.__repr__()
