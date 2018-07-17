# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['OrientDBMatchQueryTests::test_filter_in_optional_block 1'] = frozenset([(frozenset([(u'animal_name', u'Pteranodon__4')]), 1), (frozenset([(u'animal_name', u'Nazgul__3')]), 1), (frozenset([(u'parent_name', u'Nazgul__2'), (u'animal_name', u'Nazgul__(234)'), (u'uuid', u'8b0163c1-cd9d-2b7d-247a-8333f7b0b7d2')]), 1), (frozenset([(u'animal_name', u'Nazgul__1')]), 1), (frozenset([(u'parent_name', u'Nazgul__2'), (u'uuid', u'8b0163c1-cd9d-2b7d-247a-8333f7b0b7d2'), (u'animal_name', u'Nazgul__((013)24)')]), 1), (frozenset([(u'animal_name', u'Dragon__2')]), 1), (frozenset([(u'animal_name', u'Nazgul__0')]), 1), (frozenset([(u'animal_name', u'Hippogriff__4')]), 1), (frozenset([(u'animal_name', u'Dragon__3')]), 1), (frozenset([(u'parent_name', u'Nazgul__2'), (u'animal_name', u'Nazgul__(024)'), (u'uuid', u'8b0163c1-cd9d-2b7d-247a-8333f7b0b7d2')]), 1), (frozenset([(u'animal_name', u'Hippogriff__2')]), 1), (frozenset([(u'animal_name', u'Dragon__1')]), 1), (frozenset([(u'animal_name', u'Dragon__0')]), 1), (frozenset([(u'animal_name', u'Nazgul__4')]), 1), (frozenset([(u'animal_name', u'Pteranodon__0')]), 1), (frozenset([(u'animal_name', u'Pteranodon__1')]), 1), (frozenset([(u'parent_name', u'Nazgul__2'), (u'animal_name', u'Nazgul__((((234)34)01)24)'), (u'uuid', u'8b0163c1-cd9d-2b7d-247a-8333f7b0b7d2')]), 1), (frozenset([(u'animal_name', u'Hippogriff__0')]), 1), (frozenset([(u'animal_name', u'Dragon__4')]), 1), (frozenset([(u'animal_name', u'Pteranodon__3')]), 1), (frozenset([(u'animal_name', u'Hippogriff__1')]), 1), (frozenset([(u'animal_name', u'Hippogriff__3')]), 1), (frozenset([(u'animal_name', u'Pteranodon__2')]), 1), (frozenset([(u'animal_name', u'Nazgul__2')]), 1)])

snapshots['OrientDBMatchQueryTests::test_traverse_filter_and_output 1'] = frozenset([(frozenset([(u'parent_name', u'Nazgul__2')]), 4)])
