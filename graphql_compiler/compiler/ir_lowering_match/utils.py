# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple

import six

from ..blocks import Filter
from ..expressions import (BinaryComposition, Expression, LocalField, NullLiteral,
                           SelectEdgeContextField, TrueLiteral, UnaryTransformation, ZeroLiteral)
from ..helpers import Location


def filter_edge_field_non_existence(edge_expression):
    # TODO(shankha): Update docstring <30-05-18>
    """Return an Expression that is True iff the specified edge (expression) does not exist."""
    # When an edge does not exist at a given vertex, OrientDB represents that in one of two ways:
    #   - the edge's field does not exist (is null) on the vertex document, or
    #   - the edge's field does exist, but is an empty list.
    # We check both of these possibilities.
    # TODO(shankha): Assert expression type <30-05-18>
    if not isinstance(edge_expression, (LocalField, SelectEdgeContextField)):
        raise AssertionError(u'Received invalid edge_expression {} of type {}.'
                             u'Expected LocalField or SelectEdgeContextField.'
                             .format(edge_expression, type(edge_expression.__name__))

    field_null_check = BinaryComposition(u'=', edge_expression, NullLiteral)

    local_field_size = UnaryTransformation(u'size', edge_expression)
    field_size_check = BinaryComposition(u'=', local_field_size, ZeroLiteral)

    return BinaryComposition(u'||', field_null_check, field_size_check)


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


class SelectWhereFilter(Filter):
    # TODO(shankha): Fix docstring <30-05-18>#
    """A filter that ensures data matches a predicate expression, and discards all other data."""

    def __init__(self, simple_optional_root_info):
        # TODO(shankha): Docstring <30-05-18>
        where_filter_expressions = []
        for root_location, root_info_dict in six.iteritems(simple_optional_root_info):
            edge_field = root_info_dict['edge_field']
            edge_field_location = Location(root_location.query_path, field=edge_field)
            select_edge_context_field = SelectEdgeContextField(edge_field_location)
            edge_field_non_existence = filter_edge_field_non_existence(select_edge_context_field)

            inner_location, _ = root_info_dict['inner_location'].get_location_name()
            inner_local_field = LocalField(inner_location)
            inner_location_existence = BinaryComposition(u'!=', inner_local_field, NullLiteral)

            where_filter_expressions.append(BinaryComposition(u'||',
                                                              edge_field_non_existence,
                                                              inner_location_existence))

        predicate = expression_list_to_conjunction(where_filter_expressions)
        super(SelectWhereFilter, self).__init__(predicate)


###
# A CompoundMatchQuery is a representation of several MatchQuery objects containing
#   - match_queries: a list MatchQuery objects
CompoundMatchQuery = namedtuple('CompoundMatchQuery', ('match_queries'))
