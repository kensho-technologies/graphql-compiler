# Copyright 2020-present Kensho Technologies, LLC.
import unittest

from ..global_utils import find_new_name


class QueryPaginationTests(unittest.TestCase):
    """Test the global_utils module"""

    def test_find_new_name(self):
        taken_names = ["animal_0", "animal_1"]

        new_name = find_new_name("animal", taken_names, try_original=False)
        self.assertTrue(new_name not in taken_names)

        new_name = find_new_name("animal", taken_names, try_original=True)
        self.assertTrue(new_name not in taken_names)
        self.assertEqual("animal", new_name)
