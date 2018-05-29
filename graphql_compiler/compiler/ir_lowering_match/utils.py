# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple

from ..compiler_entities import BasicBlock
from ..expressions import Expression, LocalField


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


class WhereClause(BasicBlock):
    """A `WHERE` Expression, to filter the results of a SELECT-MATCH statement."""

    def __init__(self, expressions):
        """Construct a WHERE clause that filters on the conjunction of the given expressions."""
        super(BetweenClause, self).__init__(expressions)
        self.expressions = expressions
        self.validate()

    def validate(self):
        """Validate that the Between Expression is correctly representable."""
        if not isinstance(self.expressions, list):
            raise TypeError(u'Expected list expressions, got: {} {}'.format(
                type(self.expressions).__name__, self.expressions))

        for expression in expressions:
            if not isinstance(self.expression, LocalField):
                raise TypeError(u'Expected Expression expression, got: {} {}'.format(
                    type(self.expression).__name__, self.expression))

    def to_match(self):
        """Return a unicode object with the MATCH representation of this BetweenClause."""
        match_expressions_list = [expression.to_match() for expression in self.expressions]
        expressions_conjunction_string = ' AND '.join(match_expressions_list)
        template = u'(BETWEEN {expressions_conjunction_string})'
        return template.format(expressions_conjunction_string=expressions_conjunction_string)


###
# A CompoundMatchQuery is a representation of several MatchQuery objects containing
#   - match_queries: a list MatchQuery objects
CompoundMatchQuery = namedtuple('CompoundMatchQuery', ('match_queries'))
