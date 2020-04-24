from types import MappingProxyType
import unittest

from ..global_utils import assert_that_mappings_have_the_same_keys


class GlobalUtilTests(unittest.TestCase):
    def test_assert_that_mappings_have_the_same_keys(self):
        # Matching keys
        assert_that_mappings_have_the_same_keys({"a": 1, "b": 2}, {"a": 2, "b": 1})

        # Additional keys in the first dict
        with self.assertRaises(AssertionError):
            assert_that_mappings_have_the_same_keys({"a": 1, "b": 2}, {"a": 2})

        # Additional keys in the second dict
        with self.assertRaises(AssertionError):
            assert_that_mappings_have_the_same_keys({"a": 2}, {"a": 1, "b": 2})

        # Matching keys with non-dict maps
        assert_that_mappings_have_the_same_keys(
            MappingProxyType({"a": 1, "b": 2}), MappingProxyType({"b": 1, "a": 2})
        )

        # Mismatching keys of non-dict maps
        with self.assertRaises(AssertionError):
            assert_that_mappings_have_the_same_keys(
                MappingProxyType({"a": 1, "b": 2}), MappingProxyType({"a": 2})
            )

        # Same keys but different map types
        assert_that_mappings_have_the_same_keys(
            {"a": 1, "b": 2}, MappingProxyType({"a": 2, "b": 1})
        )
