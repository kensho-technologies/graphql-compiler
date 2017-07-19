# Copyright 2017 Kensho Technologies, Inc.
from .expressions import Expression
from .helpers import (CompilerEntity, ensure_unicode_string, safe_quoted_string,
                      validate_marked_location, validate_safe_string)


class BasicBlock(CompilerEntity):
    """A basic operation block of the GraphQL compiler."""

    def visit_and_update_expressions(self, visitor_fn):
        """Create an updated version (if needed) of the BasicBlock via the visitor pattern.

        Args:
            visitor_fn: function that takes an Expression argument, and returns an Expression.
                        This function is recursively called on all child Expressions that may
                        exist within this BasicBlock. If the visitor_fn does not return the
                        exact same object that was passed in, this is interpreted as an update
                        request, and the visit_and_update() method will return a new BasicBlock
                        with the given update applied. No Expressions or BasicBlocks are
                        mutated in-place.

        Returns:
            - If the visitor_fn does not request any updates (by always returning the exact same
              object it was called with), this method returns 'self'.
            - Otherwise, this method returns a new BasicBlock object that reflects the updates
              requested by the visitor_fn.
        """
        # Most BasicBlocks do not contain expressions, and immediately return 'self'.
        # Any BasicBlocks that contain Expressions will override this method.
        return self


class QueryRoot(BasicBlock):
    """The starting object of the query to be compiled."""

    def __init__(self, start_class):
        """Construct a QueryRoot object that starts querying at the specified class name.

        Args:
            start_class: set of basestring, class names from which to start the query.
                         This will generally be a set of length 1, except when using Gremlin
                         with a non-final class, where we have to include all subclasses
                         of the start class. This is done using a Gremlin-only IR lowering step.

        Returns:
            new QueryRoot object
        """
        super(QueryRoot, self).__init__(start_class)
        self.start_class = start_class
        self.validate()

    def validate(self):
        """Ensure that the QueryRoot block is valid."""
        if not (isinstance(self.start_class, set) and
                all(isinstance(x, basestring) for x in self.start_class)):
            raise TypeError(u'Expected set of basestring start_class, got: {} {}'.format(
                type(self.start_class).__name__, self.start_class))

        for cls in self.start_class:
            validate_safe_string(cls)

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()
        if len(self.start_class) == 1:
            # The official Gremlin documentation claims that this approach
            # is generally faster than the one below, since it makes using indexes easier.
            # http://gremlindocs.spmallette.documentup.com/#filter/has
            start_class = list(self.start_class)[0]
            return u'g.V({}, {})'.format('\'@class\'', safe_quoted_string(start_class))
        else:
            start_classes_list = ','.join(safe_quoted_string(x) for x in self.start_class)
            return u'g.V.has(\'@class\', T.in, [{}])'.format(start_classes_list)


class CoerceType(BasicBlock):
    """A special type of filter that discards any data that is not of the specified set of types."""

    def __init__(self, target_class):
        """Construct a CoerceType object that filters out any data that is not of the given types.

        Args:
            target_class: set of basestring, class names from which to start the query.
                          This will generally be a set of length 1, except when using Gremlin
                          with a non-final class, where we have to include all subclasses
                          of the target class. This is done using a Gremlin-only IR lowering step.

        Returns:
            new CoerceType object
        """
        super(CoerceType, self).__init__(target_class)
        self.target_class = target_class
        self.validate()

    def validate(self):
        """Ensure that the CoerceType block is valid."""
        if not (isinstance(self.target_class, set) and
                all(isinstance(x, basestring) for x in self.target_class)):
            raise TypeError(u'Expected set of basestring target_class, got: {} {}'.format(
                type(self.target_class).__name__, self.target_class))

        for cls in self.target_class:
            validate_safe_string(cls)

    def to_gremlin(self):
        """Not implemented, should not be used."""
        raise AssertionError(u'CoerceType blocks must be appropriately lowered before being '
                             u'transformed into Gremlin code. This function should not be used.')


class ConstructResult(BasicBlock):
    """A transformation of the data into a new form, for output."""

    def __init__(self, fields):
        """Construct a ConstructResult object that maps the given field names to their expressions.

        Args:
            fields: dict, variable name basestring -> Expression
                    see rules for variable names in validate_safe_string().

        Returns:
            new ConstructResult object
        """
        self.fields = {
            ensure_unicode_string(key): value
            for key, value in fields.iteritems()
        }

        # All key values are normalized to unicode before being passed to the parent constructor,
        # which saves them to enable human-readable printing and other functions.
        super(ConstructResult, self).__init__(self.fields)
        self.validate()

    def validate(self):
        """Ensure that the ConstructResult block is valid."""
        if not isinstance(self.fields, dict):
            raise TypeError(u'Expected dict fields, got: {} {}'.format(
                type(self.fields).__name__, self.fields))

        for key, value in self.fields.iteritems():
            validate_safe_string(key)
            if not isinstance(value, Expression):
                raise TypeError(
                    u'Expected Expression values in the fields dict, got: '
                    u'{} -> {}'.format(key, value))

    def visit_and_update_expressions(self, visitor_fn):
        """Create an updated version (if needed) of the ConstructResult via the visitor pattern."""
        new_fields = {}

        for key, value in self.fields.iteritems():
            new_value = value.visit_and_update(visitor_fn)
            if new_value is not value:
                new_fields[key] = new_value

        if new_fields:
            return ConstructResult(dict(self.fields, **new_fields))
        else:
            return self

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()

        template = (
            u'transform{{'
            u'it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([ {} ])'
            u'}}')

        field_representations = (
            u'{name}: {expr}'.format(name=key, expr=self.fields[key].to_gremlin())
            for key in sorted(self.fields.keys())  # Sort the keys for deterministic output order.
        )
        return template.format(u', '.join(field_representations))


class Filter(BasicBlock):
    """A filter that ensures data matches a predicate expression, and discards all other data."""

    def __init__(self, predicate):
        """Create a new Filter with the specified Expression as a predicate."""
        super(Filter, self).__init__(predicate)
        self.predicate = predicate
        self.validate()

    def validate(self):
        """Ensure that the Filter block is valid."""
        if not isinstance(self.predicate, Expression):
            raise TypeError(u'Expected Expression predicate, got: {} {}'.format(
                type(self.predicate).__name__, self.predicate))

    def visit_and_update_expressions(self, visitor_fn):
        """Create an updated version (if needed) of the Filter via the visitor pattern."""
        new_predicate = self.predicate.visit_and_update(visitor_fn)
        if new_predicate is not self.predicate:
            return Filter(new_predicate)
        else:
            return self

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()
        return u'filter{{it, m -> {}}}'.format(self.predicate.to_gremlin())


class MarkLocation(BasicBlock):
    """A block that assigns a name to a given location in the query."""

    def __init__(self, location):
        """Create a new MarkLocation at the specified Location.

        Args:
            location: Location object, must not be at a property field in the query

        Returns:
            new MarkLocation object
        """
        super(MarkLocation, self).__init__(location)
        self.location = location
        self.validate()

    def validate(self):
        """Ensure that the MarkLocation block is valid."""
        validate_marked_location(self.location)

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()
        mark_name, _ = self.location.get_location_name()
        return u'as({})'.format(safe_quoted_string(mark_name))


class Traverse(BasicBlock):
    """A block that encodes a traversal across an edge, in either direction."""

    def __init__(self, direction, edge_name, optional=False):
        """Create a new Traverse block in the given direction and across the given edge.

        Args:
            direction: basestring, 'in' or 'out'
            edge_name: basestring obeying variable name rules (see validate_safe_string).
            optional: optional bool, specifying whether the traversal to the given location
                      is optional (i.e. non-filtering) or mandatory (filtering).

        Returns:
            new Traverse object
        """
        super(Traverse, self).__init__(direction, edge_name, optional=optional)
        self.direction = direction
        self.edge_name = edge_name
        self.optional = optional
        self.validate()

    def validate(self):
        """Ensure that the Traverse block is valid."""
        if not isinstance(self.direction, basestring):
            raise TypeError(u'Expected basestring direction, got: {} {}'.format(
                type(self.direction).__name__, self.direction))

        if self.direction not in {u'in', u'out'}:
            raise ValueError(u'Expected direction to be "in" or "out", got: '
                             u'{}'.format(self.direction))

        if not isinstance(self.optional, bool):
            raise TypeError(u'Expected bool optional, got: {} {}'.format(
                type(self.optional).__name__, self.optional))

        validate_safe_string(self.edge_name)

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()
        if self.optional:
            # Optional edges have to be handled differently than non-optionals, since the compiler
            # provides the guarantee that properties read from an optional, non-existing location
            # always resolve to a "null" value. This guarantee is not upheld by default by Gremlin;
            # in fact, Gremlin .as('foo').out().as('bar').optional('foo') does not provide
            # ANY guarantees as to what the value at any "bar.*" is -- it could be "null",
            # it could be a previous pipeline element's location at "bar.*" or anything else.
            # The .ifThenElse block ensures that the edge traversal happens only if the edge exists,
            # and that otherwise the result in the pipeline is replaced with "null".
            #
            # The code below makes the assumption that links to outward/inward edges are stored
            # as vertex properties named "<direction>_<edge_name>" where direction is "in" or "out".
            # For example, the links to outward edges named "Person_SpeechBy" from Person
            # are assumed to be stored as "out_Person_SpeechBy" on the Person node.
            return (u'ifThenElse{{it.{direction}_{edge_name} == null}}'
                    u'{{null}}{{it.{direction}({edge_quoted})}}'.format(
                        direction=self.direction,
                        edge_name=self.edge_name,
                        edge_quoted=safe_quoted_string(self.edge_name)))
        else:
            return u'{direction}({edge})'.format(
                direction=self.direction,
                edge=safe_quoted_string(self.edge_name))


class Recurse(BasicBlock):
    """A block for recursive traversal of an edge, collecting all endpoints along the way."""

    def __init__(self, direction, edge_name, depth):
        """Create a new Recurse block which traverses the given edge up to "depth" times.

        Args:
            direction: basestring, 'in' or 'out'.
            edge_name: basestring obeying variable name rules (see validate_safe_string).
            depth: int, always greater than or equal to 1.

        Returns:
            new Recurse object
        """
        super(Recurse, self).__init__(direction, edge_name, depth)
        self.direction = direction
        self.edge_name = edge_name
        self.depth = depth
        self.validate()

    def validate(self):
        """Ensure that the Traverse block is valid."""
        if not isinstance(self.direction, basestring):
            raise TypeError(u'Expected basestring direction, got: {} {}'.format(
                type(self.direction).__name__, self.direction))

        if self.direction not in {u'in', u'out'}:
            raise ValueError(u'Expected direction to be "in" or "out", got: '
                             u'{}'.format(self.direction))

        validate_safe_string(self.edge_name)

        if not isinstance(self.depth, int):
            raise TypeError(u'Expected int depth, got: {} {}'.format(
                type(self.depth).__name__, self.depth))

        if not (self.depth >= 1):
            raise ValueError(u'depth ({}) >= 1 does not hold!'.format(self.depth))

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()
        template = 'copySplit({recurse}).exhaustMerge'
        recurse_base = '_()'
        recurse_traversal = '.{direction}(\'{edge_name}\')'.format(
            direction=self.direction, edge_name=self.edge_name)

        recurse_steps = [
            recurse_base + (recurse_traversal * i)
            for i in xrange(self.depth + 1)
        ]
        return template.format(recurse=','.join(recurse_steps))


class Backtrack(BasicBlock):
    """A block that specifies a return to a given Location in the query."""

    def __init__(self, location, optional=False):
        """Create a new Backtrack block, returning to the given location in the query.

        Args:
            location: Location object, specifying where to backtrack to
            optional: optional bool, specifying whether the steps between the current location
                      and the location to which Backtrack is returning were optional or not

        Returns:
            new Backtrack object
        """
        super(Backtrack, self).__init__(location, optional=optional)
        self.location = location
        self.optional = optional
        self.validate()

    def validate(self):
        """Ensure that the Backtrack block is valid."""
        validate_marked_location(self.location)
        if not isinstance(self.optional, bool):
            raise TypeError(u'Expected bool optional, got: {} {}'.format(
                type(self.optional).__name__, self.optional))

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this BasicBlock."""
        self.validate()
        if self.optional:
            operation = u'optional'
        else:
            operation = u'back'

        mark_name, _ = self.location.get_location_name()

        return u'{operation}({mark_name})'.format(
            operation=operation,
            mark_name=safe_quoted_string(mark_name))


class OutputSource(BasicBlock):
    """A block that declares the output should have >= 1 row for each value at that location.

    This block, together with the @output_source directive that generates it,
    is a mitigation strategy that allows users to specify *which* set of results they want
    fully covered. Namely, OutputSource on a given location will ensure that all possible
    values at that location are represented in at least one row of the returned result set.

    See the comment on the @output_source directive in schema.py on why this is necessary.
    """

    def __init__(self):
        """Create a new OutputSource block."""
        super(OutputSource, self).__init__()
        self.validate()

    def validate(self):
        """Ensure that the OutputSource block is valid.

        OutputSource blocks are always valid in isolation.
        """
        pass

    def to_gremlin(self):
        """Return the unicode representation of this BasicBlock.

        The correct Gremlin representation of OutputSource blocks is an empty string.
        Their effect is applied during code generation and optimization passes.
        """
        return u''
