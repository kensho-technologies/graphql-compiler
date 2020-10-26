# Copyright 2019-present Kensho Technologies, LLC.
import unittest

from ..compiler.subclass import compute_subclass_sets
from .test_helpers import get_schema


class SubclassTests(unittest.TestCase):
    """Ensure we correctly compute subclass sets."""

    def setUp(self):
        """Initialize the test schema once for all tests."""
        self.schema = get_schema()

    def test_compute_subclass_sets(self) -> None:
        type_equivalence_hints = {
            self.schema.get_type("Event"): self.schema.get_type(
                "Union__BirthEvent__Event__FeedingEvent"
            ),
        }

        subclass_sets = compute_subclass_sets(
            self.schema, type_equivalence_hints=type_equivalence_hints
        )
        cases = [
            ("Entity", "Entity", True),
            ("Animal", "Animal", True),
            ("Animal", "Entity", True),
            ("Entity", "Animal", False),
            ("Species", "Entity", True),
            ("BirthEvent", "Event", True),  # Derived from the type_equivalence_hints
        ]
        for cls1, cls2, expected in cases:
            is_subclass = cls1 in subclass_sets[cls2]
            self.assertEqual(
                expected,
                is_subclass,
                "{} is subclass of {} evaluates to {}. Expected: {}".format(
                    cls1, cls2, is_subclass, expected
                ),
            )
