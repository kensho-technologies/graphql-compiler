# Copyright 2020-present Kensho Technologies, LLC.
import unittest

from ..global_utils import assert_set_equality, checked_cast, checked_cast_to_union2


class GlobalUtilTests(unittest.TestCase):
    def test_assert_equality(self) -> None:
        # Matching sets
        assert_set_equality({"a", "b"}, {"a", "b"})

        # Additional keys in the first set
        with self.assertRaises(AssertionError):
            assert_set_equality({"a", "b"}, {"b"})

        # Additional keys in the second type
        with self.assertRaises(AssertionError):
            assert_set_equality({"b"}, {"a", "b"})

        # Different sets with same number of elements
        with self.assertRaises(AssertionError):
            assert_set_equality({"a", "b"}, {"c", "b"})

        # Different types
        with self.assertRaises(AssertionError):
            assert_set_equality({"a"}, {1})

    def test_checked_cast(self) -> None:
        checked_cast(int, 123)
        checked_cast(str, "foo")

        with self.assertRaises(AssertionError):
            checked_cast(int, "foo")

        with self.assertRaises(AssertionError):
            checked_cast(int, None)

    def test_checked_cast_to_union2(self) -> None:
        checked_cast_to_union2((int, str), 123)
        checked_cast_to_union2((int, str), "foo")

        with self.assertRaises(AssertionError):
            checked_cast_to_union2((int, str), None)

        with self.assertRaises(AssertionError):
            checked_cast_to_union2((bool, str), 123)
