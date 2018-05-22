# Copyright 2017-present Kensho Technologies, LLC.
"""Base classes for compiler entity objects like basic blocks and expressions."""

from abc import ABCMeta, abstractmethod

import six


@six.python_2_unicode_compatible
@six.add_metaclass(ABCMeta)
class CompilerEntity(object):
    """An abstract compiler entity. Can represent things like basic blocks and expressions."""

    def __init__(self, *args, **kwargs):
        """Construct a new CompilerEntity."""
        self._print_args = args
        self._print_kwargs = kwargs

    @abstractmethod
    def validate(self):
        """Ensure that the CompilerEntity is valid."""
        raise NotImplementedError()

    def __str__(self):
        """Return a human-readable unicode representation of this CompilerEntity."""
        printed_args = []
        if self._print_args:
            printed_args.append('{args}')
        if self._print_kwargs:
            printed_args.append('{kwargs}')

        template = u'{cls_name}(' + u', '.join(printed_args) + u')'
        return template.format(cls_name=type(self).__name__,
                               args=self._print_args,
                               kwargs=self._print_kwargs)

    def __repr__(self):
        """Return a human-readable str representation of the CompilerEntity object."""
        return self.__str__()

    # pylint: disable=protected-access
    def __eq__(self, other):
        """Return True if the CompilerEntity objects are equal, and False otherwise."""
        return (type(self) == type(other) and
                self._print_args == other._print_args and
                self._print_kwargs == other._print_kwargs)
    # pylint: enable=protected-access

    def __ne__(self, other):
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)

    @abstractmethod
    def to_gremlin(self):
        """Return the Gremlin unicode string representation of this object."""
        raise NotImplementedError()


@six.add_metaclass(ABCMeta)
class Expression(CompilerEntity):
    """An expression that produces a value in the GraphQL compiler."""

    def visit_and_update(self, visitor_fn):
        """Create an updated version (if needed) of the Expression via the visitor pattern.

        Args:
            visitor_fn: function that takes an Expression argument, and returns an Expression.
                        This function is recursively called on all child Expressions that may
                        exist within this expression. If the visitor_fn does not return the
                        exact same object that was passed in, this is interpreted as an update
                        request, and the visit_and_update() method will return a new Expression
                        with the given update applied. No Expressions are mutated in-place.

        Returns:
            - If the visitor_fn does not request any updates (by always returning the exact same
              object it was called with), this method returns 'self'.
            - Otherwise, this method returns a new Expression object that reflects the updates
              requested by the visitor_fn.
        """
        # Most Expressions simply visit themselves.
        # Any Expressions that contain Expressions will override this method.
        return visitor_fn(self)


@six.add_metaclass(ABCMeta)
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


@six.add_metaclass(ABCMeta)
class MarkerBlock(BasicBlock):
    """A block that is used to mark that a context-affecting operation with no output happened."""

    def to_gremlin(self):
        """Return the Gremlin representation of the block, which should almost always be empty.

        The effect of MarkerBlocks is applied during optimization and code generation steps.
        """
        return u''
