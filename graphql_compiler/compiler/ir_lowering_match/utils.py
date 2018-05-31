# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple

import six

from ..blocks import Filter
from ..expressions import (BinaryComposition, Expression, LocalField, NullLiteral,
                           SelectEdgeContextField, TrueLiteral, UnaryTransformation, ZeroLiteral)
from ..helpers import Location


def expression_list_to_conjunction(expression_list):
    """Convert a list of expressions to an Expression that is the conjunction of all of them."""
    if not isinstance(expression_list, list):
        raise AssertionError(u'Expected `list`, Received {}.'.format(expression_list))

    if len(expression_list) == 0:
        return TrueLiteral

    if not isinstance(expression_list[0], Expression):
        raise AssertionError(u'Non-Expression object {} found in expression_list'
                             .format(expression_list[0]))
    if len(expression_list) == 1:
        return expression_list[0]
    else:
        return BinaryComposition(u'&&',
                                 expression_list_to_conjunction(expression_list[1:]),
                                 expression_list[0])


class BetweenClause(Expression):
    """A `BETWEEN` Expression, constraining a field value to lie within a lower and upper bound."""

    def __init__(self, field, lower_bound, upper_bound):
        """Construct an expression that is true when the field value is within the given bounds.

        Args:
            field: LocalField Expression, denoting the field in consideration
            lower_bound: lower bound constraint for given field
            upper_bound: upper bound constraint for given field

        Returns:
            a new BetweenClause object
        """
        super(BetweenClause, self).__init__(field, lower_bound, upper_bound)
        self.field = field
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.validate()

    def validate(self):
        """Validate that the Between Expression is correctly representable."""
        if not isinstance(self.field, LocalField):
            raise TypeError(u'Expected LocalField field, got: {} {}'.format(
                type(self.field).__name__, self.field))

        if not isinstance(self.lower_bound, Expression):
            raise TypeError(u'Expected Expression lower_bound, got: {} {}'.format(
                type(self.lower_bound).__name__, self.lower_bound))

        if not isinstance(self.upper_bound, Expression):
            raise TypeError(u'Expected Expression upper_bound, got: {} {}'.format(
                type(self.upper_bound).__name__, self.upper_bound))

    def visit_and_update(self, visitor_fn):
        """Create an updated version (if needed) of BetweenClause via the visitor pattern."""
        new_lower_bound = self.lower_bound.visit_and_update(visitor_fn)
        new_upper_bound = self.upper_bound.visit_and_update(visitor_fn)

        if new_lower_bound is not self.lower_bound or new_upper_bound is not self.upper_bound:
            return visitor_fn(BetweenClause(self.field, new_lower_bound, new_upper_bound))
        else:
            return visitor_fn(self)

    def to_match(self):
        """Return a unicode object with the MATCH representation of this BetweenClause."""
        template = u'({field_name} BETWEEN {lower_bound} AND {upper_bound})'
        return template.format(
            field_name=self.field.to_match(),
            lower_bound=self.lower_bound.to_match(),
            upper_bound=self.upper_bound.to_match())

    def to_gremlin(self):
        """Must never be called."""
        raise NotImplementedError()


def filter_edge_field_non_existence(edge_expression):
    """Return an Expression that is True iff the specified edge (edge_expression) does not exist."""
    # When an edge does not exist at a given vertex, OrientDB represents that in one of two ways:
    #   - the edge's field does not exist (is null) on the vertex document, or
    #   - the edge's field does exist, but is an empty list.
    # We check both of these possibilities.
    if not isinstance(edge_expression, (LocalField, SelectEdgeContextField)):
        raise AssertionError(u'Received invalid edge_expression {} of type {}.'
                             u'Expected LocalField or SelectEdgeContextField.'
                             .format(edge_expression, type(edge_expression).__name__))
    if isinstance(edge_expression, LocalField):
        if edge_expression.field_name[:3] != u'in_' and edge_expression.field_name[:4] != u'out_':
            raise AssertionError(u'Received LocalField edge_expression {} with non-edge field_name '
                                 u'{}.'.format(edge_expression, edge_expression.field_name))

    field_null_check = BinaryComposition(u'=', edge_expression, NullLiteral)

    local_field_size = UnaryTransformation(u'size', edge_expression)
    field_size_check = BinaryComposition(u'=', local_field_size, ZeroLiteral)

    return BinaryComposition(u'||', field_null_check, field_size_check)


def filter_orientdb_simple_optional_edge(root_location_path, inner_location_name, edge_field):
    """Return an Expression that is False for rows that don't follow the @optional specification."""
    inner_local_field = LocalField(inner_location_name)
    inner_location_existence = BinaryComposition(u'!=', inner_local_field, NullLiteral)

    edge_field_location = Location(root_location_path, field=edge_field)
    select_edge_context_field = SelectEdgeContextField(edge_field_location)
    edge_field_non_existence = filter_edge_field_non_existence(select_edge_context_field)

    return BinaryComposition(u'||', edge_field_non_existence, inner_location_existence)


class SelectWhereFilter(Filter):
    """A Filter object that is used for the WHERE clause in a SELECT statement."""

    def __init__(self, simple_optional_root_info):
        """Construct a Filter block that is True if and only if each simple optional filter is True.

        Construct filters for each simple optional, that are True if and only if `edge_field` does
        not exist in the `simple_optional_root_location` OR the `inner` location is not defined.
        Return a SelectWhereFilter that evaluates to True if and only if *all* of the
        aforementioned filters evaluate to True (conjunction).

        Args:
            simple_optional_root_info: dict mapping from simple_optional_root_location -> dict
                                       containing keys
                                       - 'inner_location': Location object correspoding to the unique
                                                           MarkLocation present within a simple
                                                           @optional (one that does not expands
                                                           vertex fields) scope
                                       - 'edge_field': string representing the optional edge being
                                                       traversed
                                       where simple_optional_root_to_inner_location is the location
                                       preceding the @optional scope
        Returns:
            a new SelectWhereFilter object
        """
        where_filter_expressions = []
        for root_location, root_info_dict in six.iteritems(simple_optional_root_info):
            inner_location_name = root_info_dict['inner_location_name']
            edge_field = root_info_dict['edge_field']

            optional_edge_filter = filter_orientdb_simple_optional_edge(
                root_location.query_path, inner_location_name, edge_field)
            where_filter_expressions.append(optional_edge_filter)

        predicate = expression_list_to_conjunction(where_filter_expressions)
        super(SelectWhereFilter, self).__init__(predicate)


###
# A CompoundMatchQuery is a representation of several MatchQuery objects containing
#   - match_queries: a list MatchQuery objects
CompoundMatchQuery = namedtuple('CompoundMatchQuery', ('match_queries'))
