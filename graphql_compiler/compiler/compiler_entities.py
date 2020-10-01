# Copyright 2017-present Kensho Technologies, LLC.
"""Base classes for compiler entity objects like basic blocks and expressions."""

from abc import ABCMeta, abstractmethod
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, Union

from graphql import is_type
import six
from sqlalchemy.sql.selectable import CTE, Alias

from ..global_utils import is_same_type


@six.python_2_unicode_compatible
@six.add_metaclass(ABCMeta)
class CompilerEntity(object):
    """An abstract compiler entity. Can represent things like basic blocks and expressions."""

    __slots__ = ("_print_args", "_print_kwargs")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Construct a new CompilerEntity."""
        self._print_args = args
        self._print_kwargs = kwargs

    @abstractmethod
    def validate(self) -> None:
        """Ensure that the CompilerEntity is valid."""
        raise NotImplementedError()

    def __str__(self) -> str:
        """Return a human-readable unicode representation of this CompilerEntity."""
        printed_args = []
        if self._print_args:
            printed_args.append("{args}")
        if self._print_kwargs:
            printed_args.append("{kwargs}")

        template = "{cls_name}(" + ", ".join(printed_args) + ")"
        return template.format(
            cls_name=type(self).__name__, args=self._print_args, kwargs=self._print_kwargs
        )

    def __repr__(self) -> str:
        """Return a human-readable str representation of the CompilerEntity object."""
        return self.__str__()

    # pylint: disable=protected-access
    def __eq__(self, other: Any) -> bool:
        """Return True if the CompilerEntity objects are equal, and False otherwise."""
        if type(self) != type(other):
            return False

        if len(self._print_args) != len(other._print_args):
            return False

        # The args sometimes contain GraphQL type objects, which unfortunately do not define "==".
        # We have to split them out and compare them using "is_same_type()" instead.
        for self_arg, other_arg in six.moves.zip(self._print_args, other._print_args):
            if is_type(self_arg):
                if not is_same_type(self_arg, other_arg):
                    return False
            else:
                if self_arg != other_arg:
                    return False

        return self._print_kwargs == other._print_kwargs

    # pylint: enable=protected-access

    def __ne__(self, other: Any) -> bool:
        """Check another object for non-equality against this one."""
        return not self.__eq__(other)

    def to_gremlin(self) -> str:
        """Return the Gremlin unicode string representation of this object."""
        raise NotImplementedError()


AliasType = Union[Alias, CTE]
AliasesDictType = Dict[
    Tuple[
        Tuple[str, ...],
        Optional[Tuple[Tuple[str, str], ...]],
    ],
    AliasType,
]


@six.add_metaclass(ABCMeta)
class Expression(CompilerEntity):
    """An expression that produces a value in the GraphQL compiler."""

    __slots__ = ()

    def visit_and_update(self, visitor_fn: Callable[["Expression"], "Expression"]) -> "Expression":
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

    def to_match(self) -> str:
        """Return a string with the MATCH representation of this Expression."""
        raise NotImplementedError()

    def to_cypher(self) -> str:
        """Return a string with the Cypher representation of this Expression."""
        raise NotImplementedError()

    def to_sql(self, dialect: Any, aliases: AliasesDictType, current_alias: AliasType) -> Any:
        """Return a SQLAlchemy object with the SQL representation of this Expression."""
        raise NotImplementedError()


BasicBlockT = TypeVar("BasicBlockT", bound="BasicBlock")


@six.add_metaclass(ABCMeta)
class BasicBlock(CompilerEntity):
    """A basic operation block of the GraphQL compiler."""

    __slots__ = ()

    def visit_and_update_expressions(
        self: BasicBlockT, visitor_fn: Callable[[Expression], Expression]
    ) -> BasicBlockT:
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

            Since the visitor_fn does not transform BasicBlock types, the type returned by
            this function is guaranteed to be the same as the type of the "self" argument.
            To learn more about how the BasicBlockT type variable accomplishes this, see PEP484:
            https://www.python.org/dev/peps/pep-0484/#annotating-instance-and-class-methods
        """
        # Most BasicBlocks do not contain expressions, and immediately return 'self'.
        # Any BasicBlocks that contain Expressions will override this method.
        return self


@six.add_metaclass(ABCMeta)
class MarkerBlock(BasicBlock):
    """A block that is used to mark that a context-affecting operation with no output happened."""

    __slots__ = ()

    def to_gremlin(self) -> str:
        """Return the Gremlin representation of the block, which should almost always be empty.

        The effect of MarkerBlocks is applied during optimization and code generation steps.
        """
        return ""

    def to_cypher(self) -> str:
        """Return the Cypher representation of the block, which should almost always be empty.

        The effect of MarkerBlocks is applied during optimization and code generation steps.
        """
        return ""
