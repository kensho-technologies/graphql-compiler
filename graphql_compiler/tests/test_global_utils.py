# Copyright 2020-present Kensho Technologies, LLC.
import unittest

from ..global_utils import generate_new_name


class GlobalUtilsTests(unittest.TestCase):
    """Test the global_utils module."""

    def test_generate_new_name(self):
        taken_names = ["bird", "plane", "plane_0"]

        new_name = generate_new_name("animal", taken_names)
        self.assertEqual("animal_0", new_name)

        new_name = generate_new_name("bird", taken_names)
        self.assertEqual("bird_0", new_name)

        new_name = generate_new_name("plane", taken_names)
        self.assertEqual("plane_1", new_name)
