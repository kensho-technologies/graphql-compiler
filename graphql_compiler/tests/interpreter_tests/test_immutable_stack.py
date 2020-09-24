# Copyright 2020-present Kensho Technologies, LLC.
from copy import copy, deepcopy
from typing import Any, Tuple, cast
import unittest

from ...interpreter.immutable_stack import ImmutableStack, make_empty_stack


class ImmutableStackTests(unittest.TestCase):
    def test_equality(self) -> None:
        stack_a = make_empty_stack().push(123)
        stack_b = make_empty_stack().push(123)
        self.assertEqual(stack_a, stack_b)

        self.assertNotEqual(make_empty_stack(), stack_a)
        self.assertNotEqual(stack_a.push("foo"), stack_b)

    def test_make_push_and_pop(self) -> None:
        initial_stack = make_empty_stack()
        self.assertIsNone(initial_stack.value)
        self.assertEqual(0, initial_stack.depth)
        self.assertIsNone(initial_stack.tail)

        new_stack = initial_stack
        values_to_push: Tuple[Any, ...] = (123, "hello world", None)
        for index, value_to_push in enumerate(values_to_push):
            stack = new_stack
            new_stack = stack.push(value_to_push)

            # After the push:
            # - the stack depth has increased by one;
            self.assertEqual(index + 1, new_stack.depth)
            # - the stack's topmost value is referentially equal to the value we just pushed;
            self.assertIs(value_to_push, new_stack.value)
            # - the stack's tail is referentially equal to the pre-push stack.
            self.assertIs(stack, new_stack.tail)

        stack = new_stack
        for expected_pop_value in reversed(values_to_push):
            actual_pop_value, popped_stack = stack.pop()

            # The popped stack isn't None because it should still have leftover values.
            self.assertIsNotNone(popped_stack)
            # Cast because mypy doesn't realize the previous line will raise on None.
            stack = cast(ImmutableStack, popped_stack)

            # The popped value is referentially equal to the value we originally pushed.
            self.assertIs(expected_pop_value, actual_pop_value)

        # At the end of all the pushing and popping, the final stack is empty
        # and referentially equal to the initial stack.
        self.assertIsNone(stack.value)
        self.assertEqual(0, stack.depth)
        self.assertIsNone(stack.tail)
        self.assertIs(initial_stack, stack)

    def test_stack_copy(self) -> None:
        pushed_value = {
            1: "foo",
            2: "bar",
        }
        stack = make_empty_stack().push(pushed_value)

        # copy() makes a new stack node but keeps all its references the same.
        # This is why we check referential equality for the value and the tail.
        copied_stack = copy(stack)
        self.assertIs(stack.value, copied_stack.value)
        self.assertEqual(stack.depth, copied_stack.depth)
        self.assertIs(stack.tail, copied_stack.tail)

        # Just a consistency check, if this following fails then something has gone horribly wrong.
        self.assertEqual(stack, copied_stack)

    def test_stack_deepcopy(self) -> None:
        pushed_value = {
            1: "foo",
            2: "bar",
        }
        stack = make_empty_stack().push(pushed_value)

        # deepcopy() makes a new stack node and also makes deep copies of all its references.
        # This is why we check for lack of referential equality for the value and tail, even though
        # we check for equality of the given objects.
        copied_stack = deepcopy(stack)
        self.assertIsNot(stack.value, copied_stack.value)
        self.assertEqual(stack.depth, copied_stack.depth)
        self.assertIsNot(stack.tail, copied_stack.tail)
        self.assertEqual(stack, copied_stack)
