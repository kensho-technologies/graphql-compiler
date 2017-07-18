# Copyright 2017 Kensho Technologies, Inc.
import unittest

from ..compiler.helpers import Location


class LocationTests(unittest.TestCase):
    def test_location_name(self):
        base_location = Location(('Animal',))
        self.assertEquals((u'Animal___1', None), base_location.get_location_name())

        base_at_field = base_location.navigate_to_field(u'name')
        self.assertEquals((u'Animal___1', u'name'), base_at_field.get_location_name())

        revisited_location = base_location.revisit()
        self.assertEquals((u'Animal___2', None), revisited_location.get_location_name())

        revisited_at_field = revisited_location.navigate_to_field(u'name')
        self.assertEquals((u'Animal___2', u'name'), revisited_at_field.get_location_name())

        child_location = base_location.navigate_to_subpath(u'out_Animal_ParentOf')
        self.assertEquals(
            (u'Animal__out_Animal_ParentOf___1', None),
            child_location.get_location_name())

        child_at_field = child_location.navigate_to_field(u'name')
        self.assertEquals(
            (u'Animal__out_Animal_ParentOf___1', u'name'),
            child_at_field.get_location_name())
