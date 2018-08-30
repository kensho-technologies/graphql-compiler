# Copyright 2017-present Kensho Technologies, LLC.
import unittest

from ..compiler.helpers import FoldScopeLocation, Location


def compare_sorted_locations_list(test_case, sorted_locations):
    """Ensure that the given list of locations is in ascending order."""
    for i in range(len(sorted_locations)):
        first_location = sorted_locations[i]
        for j in range(len(sorted_locations)):
            second_location = sorted_locations[j]
            expected_comparison = i < j
            received_comparison = first_location < second_location
            test_case.assertEqual(expected_comparison, received_comparison)


class LocationTests(unittest.TestCase):
    def test_location_name(self):
        base_location = Location(('Animal',))
        self.assertEqual((u'Animal___1', None), base_location.get_location_name())

        base_at_field = base_location.navigate_to_field(u'name')
        self.assertEqual((u'Animal___1', u'name'), base_at_field.get_location_name())

        revisited_location = base_location.revisit()
        self.assertEqual((u'Animal___2', None), revisited_location.get_location_name())

        revisited_at_field = revisited_location.navigate_to_field(u'name')
        self.assertEqual((u'Animal___2', u'name'), revisited_at_field.get_location_name())

        child_location = base_location.navigate_to_subpath(u'out_Animal_ParentOf')
        self.assertEqual(
            (u'Animal__out_Animal_ParentOf___1', None),
            child_location.get_location_name())

        child_at_field = child_location.navigate_to_field(u'name')
        self.assertEqual(
            (u'Animal__out_Animal_ParentOf___1', u'name'),
            child_at_field.get_location_name())

    def test_location_comparisons(self):
        sorted_locations = [
            Location(('Animal', 'in_Animal_Parent_of'), 'uuid', 3),
            Location(('Animal', 'in_Animal_Parent_of', 'in_Animal_FedAt'), 'name', 2),
            Location(('Animal', 'in_Animal_Parent_of', 'out_Animal_FedAt'), 'name', 1),
            Location(('Animal', 'in_Animal_Parent_of', 'out_Animal_FedAt'), None, 2),
            Location(('Animal', 'in_Animal_Parent_of', 'out_Animal_FedAt'), 'name', 2),
            Location(('Animal', 'in_Animal_Parent_of', 'out_Animal_FedAt'), 'uuid', 2),
        ]
        for i in range(len(sorted_locations)):
            first_location = sorted_locations[i]
            for j in range(len(sorted_locations)):
                second_location = sorted_locations[j]
                expected_comparison = i < j
                received_location_comparison = first_location < second_location
                self.assertEqual(expected_comparison, received_location_comparison)

    def test_fold_scope_location_comparisons(self):
        sorted_locations = [
            FoldScopeLocation(
                Location(('Animal', 'in_Animal_Parent_of')),
                (('in', 'Animal_OfSpecies',),), None),
            FoldScopeLocation(
                Location(('Animal', 'in_Animal_Parent_of')),
                (('out', 'Animal_OfSpecies',),), None),
            FoldScopeLocation(
                Location(('Animal', 'in_Animal_Parent_of')),
                (('out', 'Animal_OfSpecies',), ('in', 'out_Animal_FedAt'),), None),
            FoldScopeLocation(
                Location(('Animal', 'in_Animal_Parent_of')),
                (('out', 'Animal_OfSpecies',), ('in', 'out_Animal_FedAt'),), 'name'),
            FoldScopeLocation(
                Location(('Animal', 'in_Animal_Parent_of')),
                (('out', 'Animal_OfSpecies',), ('in', 'out_Animal_FedAt'),), 'uuid'),
        ]
        for i in range(len(sorted_locations)):
            first_location = sorted_locations[i]
            for j in range(len(sorted_locations)):
                second_location = sorted_locations[j]
                expected_comparison = i < j
                received_comparison = first_location < second_location
                self.assertEqual(expected_comparison, received_comparison)

    def test_mixed_location_comparisons(self):
        sorted_locations = [
            FoldScopeLocation(
                Location(('Animal', 'in_Animal_Parent_of')),
                (('in', 'Animal_OfSpecies',),), None),
            Location(('Animal', 'in_Animal_Parent_of'), 'name'),
            FoldScopeLocation(
                Location(('Animal', 'out_Animal_Parent_of')),
                (('in', 'Animal_OfSpecies',),), None),
        ]

        compare_sorted_locations_list(self, sorted_locations)
