# Copyright 2020-present Kensho Technologies, LLC.
import unittest

from ..global_utils import assert_set_equality


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
