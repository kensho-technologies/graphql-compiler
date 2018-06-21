# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
# flake8: noqa
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['OrientdbMatchQueryTests::test_filter_in_optional_block 1'] = [
    {
        'animal_name': 'Pteranodon__(3(10(13(102)))(341))'
    },
    {
        'animal_name': 'Dragon__(204)'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'parent_name': 'Nazgul__2',
        'uuid': 'd71037d1-b83e-90ec-17e0-aa3c03983ca8'
    },
    {
        'animal_name': 'Dragon__2'
    },
    {
        'animal_name': 'Hippogriff__0'
    },
    {
        'animal_name': 'Nazgul__1'
    },
    {
        'animal_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))'
    },
    {
        'animal_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))'
    },
    {
        'animal_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)'
    },
    {
        'animal_name': 'Pteranodon__(3(341)(102))'
    },
    {
        'animal_name': 'Hippogriff__(423)'
    },
    {
        'animal_name': 'Pteranodon__4'
    },
    {
        'animal_name': 'Hippogriff__((2(40(423))3)10)'
    },
    {
        'animal_name': 'Pteranodon__((10(13(102)))42)'
    },
    {
        'animal_name': 'Pteranodon__(1(341)2)'
    },
    {
        'animal_name': 'Dragon__(20(204))'
    },
    {
        'animal_name': 'Nazgul__(241)',
        'parent_name': 'Nazgul__2',
        'uuid': 'd71037d1-b83e-90ec-17e0-aa3c03983ca8'
    },
    {
        'animal_name': 'Dragon__3'
    },
    {
        'animal_name': 'Hippogriff__1'
    },
    {
        'animal_name': 'Nazgul__2'
    },
    {
        'animal_name': 'Pteranodon__0'
    },
    {
        'animal_name': 'Dragon__(10(204))'
    },
    {
        'animal_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))'
    },
    {
        'animal_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))'
    },
    {
        'animal_name': 'Hippogriff__(40(423))'
    },
    {
        'animal_name': 'Pteranodon__(102)'
    },
    {
        'animal_name': 'Pteranodon__1'
    },
    {
        'animal_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)'
    },
    {
        'animal_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))'
    },
    {
        'animal_name': 'Pteranodon__((1(341)2)4(102))'
    },
    {
        'animal_name': 'Dragon__((204)14)'
    },
    {
        'animal_name': 'Nazgul__((241)(320)1)'
    },
    {
        'animal_name': 'Dragon__4'
    },
    {
        'animal_name': 'Hippogriff__2'
    },
    {
        'animal_name': 'Nazgul__3'
    },
    {
        'animal_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))'
    },
    {
        'animal_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)'
    },
    {
        'animal_name': 'Nazgul__(((241)(320)1)(241)0)'
    },
    {
        'animal_name': 'Pteranodon__(13(102))'
    },
    {
        'animal_name': 'Hippogriff__3'
    },
    {
        'animal_name': 'Pteranodon__2'
    },
    {
        'animal_name': 'Dragon__0'
    },
    {
        'animal_name': 'Hippogriff__((2(40(423))3)(40(423))0)'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))'
    },
    {
        'animal_name': 'Dragon__(314)'
    },
    {
        'animal_name': 'Nazgul__4'
    },
    {
        'animal_name': 'Dragon__(2((20(204))2((204)14))4)'
    },
    {
        'animal_name': 'Nazgul__0'
    },
    {
        'animal_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'parent_name': 'Nazgul__2',
        'uuid': 'd71037d1-b83e-90ec-17e0-aa3c03983ca8'
    },
    {
        'animal_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))'
    },
    {
        'animal_name': 'Hippogriff__((423)41)'
    },
    {
        'animal_name': 'Nazgul__(1(320)0)'
    },
    {
        'animal_name': 'Pteranodon__(341)'
    },
    {
        'animal_name': 'Hippogriff__4'
    },
    {
        'animal_name': 'Pteranodon__3'
    },
    {
        'animal_name': 'Dragon__1'
    },
    {
        'animal_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))'
    }
]

snapshots['OrientdbMatchQueryTests::test_immediate_output 1'] = [
    {
        'animal_name': 'Pteranodon__(3(10(13(102)))(341))'
    },
    {
        'animal_name': 'Dragon__(204)'
    },
    {
        'animal_name': 'Nazgul__(320)'
    },
    {
        'animal_name': 'Dragon__2'
    },
    {
        'animal_name': 'Hippogriff__0'
    },
    {
        'animal_name': 'Nazgul__1'
    },
    {
        'animal_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))'
    },
    {
        'animal_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))'
    },
    {
        'animal_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)'
    },
    {
        'animal_name': 'Pteranodon__(3(341)(102))'
    },
    {
        'animal_name': 'Hippogriff__(423)'
    },
    {
        'animal_name': 'Pteranodon__4'
    },
    {
        'animal_name': 'Hippogriff__((2(40(423))3)10)'
    },
    {
        'animal_name': 'Pteranodon__((10(13(102)))42)'
    },
    {
        'animal_name': 'Pteranodon__(1(341)2)'
    },
    {
        'animal_name': 'Dragon__(20(204))'
    },
    {
        'animal_name': 'Nazgul__(241)'
    },
    {
        'animal_name': 'Dragon__3'
    },
    {
        'animal_name': 'Hippogriff__1'
    },
    {
        'animal_name': 'Nazgul__2'
    },
    {
        'animal_name': 'Pteranodon__0'
    },
    {
        'animal_name': 'Dragon__(10(204))'
    },
    {
        'animal_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))'
    },
    {
        'animal_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))'
    },
    {
        'animal_name': 'Hippogriff__(40(423))'
    },
    {
        'animal_name': 'Pteranodon__(102)'
    },
    {
        'animal_name': 'Pteranodon__1'
    },
    {
        'animal_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)'
    },
    {
        'animal_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))'
    },
    {
        'animal_name': 'Pteranodon__((1(341)2)4(102))'
    },
    {
        'animal_name': 'Dragon__((204)14)'
    },
    {
        'animal_name': 'Nazgul__((241)(320)1)'
    },
    {
        'animal_name': 'Dragon__4'
    },
    {
        'animal_name': 'Hippogriff__2'
    },
    {
        'animal_name': 'Nazgul__3'
    },
    {
        'animal_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))'
    },
    {
        'animal_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)'
    },
    {
        'animal_name': 'Nazgul__(((241)(320)1)(241)0)'
    },
    {
        'animal_name': 'Pteranodon__(13(102))'
    },
    {
        'animal_name': 'Hippogriff__3'
    },
    {
        'animal_name': 'Pteranodon__2'
    },
    {
        'animal_name': 'Dragon__0'
    },
    {
        'animal_name': 'Hippogriff__((2(40(423))3)(40(423))0)'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))'
    },
    {
        'animal_name': 'Dragon__(314)'
    },
    {
        'animal_name': 'Nazgul__4'
    },
    {
        'animal_name': 'Dragon__(2((20(204))2((204)14))4)'
    },
    {
        'animal_name': 'Nazgul__0'
    },
    {
        'animal_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))'
    },
    {
        'animal_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))'
    },
    {
        'animal_name': 'Hippogriff__((423)41)'
    },
    {
        'animal_name': 'Nazgul__(1(320)0)'
    },
    {
        'animal_name': 'Pteranodon__(341)'
    },
    {
        'animal_name': 'Hippogriff__4'
    },
    {
        'animal_name': 'Pteranodon__3'
    },
    {
        'animal_name': 'Dragon__1'
    },
    {
        'animal_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))'
    }
]

snapshots['OrientdbMatchQueryTests::test_optional_and_deep_traverse 1'] = [
    {
        'animal_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))'
    },
    {
        'animal_name': 'Pteranodon__(3(10(13(102)))(341))'
    },
    {
        'animal_name': 'Pteranodon__((1(341)2)4(102))'
    },
    {
        'animal_name': 'Dragon__(314)'
    },
    {
        'animal_name': 'Dragon__(2((20(204))2((204)14))4)'
    },
    {
        'animal_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))'
    },
    {
        'animal_name': 'Dragon__(10(204))'
    },
    {
        'animal_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))'
    },
    {
        'animal_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))'
    },
    {
        'animal_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))'
    },
    {
        'animal_name': 'Pteranodon__(3(341)(102))'
    },
    {
        'animal_name': 'Hippogriff__((2(40(423))3)10)'
    },
    {
        'animal_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))'
    },
    {
        'animal_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)'
    },
    {
        'animal_name': 'Dragon__(204)',
        'child_name': 'Dragon__(20(204))',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(204)',
        'child_name': 'Dragon__(20(204))',
        'spouse_and_self_name': 'Dragon__0',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(204)',
        'child_name': 'Dragon__(20(204))',
        'spouse_and_self_name': 'Dragon__(204)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(204)',
        'child_name': 'Dragon__((204)14)',
        'spouse_and_self_name': 'Dragon__(204)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(204)',
        'child_name': 'Dragon__((204)14)',
        'spouse_and_self_name': 'Dragon__1',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(204)',
        'child_name': 'Dragon__((204)14)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(204)',
        'child_name': 'Dragon__(10(204))',
        'spouse_and_self_name': 'Dragon__1',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(204)',
        'child_name': 'Dragon__(10(204))',
        'spouse_and_self_name': 'Dragon__0',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(204)',
        'child_name': 'Dragon__(10(204))',
        'spouse_and_self_name': 'Dragon__(204)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__((241)(320)1)',
        'spouse_and_self_name': 'Nazgul__(241)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__((241)(320)1)',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__((241)(320)1)',
        'spouse_and_self_name': 'Nazgul__1',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__(1(320)0)',
        'spouse_and_self_name': 'Nazgul__1',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__(1(320)0)',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__(1(320)0)',
        'spouse_and_self_name': 'Nazgul__0',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__((241)(320)1)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(1(320)0)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_and_self_name': 'Nazgul__2',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(320)',
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_and_self_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(204)',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(204)',
        'spouse_and_self_name': 'Dragon__0',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(204)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(20(204))',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(20(204))',
        'spouse_and_self_name': 'Dragon__0',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(20(204))',
        'spouse_and_self_name': 'Dragon__(204)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__((20(204))2((204)14))',
        'spouse_and_self_name': 'Dragon__(20(204))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__((20(204))2((204)14))',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__((20(204))2((204)14))',
        'spouse_and_self_name': 'Dragon__((204)14)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))',
        'spouse_and_self_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(2((20(204))2((204)14))4)',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(2((20(204))2((204)14))4)',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__2',
        'child_name': 'Dragon__(2((20(204))2((204)14))4)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Hippogriff__0',
        'child_name': 'Hippogriff__(40(423))',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__0',
        'child_name': 'Hippogriff__(40(423))',
        'spouse_and_self_name': 'Hippogriff__0',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__0',
        'child_name': 'Hippogriff__(40(423))',
        'spouse_and_self_name': 'Hippogriff__(423)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__0',
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_and_self_name': 'Hippogriff__(2(40(423))3)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__0',
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__0',
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_and_self_name': 'Hippogriff__0',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__0',
        'child_name': 'Hippogriff__((2(40(423))3)10)',
        'spouse_and_self_name': 'Hippogriff__(2(40(423))3)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__0',
        'child_name': 'Hippogriff__((2(40(423))3)10)',
        'spouse_and_self_name': 'Hippogriff__1',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__0',
        'child_name': 'Hippogriff__((2(40(423))3)10)',
        'spouse_and_self_name': 'Hippogriff__0',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Nazgul__1',
        'child_name': 'Nazgul__(241)',
        'spouse_and_self_name': 'Nazgul__2',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__1',
        'child_name': 'Nazgul__(241)',
        'spouse_and_self_name': 'Nazgul__4',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__1',
        'child_name': 'Nazgul__(241)',
        'spouse_and_self_name': 'Nazgul__1',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__1',
        'child_name': 'Nazgul__((241)(320)1)',
        'spouse_and_self_name': 'Nazgul__(241)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__1',
        'child_name': 'Nazgul__((241)(320)1)',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__1',
        'child_name': 'Nazgul__((241)(320)1)',
        'spouse_and_self_name': 'Nazgul__1',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__1',
        'child_name': 'Nazgul__(1(320)0)',
        'spouse_and_self_name': 'Nazgul__1',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__1',
        'child_name': 'Nazgul__(1(320)0)',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__1',
        'child_name': 'Nazgul__(1(320)0)',
        'spouse_and_self_name': 'Nazgul__0',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'child_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__((241)(320)1)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'child_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'child_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(1(320)0)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'child_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))',
        'spouse_and_self_name': 'Nazgul__(1(320)0)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'child_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))',
        'spouse_and_self_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'child_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))',
        'spouse_and_self_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Hippogriff__(423)',
        'child_name': 'Hippogriff__(40(423))',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(423)',
        'child_name': 'Hippogriff__(40(423))',
        'spouse_and_self_name': 'Hippogriff__0',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(423)',
        'child_name': 'Hippogriff__(40(423))',
        'spouse_and_self_name': 'Hippogriff__(423)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(423)',
        'child_name': 'Hippogriff__((423)41)',
        'spouse_and_self_name': 'Hippogriff__(423)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(423)',
        'child_name': 'Hippogriff__((423)41)',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(423)',
        'child_name': 'Hippogriff__((423)41)',
        'spouse_and_self_name': 'Hippogriff__1',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(423)',
        'child_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(423)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(423)',
        'child_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))',
        'spouse_and_self_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(423)',
        'child_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Pteranodon__4',
        'child_name': 'Pteranodon__(341)',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__4',
        'child_name': 'Pteranodon__(341)',
        'spouse_and_self_name': 'Pteranodon__4',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__4',
        'child_name': 'Pteranodon__(341)',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__4',
        'child_name': 'Pteranodon__((1(341)2)4(102))',
        'spouse_and_self_name': 'Pteranodon__(1(341)2)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__4',
        'child_name': 'Pteranodon__((1(341)2)4(102))',
        'spouse_and_self_name': 'Pteranodon__4',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__4',
        'child_name': 'Pteranodon__((1(341)2)4(102))',
        'spouse_and_self_name': 'Pteranodon__(102)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__4',
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_and_self_name': 'Pteranodon__(10(13(102)))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__4',
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_and_self_name': 'Pteranodon__4',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__4',
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__((10(13(102)))42)',
        'child_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)',
        'spouse_and_self_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__((10(13(102)))42)',
        'child_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)',
        'spouse_and_self_name': 'Pteranodon__(10(13(102)))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__((10(13(102)))42)',
        'child_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(1(341)2)',
        'child_name': 'Pteranodon__((1(341)2)4(102))',
        'spouse_and_self_name': 'Pteranodon__(1(341)2)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(1(341)2)',
        'child_name': 'Pteranodon__((1(341)2)4(102))',
        'spouse_and_self_name': 'Pteranodon__4',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(1(341)2)',
        'child_name': 'Pteranodon__((1(341)2)4(102))',
        'spouse_and_self_name': 'Pteranodon__(102)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Dragon__(20(204))',
        'child_name': 'Dragon__((20(204))2((204)14))',
        'spouse_and_self_name': 'Dragon__(20(204))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(20(204))',
        'child_name': 'Dragon__((20(204))2((204)14))',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(20(204))',
        'child_name': 'Dragon__((20(204))2((204)14))',
        'spouse_and_self_name': 'Dragon__((204)14)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(20(204))',
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_and_self_name': 'Dragon__(20(204))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(20(204))',
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(20(204))',
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_and_self_name': 'Dragon__((204)14)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(20(204))',
        'child_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(20(204))',
        'child_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))',
        'spouse_and_self_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__(20(204))',
        'child_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))',
        'spouse_and_self_name': 'Dragon__(20(204))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Nazgul__(241)',
        'child_name': 'Nazgul__((241)(320)1)',
        'spouse_and_self_name': 'Nazgul__(241)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(241)',
        'child_name': 'Nazgul__((241)(320)1)',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(241)',
        'child_name': 'Nazgul__((241)(320)1)',
        'spouse_and_self_name': 'Nazgul__1',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(241)',
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_and_self_name': 'Nazgul__((241)(320)1)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(241)',
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_and_self_name': 'Nazgul__(241)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(241)',
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_and_self_name': 'Nazgul__0',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Dragon__3',
        'child_name': 'Dragon__(314)',
        'spouse_and_self_name': 'Dragon__3',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__3',
        'child_name': 'Dragon__(314)',
        'spouse_and_self_name': 'Dragon__1',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__3',
        'child_name': 'Dragon__(314)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Hippogriff__1',
        'child_name': 'Hippogriff__((423)41)',
        'spouse_and_self_name': 'Hippogriff__(423)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__1',
        'child_name': 'Hippogriff__((423)41)',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__1',
        'child_name': 'Hippogriff__((423)41)',
        'spouse_and_self_name': 'Hippogriff__1',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__1',
        'child_name': 'Hippogriff__((2(40(423))3)10)',
        'spouse_and_self_name': 'Hippogriff__(2(40(423))3)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__1',
        'child_name': 'Hippogriff__((2(40(423))3)10)',
        'spouse_and_self_name': 'Hippogriff__1',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__1',
        'child_name': 'Hippogriff__((2(40(423))3)10)',
        'spouse_and_self_name': 'Hippogriff__0',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Nazgul__2',
        'child_name': 'Nazgul__(320)',
        'spouse_and_self_name': 'Nazgul__3',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__2',
        'child_name': 'Nazgul__(320)',
        'spouse_and_self_name': 'Nazgul__2',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__2',
        'child_name': 'Nazgul__(320)',
        'spouse_and_self_name': 'Nazgul__0',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__2',
        'child_name': 'Nazgul__(241)',
        'spouse_and_self_name': 'Nazgul__2',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__2',
        'child_name': 'Nazgul__(241)',
        'spouse_and_self_name': 'Nazgul__4',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__2',
        'child_name': 'Nazgul__(241)',
        'spouse_and_self_name': 'Nazgul__1',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__2',
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_and_self_name': 'Nazgul__2',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__2',
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__2',
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_and_self_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Pteranodon__0',
        'child_name': 'Pteranodon__(102)',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__0',
        'child_name': 'Pteranodon__(102)',
        'spouse_and_self_name': 'Pteranodon__0',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__0',
        'child_name': 'Pteranodon__(102)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__0',
        'child_name': 'Pteranodon__(10(13(102)))',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__0',
        'child_name': 'Pteranodon__(10(13(102)))',
        'spouse_and_self_name': 'Pteranodon__0',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__0',
        'child_name': 'Pteranodon__(10(13(102)))',
        'spouse_and_self_name': 'Pteranodon__(13(102))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'child_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))',
        'spouse_and_self_name': 'Hippogriff__2',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'child_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))',
        'spouse_and_self_name': 'Hippogriff__3',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'child_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))',
        'spouse_and_self_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__(2(40(423))3)',
        'spouse_and_self_name': 'Hippogriff__2',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__(2(40(423))3)',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__(2(40(423))3)',
        'spouse_and_self_name': 'Hippogriff__3',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_and_self_name': 'Hippogriff__((423)41)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_and_self_name': 'Hippogriff__(2(40(423))3)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_and_self_name': 'Hippogriff__(2(40(423))3)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_and_self_name': 'Hippogriff__0',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(423)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))',
        'spouse_and_self_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(40(423))',
        'child_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Pteranodon__(102)',
        'child_name': 'Pteranodon__(13(102))',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(102)',
        'child_name': 'Pteranodon__(13(102))',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(102)',
        'child_name': 'Pteranodon__(13(102))',
        'spouse_and_self_name': 'Pteranodon__(102)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(102)',
        'child_name': 'Pteranodon__(3(341)(102))',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(102)',
        'child_name': 'Pteranodon__(3(341)(102))',
        'spouse_and_self_name': 'Pteranodon__(341)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(102)',
        'child_name': 'Pteranodon__(3(341)(102))',
        'spouse_and_self_name': 'Pteranodon__(102)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(102)',
        'child_name': 'Pteranodon__((1(341)2)4(102))',
        'spouse_and_self_name': 'Pteranodon__(1(341)2)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(102)',
        'child_name': 'Pteranodon__((1(341)2)4(102))',
        'spouse_and_self_name': 'Pteranodon__4',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(102)',
        'child_name': 'Pteranodon__((1(341)2)4(102))',
        'spouse_and_self_name': 'Pteranodon__(102)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(102)',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(102)',
        'spouse_and_self_name': 'Pteranodon__0',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(102)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(13(102))',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(13(102))',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(13(102))',
        'spouse_and_self_name': 'Pteranodon__(102)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(341)',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(341)',
        'spouse_and_self_name': 'Pteranodon__4',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(341)',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(1(341)2)',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(1(341)2)',
        'spouse_and_self_name': 'Pteranodon__(341)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(1(341)2)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(10(13(102)))',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(10(13(102)))',
        'spouse_and_self_name': 'Pteranodon__0',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__1',
        'child_name': 'Pteranodon__(10(13(102)))',
        'spouse_and_self_name': 'Pteranodon__(13(102))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Dragon__((204)14)',
        'child_name': 'Dragon__((20(204))2((204)14))',
        'spouse_and_self_name': 'Dragon__(20(204))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((204)14)',
        'child_name': 'Dragon__((20(204))2((204)14))',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((204)14)',
        'child_name': 'Dragon__((20(204))2((204)14))',
        'spouse_and_self_name': 'Dragon__((204)14)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((204)14)',
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_and_self_name': 'Dragon__(20(204))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((204)14)',
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((204)14)',
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_and_self_name': 'Dragon__((204)14)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Nazgul__((241)(320)1)',
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_and_self_name': 'Nazgul__((241)(320)1)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__((241)(320)1)',
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_and_self_name': 'Nazgul__(241)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__((241)(320)1)',
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_and_self_name': 'Nazgul__0',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__((241)(320)1)',
        'child_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__((241)(320)1)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__((241)(320)1)',
        'child_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__((241)(320)1)',
        'child_name': 'Nazgul__(((241)(320)1)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__(314)',
        'spouse_and_self_name': 'Dragon__3',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__(314)',
        'spouse_and_self_name': 'Dragon__1',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__(314)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__(204)',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__(204)',
        'spouse_and_self_name': 'Dragon__0',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__(204)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__((204)14)',
        'spouse_and_self_name': 'Dragon__(204)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__((204)14)',
        'spouse_and_self_name': 'Dragon__1',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__((204)14)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__(2((20(204))2((204)14))4)',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__(2((20(204))2((204)14))4)',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__4',
        'child_name': 'Dragon__(2((20(204))2((204)14))4)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Hippogriff__2',
        'child_name': 'Hippogriff__(423)',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__2',
        'child_name': 'Hippogriff__(423)',
        'spouse_and_self_name': 'Hippogriff__2',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__2',
        'child_name': 'Hippogriff__(423)',
        'spouse_and_self_name': 'Hippogriff__3',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__2',
        'child_name': 'Hippogriff__(2(40(423))3)',
        'spouse_and_self_name': 'Hippogriff__2',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__2',
        'child_name': 'Hippogriff__(2(40(423))3)',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__2',
        'child_name': 'Hippogriff__(2(40(423))3)',
        'spouse_and_self_name': 'Hippogriff__3',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__2',
        'child_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))',
        'spouse_and_self_name': 'Hippogriff__2',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__2',
        'child_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))',
        'spouse_and_self_name': 'Hippogriff__3',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__2',
        'child_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))',
        'spouse_and_self_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Nazgul__3',
        'child_name': 'Nazgul__(320)',
        'spouse_and_self_name': 'Nazgul__3',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__3',
        'child_name': 'Nazgul__(320)',
        'spouse_and_self_name': 'Nazgul__2',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__3',
        'child_name': 'Nazgul__(320)',
        'spouse_and_self_name': 'Nazgul__0',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__3',
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_and_self_name': 'Nazgul__3',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__3',
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_and_self_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__3',
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_and_self_name': 'Nazgul__4',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_and_self_name': 'Nazgul__2',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_and_self_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)',
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_and_self_name': 'Hippogriff__((423)41)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)',
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)',
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_and_self_name': 'Hippogriff__(2(40(423))3)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)',
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_and_self_name': 'Hippogriff__(2(40(423))3)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)',
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)',
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_and_self_name': 'Hippogriff__0',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)',
        'child_name': 'Hippogriff__((2(40(423))3)10)',
        'spouse_and_self_name': 'Hippogriff__(2(40(423))3)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)',
        'child_name': 'Hippogriff__((2(40(423))3)10)',
        'spouse_and_self_name': 'Hippogriff__1',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__(2(40(423))3)',
        'child_name': 'Hippogriff__((2(40(423))3)10)',
        'spouse_and_self_name': 'Hippogriff__0',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Nazgul__(((241)(320)1)(241)0)',
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_and_self_name': 'Nazgul__3',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(((241)(320)1)(241)0)',
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_and_self_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(((241)(320)1)(241)0)',
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_and_self_name': 'Nazgul__4',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Pteranodon__(13(102))',
        'child_name': 'Pteranodon__(10(13(102)))',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(13(102))',
        'child_name': 'Pteranodon__(10(13(102)))',
        'spouse_and_self_name': 'Pteranodon__0',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(13(102))',
        'child_name': 'Pteranodon__(10(13(102)))',
        'spouse_and_self_name': 'Pteranodon__(13(102))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Hippogriff__3',
        'child_name': 'Hippogriff__(423)',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__3',
        'child_name': 'Hippogriff__(423)',
        'spouse_and_self_name': 'Hippogriff__2',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__3',
        'child_name': 'Hippogriff__(423)',
        'spouse_and_self_name': 'Hippogriff__3',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__3',
        'child_name': 'Hippogriff__(2(40(423))3)',
        'spouse_and_self_name': 'Hippogriff__2',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__3',
        'child_name': 'Hippogriff__(2(40(423))3)',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__3',
        'child_name': 'Hippogriff__(2(40(423))3)',
        'spouse_and_self_name': 'Hippogriff__3',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__3',
        'child_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))',
        'spouse_and_self_name': 'Hippogriff__2',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__3',
        'child_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))',
        'spouse_and_self_name': 'Hippogriff__3',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__3',
        'child_name': 'Hippogriff__(23(4(((423)41)(40(423))(2(40(423))3))(40(423))))',
        'spouse_and_self_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__(102)',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__(102)',
        'spouse_and_self_name': 'Pteranodon__0',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__(102)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__(1(341)2)',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__(1(341)2)',
        'spouse_and_self_name': 'Pteranodon__(341)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__(1(341)2)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_and_self_name': 'Pteranodon__(10(13(102)))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_and_self_name': 'Pteranodon__4',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)',
        'spouse_and_self_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)',
        'spouse_and_self_name': 'Pteranodon__(10(13(102)))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__2',
        'child_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Dragon__0',
        'child_name': 'Dragon__(204)',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__0',
        'child_name': 'Dragon__(204)',
        'spouse_and_self_name': 'Dragon__0',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__0',
        'child_name': 'Dragon__(204)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__0',
        'child_name': 'Dragon__(20(204))',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__0',
        'child_name': 'Dragon__(20(204))',
        'spouse_and_self_name': 'Dragon__0',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__0',
        'child_name': 'Dragon__(20(204))',
        'spouse_and_self_name': 'Dragon__(204)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__0',
        'child_name': 'Dragon__(10(204))',
        'spouse_and_self_name': 'Dragon__1',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__0',
        'child_name': 'Dragon__(10(204))',
        'spouse_and_self_name': 'Dragon__0',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__0',
        'child_name': 'Dragon__(10(204))',
        'spouse_and_self_name': 'Dragon__(204)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'child_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(423)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'child_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))',
        'spouse_and_self_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'child_name': 'Hippogriff__((423)((2(40(423))3)(40(423))0)(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))',
        'child_name': 'Pteranodon__(3(10(13(102)))(341))',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))',
        'child_name': 'Pteranodon__(3(10(13(102)))(341))',
        'spouse_and_self_name': 'Pteranodon__(10(13(102)))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))',
        'child_name': 'Pteranodon__(3(10(13(102)))(341))',
        'spouse_and_self_name': 'Pteranodon__(341)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))',
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_and_self_name': 'Pteranodon__(10(13(102)))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))',
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_and_self_name': 'Pteranodon__4',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))',
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))',
        'child_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)',
        'spouse_and_self_name': 'Pteranodon__((10(13(102)))42)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))',
        'child_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)',
        'spouse_and_self_name': 'Pteranodon__(10(13(102)))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(10(13(102)))',
        'child_name': 'Pteranodon__(((10(13(102)))42)(10(13(102)))2)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_and_self_name': 'Dragon__(20(204))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_and_self_name': 'Dragon__((204)14)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))',
        'spouse_and_self_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))',
        'spouse_and_self_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))',
        'spouse_and_self_name': 'Dragon__(20(204))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__(2((20(204))2((204)14))4)',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__(2((20(204))2((204)14))4)',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))2((204)14))',
        'child_name': 'Dragon__(2((20(204))2((204)14))4)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Nazgul__4',
        'child_name': 'Nazgul__(241)',
        'spouse_and_self_name': 'Nazgul__2',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__4',
        'child_name': 'Nazgul__(241)',
        'spouse_and_self_name': 'Nazgul__4',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__4',
        'child_name': 'Nazgul__(241)',
        'spouse_and_self_name': 'Nazgul__1',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__4',
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_and_self_name': 'Nazgul__3',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__4',
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_and_self_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__4',
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_and_self_name': 'Nazgul__4',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__0',
        'child_name': 'Nazgul__(320)',
        'spouse_and_self_name': 'Nazgul__3',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__0',
        'child_name': 'Nazgul__(320)',
        'spouse_and_self_name': 'Nazgul__2',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__0',
        'child_name': 'Nazgul__(320)',
        'spouse_and_self_name': 'Nazgul__0',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__0',
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_and_self_name': 'Nazgul__((241)(320)1)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__0',
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_and_self_name': 'Nazgul__(241)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__0',
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'spouse_and_self_name': 'Nazgul__0',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__0',
        'child_name': 'Nazgul__(1(320)0)',
        'spouse_and_self_name': 'Nazgul__1',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__0',
        'child_name': 'Nazgul__(1(320)0)',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__0',
        'child_name': 'Nazgul__(1(320)0)',
        'spouse_and_self_name': 'Nazgul__0',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'child_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))',
        'spouse_and_self_name': 'Nazgul__(1(320)0)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'child_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))',
        'spouse_and_self_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'child_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))',
        'spouse_and_self_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))',
        'spouse_and_self_name': 'Dragon__2',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))2((20(204))((20(204))2((204)14))((204)14)))',
        'spouse_and_self_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))',
        'spouse_and_self_name': 'Dragon__((20(204))2((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))',
        'spouse_and_self_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'child_name': 'Dragon__(((20(204))2((204)14))((20(204))((20(204))2((204)14))((204)14))(20(204)))',
        'spouse_and_self_name': 'Dragon__(20(204))',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Hippogriff__((423)41)',
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_and_self_name': 'Hippogriff__((423)41)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__((423)41)',
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__((423)41)',
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_and_self_name': 'Hippogriff__(2(40(423))3)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Nazgul__(1(320)0)',
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(1(320)0)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(1(320)0)',
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(1(320)0)',
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'spouse_and_self_name': 'Nazgul__(320)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(1(320)0)',
        'child_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))',
        'spouse_and_self_name': 'Nazgul__(1(320)0)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(1(320)0)',
        'child_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))',
        'spouse_and_self_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Nazgul__(1(320)0)',
        'child_name': 'Nazgul__((1(320)0)(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))(3(((241)(320)1)(241)0)4))',
        'spouse_and_self_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'spouse_species': 'Nazgul'
    },
    {
        'animal_name': 'Pteranodon__(341)',
        'child_name': 'Pteranodon__(3(341)(102))',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(341)',
        'child_name': 'Pteranodon__(3(341)(102))',
        'spouse_and_self_name': 'Pteranodon__(341)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(341)',
        'child_name': 'Pteranodon__(3(341)(102))',
        'spouse_and_self_name': 'Pteranodon__(102)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(341)',
        'child_name': 'Pteranodon__(1(341)2)',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(341)',
        'child_name': 'Pteranodon__(1(341)2)',
        'spouse_and_self_name': 'Pteranodon__(341)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(341)',
        'child_name': 'Pteranodon__(1(341)2)',
        'spouse_and_self_name': 'Pteranodon__2',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(341)',
        'child_name': 'Pteranodon__(3(10(13(102)))(341))',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(341)',
        'child_name': 'Pteranodon__(3(10(13(102)))(341))',
        'spouse_and_self_name': 'Pteranodon__(10(13(102)))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__(341)',
        'child_name': 'Pteranodon__(3(10(13(102)))(341))',
        'spouse_and_self_name': 'Pteranodon__(341)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__(423)',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__(423)',
        'spouse_and_self_name': 'Hippogriff__2',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__(423)',
        'spouse_and_self_name': 'Hippogriff__3',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__(40(423))',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__(40(423))',
        'spouse_and_self_name': 'Hippogriff__0',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__(40(423))',
        'spouse_and_self_name': 'Hippogriff__(423)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__((423)41)',
        'spouse_and_self_name': 'Hippogriff__(423)',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__((423)41)',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__((423)41)',
        'spouse_and_self_name': 'Hippogriff__1',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_and_self_name': 'Hippogriff__4',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Hippogriff__4',
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'spouse_and_self_name': 'Hippogriff__(40(423))',
        'spouse_species': 'Hippogriff'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(13(102))',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(13(102))',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(13(102))',
        'spouse_and_self_name': 'Pteranodon__(102)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(341)',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(341)',
        'spouse_and_self_name': 'Pteranodon__4',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(341)',
        'spouse_and_self_name': 'Pteranodon__1',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(3(341)(102))',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(3(341)(102))',
        'spouse_and_self_name': 'Pteranodon__(341)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(3(341)(102))',
        'spouse_and_self_name': 'Pteranodon__(102)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(3(10(13(102)))(341))',
        'spouse_and_self_name': 'Pteranodon__3',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(3(10(13(102)))(341))',
        'spouse_and_self_name': 'Pteranodon__(10(13(102)))',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Pteranodon__3',
        'child_name': 'Pteranodon__(3(10(13(102)))(341))',
        'spouse_and_self_name': 'Pteranodon__(341)',
        'spouse_species': 'Pteranodon'
    },
    {
        'animal_name': 'Dragon__1',
        'child_name': 'Dragon__(314)',
        'spouse_and_self_name': 'Dragon__3',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__1',
        'child_name': 'Dragon__(314)',
        'spouse_and_self_name': 'Dragon__1',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__1',
        'child_name': 'Dragon__(314)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__1',
        'child_name': 'Dragon__((204)14)',
        'spouse_and_self_name': 'Dragon__(204)',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__1',
        'child_name': 'Dragon__((204)14)',
        'spouse_and_self_name': 'Dragon__1',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__1',
        'child_name': 'Dragon__((204)14)',
        'spouse_and_self_name': 'Dragon__4',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__1',
        'child_name': 'Dragon__(10(204))',
        'spouse_and_self_name': 'Dragon__1',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__1',
        'child_name': 'Dragon__(10(204))',
        'spouse_and_self_name': 'Dragon__0',
        'spouse_species': 'Dragon'
    },
    {
        'animal_name': 'Dragon__1',
        'child_name': 'Dragon__(10(204))',
        'spouse_and_self_name': 'Dragon__(204)',
        'spouse_species': 'Dragon'
    }
]

snapshots['OrientdbMatchQueryTests::test_optional_traverse_after_mandatory_traverse 1'] = [
    {
        'child_name': 'Pteranodon__3',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__(10(13(102)))',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__(341)',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Dragon__2',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__0',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__4',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Nazgul__3',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__2',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__0',
        'species_name': 'Nazgul'
    },
    {
        'species_name': 'Dragon'
    },
    {
        'species_name': 'Hippogriff'
    },
    {
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(1(320)0)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Dragon__((20(204))2((204)14))',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__2',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Hippogriff__((423)41)',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__(40(423))',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__(2(40(423))3)',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Nazgul__3',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(((241)(320)1)(241)0)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__4',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Pteranodon__3',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__(341)',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__(102)',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Hippogriff__4',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__2',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__3',
        'species_name': 'Hippogriff'
    },
    {
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Hippogriff__(2(40(423))3)',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__1',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__0',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Pteranodon__(10(13(102)))',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__4',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__2',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__1',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__(341)',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__2',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Dragon__2',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__0',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__(204)',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Nazgul__2',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__4',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__1',
        'species_name': 'Nazgul'
    },
    {
        'species_name': 'Dragon'
    },
    {
        'species_name': 'Hippogriff'
    },
    {
        'species_name': 'Nazgul'
    },
    {
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Dragon__1',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__0',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__(204)',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Hippogriff__4',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__(40(423))',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Nazgul__((241)(320)1)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(320)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Hippogriff__4',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__0',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__(423)',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Pteranodon__1',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__0',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__2',
        'species_name': 'Pteranodon'
    },
    {
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__((10(13(102)))42)',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__(10(13(102)))',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__2',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Hippogriff__2',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__3',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Pteranodon__(1(341)2)',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__4',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__(102)',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Dragon__(204)',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__1',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__4',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Nazgul__(241)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(320)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__1',
        'species_name': 'Nazgul'
    },
    {
        'species_name': 'Dragon'
    },
    {
        'species_name': 'Hippogriff'
    },
    {
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Dragon__((20(204))2((204)14))',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__(20(204))',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Nazgul__(1(320)0)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(3(((241)(320)1)(241)0)4)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(320)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Hippogriff__2',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__(40(423))',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__3',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Nazgul__((241)(320)1)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(241)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__0',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Pteranodon__1',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__3',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__(102)',
        'species_name': 'Pteranodon'
    },
    {
        'species_name': 'Hippogriff'
    },
    {
        'species_name': 'Pteranodon'
    },
    {
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Hippogriff__(2(40(423))3)',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__(40(423))',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__0',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Pteranodon__1',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__0',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__(13(102))',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Dragon__(20(204))',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__2',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__((204)14)',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__3',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__1',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__4',
        'species_name': 'Dragon'
    },
    {
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Dragon__2',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__((20(204))2((204)14))',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__4',
        'species_name': 'Dragon'
    },
    {
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__2',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(320)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Dragon__(20(204))',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__((20(204))2((204)14))',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Dragon__((204)14)',
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Hippogriff__(423)',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__4',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__1',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Nazgul__1',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__(320)',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Nazgul__0',
        'species_name': 'Nazgul'
    },
    {
        'child_name': 'Pteranodon__3',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__4',
        'species_name': 'Pteranodon'
    },
    {
        'child_name': 'Pteranodon__1',
        'species_name': 'Pteranodon'
    },
    {
        'species_name': 'Hippogriff'
    },
    {
        'species_name': 'Pteranodon'
    },
    {
        'species_name': 'Dragon'
    },
    {
        'child_name': 'Hippogriff__(423)',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__((2(40(423))3)(40(423))0)',
        'species_name': 'Hippogriff'
    },
    {
        'child_name': 'Hippogriff__(40(423))',
        'species_name': 'Hippogriff'
    }
]

snapshots['OrientdbMatchQueryTests::test_traverse_and_output 1'] = [
    {
        'parent_name': 'Pteranodon__3'
    },
    {
        'parent_name': 'Pteranodon__(10(13(102)))'
    },
    {
        'parent_name': 'Pteranodon__(341)'
    },
    {
        'parent_name': 'Dragon__2'
    },
    {
        'parent_name': 'Dragon__0'
    },
    {
        'parent_name': 'Dragon__4'
    },
    {
        'parent_name': 'Nazgul__3'
    },
    {
        'parent_name': 'Nazgul__2'
    },
    {
        'parent_name': 'Nazgul__0'
    },
    {
        'parent_name': 'Nazgul__(1(320)0)'
    },
    {
        'parent_name': 'Nazgul__(2(320)((1(320)0)(3(((241)(320)1)(241)0)4)(320)))'
    },
    {
        'parent_name': 'Nazgul__(3(((241)(320)1)(241)0)4)'
    },
    {
        'parent_name': 'Dragon__((20(204))2((204)14))'
    },
    {
        'parent_name': 'Dragon__2'
    },
    {
        'parent_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))'
    },
    {
        'parent_name': 'Hippogriff__((423)41)'
    },
    {
        'parent_name': 'Hippogriff__(40(423))'
    },
    {
        'parent_name': 'Hippogriff__(2(40(423))3)'
    },
    {
        'parent_name': 'Nazgul__3'
    },
    {
        'parent_name': 'Nazgul__(((241)(320)1)(241)0)'
    },
    {
        'parent_name': 'Nazgul__4'
    },
    {
        'parent_name': 'Pteranodon__3'
    },
    {
        'parent_name': 'Pteranodon__(341)'
    },
    {
        'parent_name': 'Pteranodon__(102)'
    },
    {
        'parent_name': 'Hippogriff__4'
    },
    {
        'parent_name': 'Hippogriff__2'
    },
    {
        'parent_name': 'Hippogriff__3'
    },
    {
        'parent_name': 'Hippogriff__(2(40(423))3)'
    },
    {
        'parent_name': 'Hippogriff__1'
    },
    {
        'parent_name': 'Hippogriff__0'
    },
    {
        'parent_name': 'Pteranodon__(10(13(102)))'
    },
    {
        'parent_name': 'Pteranodon__4'
    },
    {
        'parent_name': 'Pteranodon__2'
    },
    {
        'parent_name': 'Pteranodon__1'
    },
    {
        'parent_name': 'Pteranodon__(341)'
    },
    {
        'parent_name': 'Pteranodon__2'
    },
    {
        'parent_name': 'Dragon__2'
    },
    {
        'parent_name': 'Dragon__0'
    },
    {
        'parent_name': 'Dragon__(204)'
    },
    {
        'parent_name': 'Nazgul__2'
    },
    {
        'parent_name': 'Nazgul__4'
    },
    {
        'parent_name': 'Nazgul__1'
    },
    {
        'parent_name': 'Dragon__1'
    },
    {
        'parent_name': 'Dragon__0'
    },
    {
        'parent_name': 'Dragon__(204)'
    },
    {
        'parent_name': 'Hippogriff__4'
    },
    {
        'parent_name': 'Hippogriff__(((423)41)(40(423))(2(40(423))3))'
    },
    {
        'parent_name': 'Hippogriff__(40(423))'
    },
    {
        'parent_name': 'Nazgul__((241)(320)1)'
    },
    {
        'parent_name': 'Nazgul__(3(((241)(320)1)(241)0)4)'
    },
    {
        'parent_name': 'Nazgul__(320)'
    },
    {
        'parent_name': 'Hippogriff__4'
    },
    {
        'parent_name': 'Hippogriff__0'
    },
    {
        'parent_name': 'Hippogriff__(423)'
    },
    {
        'parent_name': 'Pteranodon__1'
    },
    {
        'parent_name': 'Pteranodon__0'
    },
    {
        'parent_name': 'Pteranodon__2'
    },
    {
        'parent_name': 'Pteranodon__((10(13(102)))42)'
    },
    {
        'parent_name': 'Pteranodon__(10(13(102)))'
    },
    {
        'parent_name': 'Pteranodon__2'
    },
    {
        'parent_name': 'Hippogriff__2'
    },
    {
        'parent_name': 'Hippogriff__3'
    },
    {
        'parent_name': 'Hippogriff__(4(((423)41)(40(423))(2(40(423))3))(40(423)))'
    },
    {
        'parent_name': 'Pteranodon__(1(341)2)'
    },
    {
        'parent_name': 'Pteranodon__4'
    },
    {
        'parent_name': 'Pteranodon__(102)'
    },
    {
        'parent_name': 'Dragon__(204)'
    },
    {
        'parent_name': 'Dragon__1'
    },
    {
        'parent_name': 'Dragon__4'
    },
    {
        'parent_name': 'Nazgul__(241)'
    },
    {
        'parent_name': 'Nazgul__(320)'
    },
    {
        'parent_name': 'Nazgul__1'
    },
    {
        'parent_name': 'Dragon__((20(204))2((204)14))'
    },
    {
        'parent_name': 'Dragon__((20(204))((20(204))2((204)14))((204)14))'
    },
    {
        'parent_name': 'Dragon__(20(204))'
    },
    {
        'parent_name': 'Nazgul__(1(320)0)'
    },
    {
        'parent_name': 'Nazgul__(3(((241)(320)1)(241)0)4)'
    },
    {
        'parent_name': 'Nazgul__(320)'
    },
    {
        'parent_name': 'Hippogriff__2'
    },
    {
        'parent_name': 'Hippogriff__(40(423))'
    },
    {
        'parent_name': 'Hippogriff__3'
    },
    {
        'parent_name': 'Nazgul__((241)(320)1)'
    },
    {
        'parent_name': 'Nazgul__(241)'
    },
    {
        'parent_name': 'Nazgul__0'
    },
    {
        'parent_name': 'Pteranodon__1'
    },
    {
        'parent_name': 'Pteranodon__3'
    },
    {
        'parent_name': 'Pteranodon__(102)'
    },
    {
        'parent_name': 'Hippogriff__(2(40(423))3)'
    },
    {
        'parent_name': 'Hippogriff__(40(423))'
    },
    {
        'parent_name': 'Hippogriff__0'
    },
    {
        'parent_name': 'Pteranodon__1'
    },
    {
        'parent_name': 'Pteranodon__0'
    },
    {
        'parent_name': 'Pteranodon__(13(102))'
    },
    {
        'parent_name': 'Dragon__(20(204))'
    },
    {
        'parent_name': 'Dragon__2'
    },
    {
        'parent_name': 'Dragon__((204)14)'
    },
    {
        'parent_name': 'Dragon__3'
    },
    {
        'parent_name': 'Dragon__1'
    },
    {
        'parent_name': 'Dragon__4'
    },
    {
        'parent_name': 'Dragon__2'
    },
    {
        'parent_name': 'Dragon__((20(204))2((204)14))'
    },
    {
        'parent_name': 'Dragon__4'
    },
    {
        'parent_name': 'Nazgul__2'
    },
    {
        'parent_name': 'Nazgul__(320)'
    },
    {
        'parent_name': 'Nazgul__((1(320)0)(3(((241)(320)1)(241)0)4)(320))'
    },
    {
        'parent_name': 'Dragon__(20(204))'
    },
    {
        'parent_name': 'Dragon__((20(204))2((204)14))'
    },
    {
        'parent_name': 'Dragon__((204)14)'
    },
    {
        'parent_name': 'Hippogriff__(423)'
    },
    {
        'parent_name': 'Hippogriff__4'
    },
    {
        'parent_name': 'Hippogriff__1'
    },
    {
        'parent_name': 'Nazgul__1'
    },
    {
        'parent_name': 'Nazgul__(320)'
    },
    {
        'parent_name': 'Nazgul__0'
    },
    {
        'parent_name': 'Pteranodon__3'
    },
    {
        'parent_name': 'Pteranodon__4'
    },
    {
        'parent_name': 'Pteranodon__1'
    },
    {
        'parent_name': 'Hippogriff__(423)'
    },
    {
        'parent_name': 'Hippogriff__((2(40(423))3)(40(423))0)'
    },
    {
        'parent_name': 'Hippogriff__(40(423))'
    }
]

snapshots['OrientdbMatchQueryTests::test_traverse_filter_and_output 1'] = [
    {
        'parent_name': 'Nazgul__2'
    },
    {
        'parent_name': 'Nazgul__2'
    },
    {
        'parent_name': 'Nazgul__2'
    }
]
