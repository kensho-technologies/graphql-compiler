# Copyright 2020-present Kensho Technologies, LLC.
from typing import Any, Tuple
import unittest

from ...interpreter.immutable_stack import make_empty_stack


class ImmutableStackTests(unittest.TestCase):
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
            actual_pop_value, stack = stack.pop()

            # The popped value is referentially equal to the value we originally pushed.
            self.assertIs(expected_pop_value, actual_pop_value)

        # At the end of all the pushing and popping, the final stack is empty
        # and referentially equal to the initial stack.
        self.assertIsNone(stack.value)
        self.assertEqual(0, stack.depth)
        self.assertIsNone(stack.tail)
        self.assertIs(initial_stack, stack)
