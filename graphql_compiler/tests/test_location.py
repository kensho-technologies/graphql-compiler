# Copyright 2017-present Kensho Technologies, LLC.
from typing import List
import unittest

from ..compiler.helpers import BaseLocation, FoldScopeLocation, Location


def compare_sorted_locations_list(
    test_case: unittest.TestCase, sorted_locations: List[BaseLocation]
) -> None:
    """Ensure that the given list of locations is in ascending order."""
    for i, first_location in enumerate(sorted_locations):
        for j, second_location in enumerate(sorted_locations):
            expected_comparison = i < j
            received_comparison = first_location < second_location
            test_case.assertEqual(
                expected_comparison,
                received_comparison,
                msg=(
                    "{} < {}, expected result {} but got {}".format(
                        first_location, second_location, expected_comparison, received_comparison
                    )
                ),
            )


class LocationTests(unittest.TestCase):
    def test_location_name(self) -> None:
        base_location = Location(("Animal",))
        self.assertEqual(("Animal___1", None), base_location.get_location_name())

        base_at_field = base_location.navigate_to_field("name")
        self.assertEqual(("Animal___1", "name"), base_at_field.get_location_name())

        revisited_location = base_location.revisit()
        self.assertEqual(("Animal___2", None), revisited_location.get_location_name())

        revisited_at_field = revisited_location.navigate_to_field("name")
        self.assertEqual(("Animal___2", "name"), revisited_at_field.get_location_name())

        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        self.assertEqual(
            ("Animal__out_Animal_ParentOf___1", None), child_location.get_location_name()
        )

        child_at_field = child_location.navigate_to_field("name")
        self.assertEqual(
            ("Animal__out_Animal_ParentOf___1", "name"), child_at_field.get_location_name()
        )

    def test_location_comparisons(self) -> None:
        sorted_locations = [
            Location(("Animal", "in_Animal_Parent_of"), "uuid", 3),
            Location(("Animal", "in_Animal_Parent_of", "in_Animal_FedAt"), "name", 2),
            Location(("Animal", "in_Animal_Parent_of", "out_Animal_FedAt"), "name", 1),
            Location(("Animal", "in_Animal_Parent_of", "out_Animal_FedAt"), None, 2),
            Location(("Animal", "in_Animal_Parent_of", "out_Animal_FedAt"), "name", 2),
            Location(("Animal", "in_Animal_Parent_of", "out_Animal_FedAt"), "uuid", 2),
        ]
        for i, first_location in enumerate(sorted_locations):
            for j, second_location in enumerate(sorted_locations):
                expected_comparison = i < j
                received_location_comparison = first_location < second_location
                self.assertEqual(expected_comparison, received_location_comparison)

    def test_fold_scope_location_comparisons(self) -> None:
        sorted_locations = [
            FoldScopeLocation(
                Location(("Animal", "in_Animal_Parent_of")),
                (
                    (
                        "in",
                        "Animal_OfSpecies",
                    ),
                ),
                None,
            ),
            FoldScopeLocation(
                Location(("Animal", "in_Animal_Parent_of")),
                (
                    (
                        "out",
                        "Animal_OfSpecies",
                    ),
                ),
                None,
            ),
            FoldScopeLocation(
                Location(("Animal", "in_Animal_Parent_of")),
                (
                    (
                        "out",
                        "Animal_OfSpecies",
                    ),
                    ("in", "out_Animal_FedAt"),
                ),
                None,
            ),
            FoldScopeLocation(
                Location(("Animal", "in_Animal_Parent_of")),
                (
                    (
                        "out",
                        "Animal_OfSpecies",
                    ),
                    ("in", "out_Animal_FedAt"),
                ),
                "name",
            ),
            FoldScopeLocation(
                Location(("Animal", "in_Animal_Parent_of")),
                (
                    (
                        "out",
                        "Animal_OfSpecies",
                    ),
                    ("in", "out_Animal_FedAt"),
                ),
                "uuid",
            ),
        ]
        for i, first_location in enumerate(sorted_locations):
            for j, second_location in enumerate(sorted_locations):
                expected_comparison = i < j
                received_comparison = first_location < second_location
                self.assertEqual(expected_comparison, received_comparison)

    def test_mixed_location_comparisons(self) -> None:
        sorted_locations = [
            FoldScopeLocation(
                Location(("Animal", "in_Animal_Parent_of")),
                (
                    (
                        "in",
                        "Animal_OfSpecies",
                    ),
                ),
                None,
            ),
            Location(("Animal", "in_Animal_Parent_of"), "name"),
            FoldScopeLocation(
                Location(("Animal", "out_Animal_Parent_of")),
                (
                    (
                        "in",
                        "Animal_OfSpecies",
                    ),
                ),
                None,
            ),
        ]

        compare_sorted_locations_list(self, sorted_locations)
