# Copyright 2020-present Kensho Technologies, LLC.
import unittest

from ..global_utils import generate_new_name


class GlobalUtilsTests(unittest.TestCase):
    """Test the global_utils module."""

    def test_generate_new_name(self):
        taken_names = ["animal_0", "animal_1"]

        new_name = generate_new_name("animal", taken_names)
        self.assertEqual("animal", new_name)

        new_name = generate_new_name("animal_0", taken_names)
        self.assertTrue(new_name not in taken_names)
