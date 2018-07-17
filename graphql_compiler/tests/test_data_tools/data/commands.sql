# Auto-generated output from `generate_test_sql/__init__.py`.
# Do not edit directly!
# Generated on 2018-07-17T18:51:46.983961 from compiler version 1.7.0.

create vertex Species set limbs = 9, name = 'Nazgul', uuid = '0a5d2f34-6baa-9455-e3e7-0682c2094cac'
create vertex Species set limbs = 10, name = 'Pteranodon', uuid = '81332876-37eb-dcd9-e87a-1613e443df78'
create vertex Species set limbs = 4, name = 'Dragon', uuid = 'cca5a5a1-9e4d-6e3c-1846-d424c17c6279'
create vertex Species set limbs = 10, name = 'Hippogriff', uuid = 'af19922a-d9b8-a714-e61a-441c12e0c8b2'
create vertex Animal set birthday = DATE("2012-03-16 00:00:00"), color = 'green', name = 'Nazgul__0', net_worth = 442.69, uuid = '5a921187-19c7-8df4-8f4f-f31e78de5857'
create vertex Animal set birthday = DATE("2006-09-20 00:00:00"), color = 'orange', name = 'Nazgul__1', net_worth = 62.98, uuid = '9ca5499d-004a-e545-a011-6be5ab0c1681'
create vertex Animal set birthday = DATE("2018-11-28 00:00:00"), color = 'red', name = 'Nazgul__2', net_worth = 489.28, uuid = '8b0163c1-cd9d-2b7d-247a-8333f7b0b7d2'
create vertex Animal set birthday = DATE("2015-07-27 00:00:00"), color = 'magenta', name = 'Nazgul__3', net_worth = 603.18, uuid = 'b4e1357d-4a84-eb03-8d1f-d9b74d2b9deb'
create vertex Animal set birthday = DATE("2003-03-18 00:00:00"), color = 'green', name = 'Nazgul__4', net_worth = 656.65, uuid = '935ddd72-5129-fb7c-6288-e1a5cc457821'
create vertex Animal set birthday = DATE("2017-12-16 00:00:00"), color = 'orange', name = 'Nazgul__5', net_worth = 391.29, uuid = 'ec62b2c8-2648-ee38-e074-05eb215663ab'
create vertex Animal set birthday = DATE("2011-11-07 00:00:00"), color = 'yellow', name = 'Nazgul__6', net_worth = 731.48, uuid = '9cdf5a86-5306-f3f5-1516-65705b7c709a'
create vertex Animal set birthday = DATE("2002-09-02 00:00:00"), color = 'red', name = 'Nazgul__7', net_worth = 573.86, uuid = 'd0dfae43-6d16-ee18-5521-16dd2ba4b180'
create vertex Animal set birthday = DATE("2010-05-11 00:00:00"), color = 'magenta', name = 'Nazgul__8', net_worth = 980.51, uuid = 'a28f5ab0-1fdb-8b32-06d5-99e812f175ff'
create vertex Animal set birthday = DATE("2015-12-01 00:00:00"), color = 'blue', name = 'Nazgul__9', net_worth = 425.61, uuid = '1fb797fa-b7d6-467b-2f5a-522af87f43fd'
create vertex Animal set birthday = DATE("2005-06-02 00:00:00"), color = 'red', name = 'Nazgul__10', net_worth = 467.13, uuid = '11ebcd49-428a-1c22-d5fd-b76a19fbeb1d'
create vertex Animal set birthday = DATE("2006-09-24 00:00:00"), color = 'blue', name = 'Nazgul__11', net_worth = 918.48, uuid = 'fcfcfa81-b306-d700-19d5-f97098b33c6e'
create vertex Animal set birthday = DATE("2006-04-17 00:00:00"), color = 'orange', name = 'Nazgul__12', net_worth = 442.31, uuid = 'ad1b8f60-c9e4-dab2-0edc-6d2bc470f0e7'
create vertex Animal set birthday = DATE("2016-12-19 00:00:00"), color = 'indigo', name = 'Nazgul__13', net_worth = 388.64, uuid = 'ae68690a-78bc-7175-0361-524c2cc0f859'
create vertex Animal set birthday = DATE("2010-02-22 00:00:00"), color = 'black', name = 'Nazgul__14', net_worth = 481.82, uuid = '143e2e04-bdd7-d19b-753c-7c99032f06ca'
create vertex Animal set birthday = DATE("2013-02-07 00:00:00"), color = 'magenta', name = 'Nazgul__15', net_worth = 448.13, uuid = '14aa451c-a69c-fb85-d432-f8db6a174c1c'
create vertex Animal set birthday = DATE("2008-11-26 00:00:00"), color = 'black', name = 'Nazgul__16', net_worth = 603.97, uuid = '105ada6b-7202-99e3-2a69-acc70bf9c0ef'
create vertex Animal set birthday = DATE("2008-10-25 00:00:00"), color = 'green', name = 'Nazgul__17', net_worth = 812.41, uuid = '7e9cf84f-09f6-048f-e245-a4600004884c'
create vertex Animal set birthday = DATE("2007-09-09 00:00:00"), color = 'indigo', name = 'Nazgul__18', net_worth = 213.52, uuid = 'b9bdee2d-d663-049d-155e-18b1fa83ada4'
create vertex Animal set birthday = DATE("2012-11-08 00:00:00"), color = 'red', name = 'Nazgul__19', net_worth = 978.51, uuid = '19086515-9cb0-17c1-8741-ae91acfebb4b'
create vertex Animal set birthday = DATE("2002-11-02 00:00:00"), color = 'red', name = 'Nazgul__(11627)', net_worth = 205.73, uuid = 'a51ad4f3-a699-bae0-d138-d1508557716a'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(11627)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(11627)') to (select from Animal where name = 'Nazgul__16')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(11627)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(11627)') to (select from Animal where name = 'Nazgul__7')
create vertex Animal set birthday = DATE("2010-03-17 00:00:00"), color = 'green', name = 'Nazgul__(101956)', net_worth = 8.89, uuid = 'a3e04b3b-756b-0715-e718-0322a4e695c9'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(101956)') to (select from Animal where name = 'Nazgul__10')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(101956)') to (select from Animal where name = 'Nazgul__19')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(101956)') to (select from Animal where name = 'Nazgul__5')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(101956)') to (select from Animal where name = 'Nazgul__6')
create vertex Animal set birthday = DATE("2002-08-11 00:00:00"), color = 'green', name = 'Nazgul__(151737)', net_worth = 989.3, uuid = '09215f4f-9edb-95f2-c787-ddfb5697f17c'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(151737)') to (select from Animal where name = 'Nazgul__15')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(151737)') to (select from Animal where name = 'Nazgul__17')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(151737)') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(151737)') to (select from Animal where name = 'Nazgul__7')
create vertex Animal set birthday = DATE("2006-05-03 00:00:00"), color = 'yellow', name = 'Nazgul__((101956)1627)', net_worth = 908.65, uuid = '122411e6-ba89-82dd-85e6-9ea9db66bfda'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((101956)1627)') to (select from Animal where name = 'Nazgul__(101956)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((101956)1627)') to (select from Animal where name = 'Nazgul__16')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((101956)1627)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((101956)1627)') to (select from Animal where name = 'Nazgul__7')
create vertex Animal set birthday = DATE("2006-09-05 00:00:00"), color = 'red', name = 'Nazgul__(((101956)1627)(11627)118)', net_worth = 166.55, uuid = '7f6b8793-b318-ad4c-1db2-b4527aa56a18'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)') to (select from Animal where name = 'Nazgul__((101956)1627)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)') to (select from Animal where name = 'Nazgul__(11627)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)') to (select from Animal where name = 'Nazgul__11')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)') to (select from Animal where name = 'Nazgul__8')
create vertex Animal set birthday = DATE("2000-05-15 00:00:00"), color = 'red', name = 'Nazgul__((((101956)1627)(11627)118)(11627)142)', net_worth = 448.54, uuid = 'bff773ce-32b2-c492-15ac-e7a1ceca2ee3'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(11627)142)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(11627)142)') to (select from Animal where name = 'Nazgul__(11627)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(11627)142)') to (select from Animal where name = 'Nazgul__14')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(11627)142)') to (select from Animal where name = 'Nazgul__2')
create vertex Animal set birthday = DATE("2003-03-04 00:00:00"), color = 'magenta', name = 'Nazgul__(10121517)', net_worth = 821.98, uuid = 'ffc573d5-fd0b-a70e-385a-f4635e4af862'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(10121517)') to (select from Animal where name = 'Nazgul__10')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(10121517)') to (select from Animal where name = 'Nazgul__12')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(10121517)') to (select from Animal where name = 'Nazgul__15')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(10121517)') to (select from Animal where name = 'Nazgul__17')
create vertex Animal set birthday = DATE("2000-12-07 00:00:00"), color = 'blue', name = 'Nazgul__(((101956)1627)(11627)014)', net_worth = 146.35, uuid = '65e04993-7f41-1fed-1e70-e79933a1d1c2'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)014)') to (select from Animal where name = 'Nazgul__((101956)1627)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)014)') to (select from Animal where name = 'Nazgul__(11627)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)014)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)014)') to (select from Animal where name = 'Nazgul__14')
create vertex Animal set birthday = DATE("2012-06-15 00:00:00"), color = 'magenta', name = 'Nazgul__(101545)', net_worth = 679.31, uuid = '7ce71b48-fba5-2e59-98a3-3736fd1ac7ce'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(101545)') to (select from Animal where name = 'Nazgul__10')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(101545)') to (select from Animal where name = 'Nazgul__15')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(101545)') to (select from Animal where name = 'Nazgul__4')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(101545)') to (select from Animal where name = 'Nazgul__5')
create vertex Animal set birthday = DATE("2002-04-22 00:00:00"), color = 'red', name = 'Nazgul__(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)', net_worth = 842.33, uuid = 'd17034ce-5179-7350-e625-6403bf3df0bb'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)') to (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(11627)142)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)') to (select from Animal where name = 'Nazgul__(101545)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)') to (select from Animal where name = 'Nazgul__18')
create vertex Animal set birthday = DATE("2002-04-22 00:00:00"), color = 'red', name = 'Nazgul__((((101956)1627)(11627)118)(101956)117)', net_worth = 448.58, uuid = 'ea5f24b6-de6f-ec4b-843b-2a7d15ab2c21'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101956)117)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101956)117)') to (select from Animal where name = 'Nazgul__(101956)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101956)117)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101956)117)') to (select from Animal where name = 'Nazgul__17')
create vertex Animal set birthday = DATE("2012-10-22 00:00:00"), color = 'magenta', name = 'Nazgul__((((101956)1627)(11627)118)(10121517)1114)', net_worth = 990.53, uuid = '809f2923-87a1-798f-e6ad-dd9e61d9fe39'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(10121517)1114)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(10121517)1114)') to (select from Animal where name = 'Nazgul__(10121517)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(10121517)1114)') to (select from Animal where name = 'Nazgul__11')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(10121517)1114)') to (select from Animal where name = 'Nazgul__14')
create vertex Animal set birthday = DATE("2018-08-07 00:00:00"), color = 'orange', name = 'Nazgul__(((101956)1627)(101545)176)', net_worth = 864.77, uuid = 'f8f8f071-d360-da69-6af7-9ad2993ec8c6'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(101545)176)') to (select from Animal where name = 'Nazgul__((101956)1627)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(101545)176)') to (select from Animal where name = 'Nazgul__(101545)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(101545)176)') to (select from Animal where name = 'Nazgul__17')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)1627)(101545)176)') to (select from Animal where name = 'Nazgul__6')
create vertex Animal set birthday = DATE("2017-04-12 00:00:00"), color = 'orange', name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(((101956)1627)(11627)118)09)', net_worth = 810.03, uuid = '10cc8711-552a-e5ca-4124-405b91fcfe88'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(((101956)1627)(11627)118)09)') to (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(((101956)1627)(11627)118)09)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(((101956)1627)(11627)118)09)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(((101956)1627)(11627)118)09)') to (select from Animal where name = 'Nazgul__9')
create vertex Animal set birthday = DATE("2002-11-17 00:00:00"), color = 'yellow', name = 'Nazgul__((101956)249)', net_worth = 81.61, uuid = 'f11ddff7-0e37-0526-5582-a3bdd476fe38'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((101956)249)') to (select from Animal where name = 'Nazgul__(101956)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((101956)249)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((101956)249)') to (select from Animal where name = 'Nazgul__4')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((101956)249)') to (select from Animal where name = 'Nazgul__9')
create vertex Animal set birthday = DATE("2002-01-18 00:00:00"), color = 'yellow', name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)', net_worth = 629.96, uuid = '0c0a5967-7579-501a-62fd-a854775e0ec3'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)') to (select from Animal where name = 'Nazgul__(101545)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)') to (select from Animal where name = 'Nazgul__12')
create vertex Animal set birthday = DATE("2013-04-24 00:00:00"), color = 'indigo', name = 'Nazgul__(1213193)', net_worth = 958.46, uuid = 'a6855857-567e-5862-ef15-1673a1df3da7'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(1213193)') to (select from Animal where name = 'Nazgul__12')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(1213193)') to (select from Animal where name = 'Nazgul__13')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(1213193)') to (select from Animal where name = 'Nazgul__19')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(1213193)') to (select from Animal where name = 'Nazgul__3')
create vertex Animal set birthday = DATE("2015-01-02 00:00:00"), color = 'yellow', name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)1627)(11627)014)1014)', net_worth = 934.28, uuid = 'c1b199c4-5f1f-f97c-71cf-f814645bd776'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)1627)(11627)014)1014)') to (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)1627)(11627)014)1014)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)014)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)1627)(11627)014)1014)') to (select from Animal where name = 'Nazgul__10')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)1627)(11627)014)1014)') to (select from Animal where name = 'Nazgul__14')
create vertex Animal set birthday = DATE("2016-08-15 00:00:00"), color = 'orange', name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)', net_worth = 523.71, uuid = '3acaaf82-374a-6cc9-e039-7e67926146de'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)') to (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)') to (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(11627)142)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)') to (select from Animal where name = 'Nazgul__((101956)249)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)') to (select from Animal where name = 'Nazgul__18')
create vertex Animal set birthday = DATE("2001-10-21 00:00:00"), color = 'yellow', name = 'Nazgul__(((101956)249)(1213193)195)', net_worth = 30.7, uuid = 'ef8d9ff0-1583-1fee-ec41-e6f66c0be55c'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)249)(1213193)195)') to (select from Animal where name = 'Nazgul__((101956)249)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)249)(1213193)195)') to (select from Animal where name = 'Nazgul__(1213193)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)249)(1213193)195)') to (select from Animal where name = 'Nazgul__19')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((101956)249)(1213193)195)') to (select from Animal where name = 'Nazgul__5')
create vertex Animal set birthday = DATE("2002-09-10 00:00:00"), color = 'green', name = 'Nazgul__((((101956)1627)(11627)014)(1213193)117)', net_worth = 177.9, uuid = '40a978bf-b8f8-903b-5312-5ffdf655860b'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)014)(1213193)117)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)014)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)014)(1213193)117)') to (select from Animal where name = 'Nazgul__(1213193)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)014)(1213193)117)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)014)(1213193)117)') to (select from Animal where name = 'Nazgul__17')
create vertex Animal set birthday = DATE("2005-09-27 00:00:00"), color = 'black', name = 'Nazgul__((((101956)1627)(11627)118)((101956)249)149)', net_worth = 232.86, uuid = 'e6a1a40b-f031-f4b9-bb6b-0095ac7b7ab2'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)((101956)249)149)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)((101956)249)149)') to (select from Animal where name = 'Nazgul__((101956)249)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)((101956)249)149)') to (select from Animal where name = 'Nazgul__14')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)((101956)249)149)') to (select from Animal where name = 'Nazgul__9')
create vertex Animal set birthday = DATE("2008-04-27 00:00:00"), color = 'green', name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)', net_worth = 958.14, uuid = 'f76dce6e-0726-d44a-2152-03c7421aa15e'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)') to (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)') to (select from Animal where name = 'Nazgul__(11627)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)') to (select from Animal where name = 'Nazgul__19')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)') to (select from Animal where name = 'Nazgul__5')
create vertex Animal set birthday = DATE("2004-10-09 00:00:00"), color = 'green', name = 'Nazgul__(((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)', net_worth = 419.78, uuid = 'cdec85da-200f-7753-f217-faac259cff81'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)') to (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)') to (select from Animal where name = 'Nazgul__(((101956)1627)(11627)014)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)') to (select from Animal where name = 'Nazgul__4')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)') to (select from Animal where name = 'Nazgul__7')
create vertex Animal set birthday = DATE("2012-08-15 00:00:00"), color = 'blue', name = 'Nazgul__(0235)', net_worth = 376.43, uuid = '5ac4b6c7-a310-34dd-4c4b-91fe6c148fc6'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0235)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0235)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0235)') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0235)') to (select from Animal where name = 'Nazgul__5')
create vertex Animal set birthday = DATE("2015-04-16 00:00:00"), color = 'indigo', name = 'Nazgul__((((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)((((101956)1627)(11627)014)(1213193)117)019)', net_worth = 688.2, uuid = '788c161e-f3cc-9d8a-4b16-78e45f20f406'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)((((101956)1627)(11627)014)(1213193)117)019)') to (select from Animal where name = 'Nazgul__(((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)((((101956)1627)(11627)014)(1213193)117)019)') to (select from Animal where name = 'Nazgul__((((101956)1627)(11627)014)(1213193)117)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)((((101956)1627)(11627)014)(1213193)117)019)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)((((101956)1627)(11627)014)(1213193)117)019)') to (select from Animal where name = 'Nazgul__19')
create vertex Animal set birthday = DATE("2009-05-18 00:00:00"), color = 'green', name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(11627)(1213193)18)', net_worth = 86.49, uuid = 'f5a3e893-3f7a-2748-2cbb-93c26e84f8ea'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(11627)(1213193)18)') to (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(11627)(1213193)18)') to (select from Animal where name = 'Nazgul__(11627)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(11627)(1213193)18)') to (select from Animal where name = 'Nazgul__(1213193)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(11627)(1213193)18)') to (select from Animal where name = 'Nazgul__18')
create vertex Animal set birthday = DATE("2011-07-05 00:00:00"), color = 'orange', name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)249)(1213193)195)(101956)13)', net_worth = 706.29, uuid = '4c6e6fbb-37fe-f6b5-01fd-a698764657ca'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)249)(1213193)195)(101956)13)') to (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)249)(1213193)195)(101956)13)') to (select from Animal where name = 'Nazgul__(((101956)249)(1213193)195)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)249)(1213193)195)(101956)13)') to (select from Animal where name = 'Nazgul__(101956)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)249)(1213193)195)(101956)13)') to (select from Animal where name = 'Nazgul__13')
create vertex Animal set birthday = DATE("2004-04-22 00:00:00"), color = 'red', name = 'Nazgul__((((101956)1627)(101545)176)(1213193)(151737)11)', net_worth = 908.77, uuid = '656fa7e6-b5c0-3f6f-94e4-cc44e3fbdbda'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(101545)176)(1213193)(151737)11)') to (select from Animal where name = 'Nazgul__(((101956)1627)(101545)176)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(101545)176)(1213193)(151737)11)') to (select from Animal where name = 'Nazgul__(1213193)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(101545)176)(1213193)(151737)11)') to (select from Animal where name = 'Nazgul__(151737)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((101956)1627)(101545)176)(1213193)(151737)11)') to (select from Animal where name = 'Nazgul__11')
create vertex Animal set birthday = DATE("2014-01-25 00:00:00"), color = 'indigo', name = 'Nazgul__((((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)114)', net_worth = 282.74, uuid = 'dc0520a4-87ba-3b90-1e41-5c4e57030ede'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)114)') to (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)114)') to (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)114)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)114)') to (select from Animal where name = 'Nazgul__14')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__0') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__1') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__2') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__3') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__4') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__5') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__6') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__7') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__8') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__9') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__10') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__11') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__12') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__13') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__14') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__15') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__16') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__17') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__18') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__19') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(11627)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(101956)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(151737)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((101956)1627)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)118)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(11627)142)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(10121517)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((101956)1627)(11627)014)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(101545)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101956)117)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(10121517)1114)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((101956)1627)(101545)176)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(((101956)1627)(11627)118)09)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((101956)249)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)(101545)112)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(1213193)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)1627)(11627)014)1014)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((101956)249)(1213193)195)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)014)(1213193)117)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((101956)1627)(11627)118)((101956)249)149)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(0235)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)(11627)195)(((101956)1627)(11627)014)47)((((101956)1627)(11627)014)(1213193)117)019)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(11627)(1213193)18)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((101956)1627)(11627)118)(101545)112)(((101956)249)(1213193)195)(101956)13)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((101956)1627)(101545)176)(1213193)(151737)11)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((((101956)1627)(11627)118)(101545)112)((((101956)1627)(11627)118)(11627)142)((101956)249)18)(((((101956)1627)(11627)118)(11627)142)(((101956)1627)(11627)118)(101545)18)114)') to (select from Species where name = 'Nazgul')
create vertex Animal set birthday = DATE("2007-08-12 00:00:00"), color = 'magenta', name = 'Pteranodon__0', net_worth = 778.55, uuid = 'a08c3a00-85e7-4250-92f0-78b822696227'
create vertex Animal set birthday = DATE("2002-02-04 00:00:00"), color = 'magenta', name = 'Pteranodon__1', net_worth = 401.21, uuid = '713eceb1-4ad1-2b4c-4753-4952c9c5fef1'
create vertex Animal set birthday = DATE("2008-05-14 00:00:00"), color = 'green', name = 'Pteranodon__2', net_worth = 694.69, uuid = 'ab12fb53-8f42-cebe-23b8-70f377cb1a27'
create vertex Animal set birthday = DATE("2002-06-25 00:00:00"), color = 'yellow', name = 'Pteranodon__3', net_worth = 215.71, uuid = 'f55b2e5c-a6ed-0ac0-7e22-e1b751783032'
create vertex Animal set birthday = DATE("2001-12-26 00:00:00"), color = 'black', name = 'Pteranodon__4', net_worth = 395.11, uuid = 'fa999f9b-86de-3365-d8a2-30de02969326'
create vertex Animal set birthday = DATE("2016-09-21 00:00:00"), color = 'indigo', name = 'Pteranodon__5', net_worth = 226.68, uuid = '9ef1c846-1dbc-24fd-0a8a-a1e45c7cbc62'
create vertex Animal set birthday = DATE("2013-05-10 00:00:00"), color = 'yellow', name = 'Pteranodon__6', net_worth = 648.0, uuid = '30f2c485-49b5-64fb-92a6-51d7c069c542'
create vertex Animal set birthday = DATE("2003-05-28 00:00:00"), color = 'blue', name = 'Pteranodon__7', net_worth = 427.29, uuid = '50ea1324-862f-78e1-25c2-9b6ab575bc6e'
create vertex Animal set birthday = DATE("2001-03-02 00:00:00"), color = 'blue', name = 'Pteranodon__8', net_worth = 638.07, uuid = '636abf8c-e7e3-f52c-0cbf-404db5c25d42'
create vertex Animal set birthday = DATE("2001-09-19 00:00:00"), color = 'yellow', name = 'Pteranodon__9', net_worth = 648.51, uuid = 'e2091f49-e0a1-0d2b-c57c-799848d002be'
create vertex Animal set birthday = DATE("2009-09-07 00:00:00"), color = 'magenta', name = 'Pteranodon__10', net_worth = 265.87, uuid = 'ef1fa0a3-bc02-ba67-ee04-bdde8c141838'
create vertex Animal set birthday = DATE("2000-01-12 00:00:00"), color = 'green', name = 'Pteranodon__11', net_worth = 222.16, uuid = '598ca3b4-29b1-0823-0d74-22560b36f3cd'
create vertex Animal set birthday = DATE("2006-02-25 00:00:00"), color = 'yellow', name = 'Pteranodon__12', net_worth = 794.79, uuid = 'ebe0572c-8ec9-ea98-6581-f9349bcfb1c4'
create vertex Animal set birthday = DATE("2009-03-03 00:00:00"), color = 'green', name = 'Pteranodon__13', net_worth = 869.94, uuid = 'e4bacd78-74ab-a9fc-8930-d17952ab793f'
create vertex Animal set birthday = DATE("2013-04-25 00:00:00"), color = 'black', name = 'Pteranodon__14', net_worth = 254.63, uuid = '339d78f5-d658-b1b3-3012-ae1c5882e3bb'
create vertex Animal set birthday = DATE("2010-01-14 00:00:00"), color = 'green', name = 'Pteranodon__15', net_worth = 438.19, uuid = '3d6e2667-b665-1d6e-df39-ccaa580c79fc'
create vertex Animal set birthday = DATE("2002-01-03 00:00:00"), color = 'yellow', name = 'Pteranodon__16', net_worth = 765.44, uuid = 'fa98c115-6980-b561-cf1a-ccc1eaca3811'
create vertex Animal set birthday = DATE("2015-07-25 00:00:00"), color = 'magenta', name = 'Pteranodon__17', net_worth = 394.47, uuid = '36a5be06-eb52-ee01-e25e-651269fcbef0'
create vertex Animal set birthday = DATE("2016-12-09 00:00:00"), color = 'blue', name = 'Pteranodon__18', net_worth = 434.84, uuid = '7d718591-3fee-2fc7-2e2d-ffdff57b8a92'
create vertex Animal set birthday = DATE("2014-02-21 00:00:00"), color = 'red', name = 'Pteranodon__19', net_worth = 248.77, uuid = '3b56735e-45c5-96d4-42d0-1ba3a2652c9e'
create vertex Animal set birthday = DATE("2005-12-16 00:00:00"), color = 'yellow', name = 'Pteranodon__(1112135)', net_worth = 229.56, uuid = '0cbdc014-dbed-b42e-6da3-13e783e9973b'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1112135)') to (select from Animal where name = 'Pteranodon__11')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1112135)') to (select from Animal where name = 'Pteranodon__12')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1112135)') to (select from Animal where name = 'Pteranodon__13')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1112135)') to (select from Animal where name = 'Pteranodon__5')
create vertex Animal set birthday = DATE("2004-08-09 00:00:00"), color = 'black', name = 'Pteranodon__(1013155)', net_worth = 171.38, uuid = '84a5b1c3-1095-e497-3d79-8f0be6cd3595'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1013155)') to (select from Animal where name = 'Pteranodon__10')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1013155)') to (select from Animal where name = 'Pteranodon__13')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1013155)') to (select from Animal where name = 'Pteranodon__15')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1013155)') to (select from Animal where name = 'Pteranodon__5')
create vertex Animal set birthday = DATE("2014-10-16 00:00:00"), color = 'orange', name = 'Pteranodon__(012177)', net_worth = 695.69, uuid = '1392a255-fdc1-2930-82ae-752f2d4076bc'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012177)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012177)') to (select from Animal where name = 'Pteranodon__12')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012177)') to (select from Animal where name = 'Pteranodon__17')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012177)') to (select from Animal where name = 'Pteranodon__7')
create vertex Animal set birthday = DATE("2005-12-16 00:00:00"), color = 'yellow', name = 'Pteranodon__(1617184)', net_worth = 163.03, uuid = '989bb030-86c4-7b06-06a8-e22fd57caf0d'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1617184)') to (select from Animal where name = 'Pteranodon__16')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1617184)') to (select from Animal where name = 'Pteranodon__17')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1617184)') to (select from Animal where name = 'Pteranodon__18')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1617184)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set birthday = DATE("2013-10-22 00:00:00"), color = 'magenta', name = 'Pteranodon__((1013155)131719)', net_worth = 384.09, uuid = '425832c0-142a-6c95-d908-2a42b4480761'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((1013155)131719)') to (select from Animal where name = 'Pteranodon__(1013155)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((1013155)131719)') to (select from Animal where name = 'Pteranodon__13')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((1013155)131719)') to (select from Animal where name = 'Pteranodon__17')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((1013155)131719)') to (select from Animal where name = 'Pteranodon__19')
create vertex Animal set birthday = DATE("2005-05-16 00:00:00"), color = 'black', name = 'Pteranodon__(((1013155)131719)0118)', net_worth = 732.31, uuid = '42965873-39d5-b552-a867-a0f0a8e6a772'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)0118)') to (select from Animal where name = 'Pteranodon__((1013155)131719)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)0118)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)0118)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)0118)') to (select from Animal where name = 'Pteranodon__18')
create vertex Animal set birthday = DATE("2006-08-04 00:00:00"), color = 'orange', name = 'Pteranodon__(01163)', net_worth = 921.98, uuid = '53a081a6-a764-7989-f20e-8bda39cc6d88'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(01163)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(01163)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(01163)') to (select from Animal where name = 'Pteranodon__16')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(01163)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set birthday = DATE("2007-04-15 00:00:00"), color = 'yellow', name = 'Pteranodon__(121738)', net_worth = 735.63, uuid = 'bf4fa4a3-c908-53fd-fc9e-a692ba626aee'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(121738)') to (select from Animal where name = 'Pteranodon__12')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(121738)') to (select from Animal where name = 'Pteranodon__17')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(121738)') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(121738)') to (select from Animal where name = 'Pteranodon__8')
create vertex Animal set birthday = DATE("2011-08-24 00:00:00"), color = 'magenta', name = 'Pteranodon__((((1013155)131719)0118)11219)', net_worth = 699.6, uuid = '2bdb5720-63ea-a07f-f436-498e68afe2b8'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)') to (select from Animal where name = 'Pteranodon__(((1013155)131719)0118)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)') to (select from Animal where name = 'Pteranodon__12')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)') to (select from Animal where name = 'Pteranodon__19')
create vertex Animal set birthday = DATE("2011-08-13 00:00:00"), color = 'indigo', name = 'Pteranodon__(((1013155)131719)256)', net_worth = 150.07, uuid = '1417d4f9-b7c1-44fb-2b16-ad048fb87c76'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)256)') to (select from Animal where name = 'Pteranodon__((1013155)131719)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)256)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)256)') to (select from Animal where name = 'Pteranodon__5')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)256)') to (select from Animal where name = 'Pteranodon__6')
create vertex Animal set birthday = DATE("2006-09-13 00:00:00"), color = 'yellow', name = 'Pteranodon__(((1013155)131719)(1013155)187)', net_worth = 507.43, uuid = 'e3b4df81-eeb3-462c-a032-149d06fafb60'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1013155)187)') to (select from Animal where name = 'Pteranodon__((1013155)131719)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1013155)187)') to (select from Animal where name = 'Pteranodon__(1013155)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1013155)187)') to (select from Animal where name = 'Pteranodon__18')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1013155)187)') to (select from Animal where name = 'Pteranodon__7')
create vertex Animal set birthday = DATE("2002-05-02 00:00:00"), color = 'yellow', name = 'Pteranodon__(((1013155)131719)(1617184)105)', net_worth = 273.04, uuid = '09ce15a8-afd4-fc7b-ef20-8346432fb308'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1617184)105)') to (select from Animal where name = 'Pteranodon__((1013155)131719)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1617184)105)') to (select from Animal where name = 'Pteranodon__(1617184)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1617184)105)') to (select from Animal where name = 'Pteranodon__10')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1617184)105)') to (select from Animal where name = 'Pteranodon__5')
create vertex Animal set birthday = DATE("2015-04-04 00:00:00"), color = 'yellow', name = 'Pteranodon__((((1013155)131719)(1617184)105)(012177)(1013155)8)', net_worth = 981.72, uuid = '8429aeae-877e-5ea1-c339-93f235045f77'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(012177)(1013155)8)') to (select from Animal where name = 'Pteranodon__(((1013155)131719)(1617184)105)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(012177)(1013155)8)') to (select from Animal where name = 'Pteranodon__(012177)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(012177)(1013155)8)') to (select from Animal where name = 'Pteranodon__(1013155)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(012177)(1013155)8)') to (select from Animal where name = 'Pteranodon__8')
create vertex Animal set birthday = DATE("2017-04-21 00:00:00"), color = 'indigo', name = 'Pteranodon__((((1013155)131719)(1617184)105)(01163)(012177)8)', net_worth = 9.09, uuid = '5a7583c0-e02a-35e9-ae6b-4c8e88644581'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(01163)(012177)8)') to (select from Animal where name = 'Pteranodon__(((1013155)131719)(1617184)105)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(01163)(012177)8)') to (select from Animal where name = 'Pteranodon__(01163)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(01163)(012177)8)') to (select from Animal where name = 'Pteranodon__(012177)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(01163)(012177)8)') to (select from Animal where name = 'Pteranodon__8')
create vertex Animal set birthday = DATE("2002-01-04 00:00:00"), color = 'red', name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)', net_worth = 929.38, uuid = 'fccae6b8-6e56-6274-99c7-abea6756264d'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)') to (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(012177)(1013155)8)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)') to (select from Animal where name = 'Pteranodon__(121738)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)') to (select from Animal where name = 'Pteranodon__12')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)') to (select from Animal where name = 'Pteranodon__19')
create vertex Animal set birthday = DATE("2008-12-21 00:00:00"), color = 'green', name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)', net_worth = 946.25, uuid = '4408c04c-6f44-6806-c137-8e75627b9de7'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)') to (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(01163)(012177)8)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)') to (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)') to (select from Animal where name = 'Pteranodon__(121738)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)') to (select from Animal where name = 'Pteranodon__16')
create vertex Animal set birthday = DATE("2000-11-18 00:00:00"), color = 'yellow', name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)', net_worth = 798.47, uuid = '62574c5a-9033-74bf-c812-36e6ec77cfc8'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)') to (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)') to (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)') to (select from Animal where name = 'Pteranodon__19')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)') to (select from Animal where name = 'Pteranodon__6')
create vertex Animal set birthday = DATE("2009-09-07 00:00:00"), color = 'black', name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)13)', net_worth = 891.75, uuid = 'a1832fdb-31cb-5e8e-ae25-62ca28948b4c'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)13)') to (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)13)') to (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(01163)(012177)8)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)13)') to (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)13)') to (select from Animal where name = 'Pteranodon__13')
create vertex Animal set birthday = DATE("2003-12-26 00:00:00"), color = 'indigo', name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)10172)', net_worth = 634.74, uuid = 'b47a5dce-cf70-9452-ce8c-037ee51c0cdb'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)10172)') to (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)10172)') to (select from Animal where name = 'Pteranodon__10')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)10172)') to (select from Animal where name = 'Pteranodon__17')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)10172)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set birthday = DATE("2014-03-12 00:00:00"), color = 'yellow', name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)(((1013155)131719)(1013155)187)9)', net_worth = 435.61, uuid = '4e98ce25-1733-7a7c-53e8-36639c14940d'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)(((1013155)131719)(1013155)187)9)') to (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)(((1013155)131719)(1013155)187)9)') to (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)(((1013155)131719)(1013155)187)9)') to (select from Animal where name = 'Pteranodon__(((1013155)131719)(1013155)187)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)(((1013155)131719)(1013155)187)9)') to (select from Animal where name = 'Pteranodon__9')
create vertex Animal set birthday = DATE("2007-12-04 00:00:00"), color = 'orange', name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(((1013155)131719)0118)(01163)(121738))', net_worth = 81.48, uuid = '4741ee56-b5e2-834d-907d-85322076d932'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(((1013155)131719)0118)(01163)(121738))') to (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(012177)(1013155)8)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(((1013155)131719)0118)(01163)(121738))') to (select from Animal where name = 'Pteranodon__(((1013155)131719)0118)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(((1013155)131719)0118)(01163)(121738))') to (select from Animal where name = 'Pteranodon__(01163)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(((1013155)131719)0118)(01163)(121738))') to (select from Animal where name = 'Pteranodon__(121738)')
create vertex Animal set birthday = DATE("2016-12-09 00:00:00"), color = 'indigo', name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)', net_worth = 905.26, uuid = '0b09ec41-789a-2829-8a66-3359abe0a177'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)') to (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)') to (select from Animal where name = 'Pteranodon__(((1013155)131719)256)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)') to (select from Animal where name = 'Pteranodon__14')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set birthday = DATE("2003-11-26 00:00:00"), color = 'magenta', name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)', net_worth = 705.31, uuid = 'ddda17a3-6779-de0d-25c1-df67987d616d'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)') to (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)') to (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(012177)(1013155)8)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)') to (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)') to (select from Animal where name = 'Pteranodon__11')
create vertex Animal set birthday = DATE("2006-08-03 00:00:00"), color = 'indigo', name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)(((1013155)131719)(1617184)105)(012177))', net_worth = 559.79, uuid = 'a197b954-b283-5498-be80-793eb0f1bb1d'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)(((1013155)131719)(1617184)105)(012177))') to (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)(((1013155)131719)(1617184)105)(012177))') to (select from Animal where name = 'Pteranodon__(((1013155)131719)(1013155)187)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)(((1013155)131719)(1617184)105)(012177))') to (select from Animal where name = 'Pteranodon__(((1013155)131719)(1617184)105)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)(((1013155)131719)(1617184)105)(012177))') to (select from Animal where name = 'Pteranodon__(012177)')
create vertex Animal set birthday = DATE("2003-07-26 00:00:00"), color = 'black', name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)', net_worth = 316.08, uuid = '271f2772-8d7f-7ba5-72e6-316ee6710ad2'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)') to (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)') to (select from Animal where name = 'Pteranodon__(((1013155)131719)(1013155)187)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)') to (select from Animal where name = 'Pteranodon__11')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)') to (select from Animal where name = 'Pteranodon__8')
create vertex Animal set birthday = DATE("2001-01-15 00:00:00"), color = 'orange', name = 'Pteranodon__((((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(121738)8)', net_worth = 2.46, uuid = '2287401b-a7bb-aa76-e9a4-a856556b20fa'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(121738)8)') to (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(121738)8)') to (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(121738)8)') to (select from Animal where name = 'Pteranodon__(121738)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(121738)8)') to (select from Animal where name = 'Pteranodon__8')
create vertex Animal set birthday = DATE("2016-02-09 00:00:00"), color = 'indigo', name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(01163)(121738)4)', net_worth = 22.72, uuid = '832c9b79-60c8-e5a0-d560-e64c55f7792a'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(01163)(121738)4)') to (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(01163)(121738)4)') to (select from Animal where name = 'Pteranodon__(01163)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(01163)(121738)4)') to (select from Animal where name = 'Pteranodon__(121738)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(01163)(121738)4)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set birthday = DATE("2017-08-23 00:00:00"), color = 'orange', name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)09)', net_worth = 168.16, uuid = 'b2e74e77-0fe1-cedf-a538-790169f12ccd'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)09)') to (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)09)') to (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)09)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)09)') to (select from Animal where name = 'Pteranodon__9')
create vertex Animal set birthday = DATE("2015-05-01 00:00:00"), color = 'magenta', name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)((((1013155)131719)0118)11219)(1013155)19)', net_worth = 802.4, uuid = 'ac1d02e8-417d-f4f8-c1a7-de009ec12fa2'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)((((1013155)131719)0118)11219)(1013155)19)') to (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)((((1013155)131719)0118)11219)(1013155)19)') to (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)((((1013155)131719)0118)11219)(1013155)19)') to (select from Animal where name = 'Pteranodon__(1013155)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)((((1013155)131719)0118)11219)(1013155)19)') to (select from Animal where name = 'Pteranodon__19')
create vertex Animal set birthday = DATE("2010-11-14 00:00:00"), color = 'yellow', name = 'Pteranodon__(171869)', net_worth = 80.45, uuid = '037e5725-e5a1-bdae-a747-795eb0c952af'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(171869)') to (select from Animal where name = 'Pteranodon__17')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(171869)') to (select from Animal where name = 'Pteranodon__18')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(171869)') to (select from Animal where name = 'Pteranodon__6')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(171869)') to (select from Animal where name = 'Pteranodon__9')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__0') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__1') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__2') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__3') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__4') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__5') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__6') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__7') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__8') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__9') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__10') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__11') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__12') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__13') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__14') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__15') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__16') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__17') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__18') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__19') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(1112135)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(1013155)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(012177)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(1617184)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((1013155)131719)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((1013155)131719)0118)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(01163)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(121738)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((1013155)131719)0118)11219)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((1013155)131719)256)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1013155)187)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((1013155)131719)(1617184)105)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(012177)(1013155)8)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((1013155)131719)(1617184)105)(01163)(012177)8)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)13)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)10172)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)((((1013155)131719)0118)11219)196)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)(((1013155)131719)(1013155)187)9)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((1013155)131719)(1617184)105)(012177)(1013155)8)(((1013155)131719)0118)(01163)(121738))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)(((1013155)131719)(1617184)105)(012177))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)((((1013155)131719)(1617184)105)(012177)(1013155)8)((((1013155)131719)0118)11219)11)(((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(121738)8)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(01163)(121738)4)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)256)142)(((((1013155)131719)(1617184)105)(012177)(1013155)8)(121738)1219)09)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((((1013155)131719)(1617184)105)(01163)(012177)8)((((1013155)131719)0118)11219)(121738)16)(((1013155)131719)(1013155)187)118)((((1013155)131719)0118)11219)(1013155)19)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(171869)') to (select from Species where name = 'Pteranodon')
create vertex Animal set birthday = DATE("2001-10-10 00:00:00"), color = 'black', name = 'Dragon__0', net_worth = 955.14, uuid = '432255ee-eceb-9505-dbc3-3e56c8a17945'
create vertex Animal set birthday = DATE("2013-02-22 00:00:00"), color = 'indigo', name = 'Dragon__1', net_worth = 158.97, uuid = '5672ebc7-606e-8502-002f-9cc4096bfaff'
create vertex Animal set birthday = DATE("2011-05-07 00:00:00"), color = 'indigo', name = 'Dragon__2', net_worth = 635.67, uuid = '061ae8d1-f212-cc6f-5409-88e79fed6060'
create vertex Animal set birthday = DATE("2016-06-25 00:00:00"), color = 'blue', name = 'Dragon__3', net_worth = 137.99, uuid = '3cf9d1fe-f75a-7e6f-2b86-3694541d1a81'
create vertex Animal set birthday = DATE("2006-01-02 00:00:00"), color = 'red', name = 'Dragon__4', net_worth = 925.55, uuid = '261cec19-fff8-3cec-2c05-b870cd34bcd7'
create vertex Animal set birthday = DATE("2007-01-13 00:00:00"), color = 'black', name = 'Dragon__5', net_worth = 913.69, uuid = 'c7405255-25cf-51c4-9c89-929692b035e0'
create vertex Animal set birthday = DATE("2004-05-04 00:00:00"), color = 'green', name = 'Dragon__6', net_worth = 566.1, uuid = 'ec2b5e21-3f7a-38e0-b611-8bd6553a773a'
create vertex Animal set birthday = DATE("2004-06-26 00:00:00"), color = 'indigo', name = 'Dragon__7', net_worth = 69.01, uuid = '61bafa39-789c-3c72-3ee2-9e686fa00319'
create vertex Animal set birthday = DATE("2006-10-27 00:00:00"), color = 'red', name = 'Dragon__8', net_worth = 106.66, uuid = '3cad275a-e072-caae-797c-27bfc7938520'
create vertex Animal set birthday = DATE("2006-05-17 00:00:00"), color = 'blue', name = 'Dragon__9', net_worth = 996.03, uuid = '9aabd22d-75ef-8aab-b693-f4ef1ad566c3'
create vertex Animal set birthday = DATE("2011-10-06 00:00:00"), color = 'orange', name = 'Dragon__10', net_worth = 957.33, uuid = 'a0ec3e5a-2487-8d19-586d-7f415e47c2a0'
create vertex Animal set birthday = DATE("2000-07-01 00:00:00"), color = 'yellow', name = 'Dragon__11', net_worth = 410.54, uuid = '531da6ac-956c-2129-b934-718f2d492ca2'
create vertex Animal set birthday = DATE("2011-02-13 00:00:00"), color = 'blue', name = 'Dragon__12', net_worth = 398.39, uuid = '58ccf9b4-354a-f1bd-ba56-12f7600aa45e'
create vertex Animal set birthday = DATE("2000-02-14 00:00:00"), color = 'blue', name = 'Dragon__13', net_worth = 899.85, uuid = '2728ec95-2b52-dab1-2367-ad9e8dcd7d64'
create vertex Animal set birthday = DATE("2018-07-05 00:00:00"), color = 'black', name = 'Dragon__14', net_worth = 376.13, uuid = '2887a3a9-e633-17c3-4303-42c7dcfbde0a'
create vertex Animal set birthday = DATE("2018-05-27 00:00:00"), color = 'indigo', name = 'Dragon__15', net_worth = 511.54, uuid = '4e245cf7-8e33-dcab-be68-4e2bbd637b3a'
create vertex Animal set birthday = DATE("2011-09-27 00:00:00"), color = 'red', name = 'Dragon__16', net_worth = 517.11, uuid = '276d7e19-f924-e06a-aef5-baef1903b45f'
create vertex Animal set birthday = DATE("2011-07-08 00:00:00"), color = 'magenta', name = 'Dragon__17', net_worth = 731.91, uuid = 'b2b4c281-a5b9-1ee8-c77f-0b62b26489f7'
create vertex Animal set birthday = DATE("2016-10-14 00:00:00"), color = 'red', name = 'Dragon__18', net_worth = 108.13, uuid = 'cb18d6a4-15db-4487-6038-03f32b2bcfda'
create vertex Animal set birthday = DATE("2015-03-05 00:00:00"), color = 'black', name = 'Dragon__19', net_worth = 551.63, uuid = 'b259a6a0-9591-9900-5e7c-faad73df770a'
create vertex Animal set birthday = DATE("2009-08-06 00:00:00"), color = 'indigo', name = 'Dragon__(1415179)', net_worth = 708.13, uuid = 'd97d2b38-a4a9-8266-d3d6-362b06999e1e'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1415179)') to (select from Animal where name = 'Dragon__14')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1415179)') to (select from Animal where name = 'Dragon__15')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1415179)') to (select from Animal where name = 'Dragon__17')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1415179)') to (select from Animal where name = 'Dragon__9')
create vertex Animal set birthday = DATE("2007-04-07 00:00:00"), color = 'magenta', name = 'Dragon__(0268)', net_worth = 364.32, uuid = '81eb88e5-d549-faad-44c8-fd001a0ff218'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(0268)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(0268)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(0268)') to (select from Animal where name = 'Dragon__6')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(0268)') to (select from Animal where name = 'Dragon__8')
create vertex Animal set birthday = DATE("2015-04-11 00:00:00"), color = 'yellow', name = 'Dragon__((1415179)10136)', net_worth = 94.14, uuid = '179d221d-8e5f-37fa-68f4-9b51f3fa8613'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1415179)10136)') to (select from Animal where name = 'Dragon__(1415179)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1415179)10136)') to (select from Animal where name = 'Dragon__10')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1415179)10136)') to (select from Animal where name = 'Dragon__13')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1415179)10136)') to (select from Animal where name = 'Dragon__6')
create vertex Animal set birthday = DATE("2006-02-01 00:00:00"), color = 'orange', name = 'Dragon__(113154)', net_worth = 226.65, uuid = '8f3e64f4-7914-0a61-ee65-afeb1b674518'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(113154)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(113154)') to (select from Animal where name = 'Dragon__13')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(113154)') to (select from Animal where name = 'Dragon__15')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(113154)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set birthday = DATE("2005-06-21 00:00:00"), color = 'red', name = 'Dragon__((1415179)1157)', net_worth = 963.57, uuid = 'ed3032ed-824c-6948-f474-b1a4f2684ee1'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1415179)1157)') to (select from Animal where name = 'Dragon__(1415179)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1415179)1157)') to (select from Animal where name = 'Dragon__11')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1415179)1157)') to (select from Animal where name = 'Dragon__5')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1415179)1157)') to (select from Animal where name = 'Dragon__7')
create vertex Animal set birthday = DATE("2002-05-25 00:00:00"), color = 'orange', name = 'Dragon__((0268)347)', net_worth = 228.64, uuid = '9cc753ad-6264-190f-486c-0adf5bf26ec8'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)347)') to (select from Animal where name = 'Dragon__(0268)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)347)') to (select from Animal where name = 'Dragon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)347)') to (select from Animal where name = 'Dragon__4')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)347)') to (select from Animal where name = 'Dragon__7')
create vertex Animal set birthday = DATE("2002-02-27 00:00:00"), color = 'indigo', name = 'Dragon__(161879)', net_worth = 743.32, uuid = '1af4321a-ddd3-e779-4879-996dfe38f4eb'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(161879)') to (select from Animal where name = 'Dragon__16')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(161879)') to (select from Animal where name = 'Dragon__18')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(161879)') to (select from Animal where name = 'Dragon__7')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(161879)') to (select from Animal where name = 'Dragon__9')
create vertex Animal set birthday = DATE("2018-07-18 00:00:00"), color = 'indigo', name = 'Dragon__(((0268)347)1869)', net_worth = 675.62, uuid = '8376ffa8-76fe-579f-6382-f3b5f9adf8c5'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)1869)') to (select from Animal where name = 'Dragon__((0268)347)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)1869)') to (select from Animal where name = 'Dragon__18')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)1869)') to (select from Animal where name = 'Dragon__6')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)1869)') to (select from Animal where name = 'Dragon__9')
create vertex Animal set birthday = DATE("2010-01-03 00:00:00"), color = 'indigo', name = 'Dragon__(1314198)', net_worth = 200.3, uuid = 'f7b37a86-d21d-bc09-3a35-7442f325f875'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1314198)') to (select from Animal where name = 'Dragon__13')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1314198)') to (select from Animal where name = 'Dragon__14')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1314198)') to (select from Animal where name = 'Dragon__19')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1314198)') to (select from Animal where name = 'Dragon__8')
create vertex Animal set birthday = DATE("2002-10-17 00:00:00"), color = 'magenta', name = 'Dragon__((113154)1039)', net_worth = 912.48, uuid = '0212585b-0b2f-8580-f3f0-53233bd5f8a2'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((113154)1039)') to (select from Animal where name = 'Dragon__(113154)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((113154)1039)') to (select from Animal where name = 'Dragon__10')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((113154)1039)') to (select from Animal where name = 'Dragon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((113154)1039)') to (select from Animal where name = 'Dragon__9')
create vertex Animal set birthday = DATE("2007-10-18 00:00:00"), color = 'yellow', name = 'Dragon__(((0268)347)13152)', net_worth = 269.31, uuid = 'ceb09220-7984-f33f-61c6-1ae46a594b07'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)13152)') to (select from Animal where name = 'Dragon__((0268)347)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)13152)') to (select from Animal where name = 'Dragon__13')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)13152)') to (select from Animal where name = 'Dragon__15')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)13152)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set birthday = DATE("2001-02-01 00:00:00"), color = 'green', name = 'Dragon__(((0268)347)(0268)(1415179)18)', net_worth = 141.89, uuid = '845c21e7-988d-0e4a-2266-a107a408001f'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)(0268)(1415179)18)') to (select from Animal where name = 'Dragon__((0268)347)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)(0268)(1415179)18)') to (select from Animal where name = 'Dragon__(0268)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)(0268)(1415179)18)') to (select from Animal where name = 'Dragon__(1415179)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)347)(0268)(1415179)18)') to (select from Animal where name = 'Dragon__18')
create vertex Animal set birthday = DATE("2008-05-12 00:00:00"), color = 'yellow', name = 'Dragon__((((0268)347)(0268)(1415179)18)((1415179)1157)46)', net_worth = 377.23, uuid = 'e4ad24e2-824d-9e96-1fe2-53b079801aaa'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)((1415179)1157)46)') to (select from Animal where name = 'Dragon__(((0268)347)(0268)(1415179)18)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)((1415179)1157)46)') to (select from Animal where name = 'Dragon__((1415179)1157)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)((1415179)1157)46)') to (select from Animal where name = 'Dragon__4')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)((1415179)1157)46)') to (select from Animal where name = 'Dragon__6')
create vertex Animal set birthday = DATE("2009-03-08 00:00:00"), color = 'green', name = 'Dragon__((((0268)347)1869)11187)', net_worth = 653.29, uuid = '6df2fc82-3956-fba9-7232-3dc9c67781b2'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)1869)11187)') to (select from Animal where name = 'Dragon__(((0268)347)1869)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)1869)11187)') to (select from Animal where name = 'Dragon__11')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)1869)11187)') to (select from Animal where name = 'Dragon__18')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)1869)11187)') to (select from Animal where name = 'Dragon__7')
create vertex Animal set birthday = DATE("2000-11-23 00:00:00"), color = 'blue', name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)', net_worth = 765.74, uuid = 'f239fbb0-1f6c-eec1-ac54-6740a182e35f'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)') to (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)((1415179)1157)46)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)') to (select from Animal where name = 'Dragon__(((0268)347)(0268)(1415179)18)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)') to (select from Animal where name = 'Dragon__(1415179)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)') to (select from Animal where name = 'Dragon__17')
create vertex Animal set birthday = DATE("2013-06-19 00:00:00"), color = 'blue', name = 'Dragon__((113154)14166)', net_worth = 928.8, uuid = '952b750d-9830-349d-d9ef-bb41b66b6b0b'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((113154)14166)') to (select from Animal where name = 'Dragon__(113154)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((113154)14166)') to (select from Animal where name = 'Dragon__14')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((113154)14166)') to (select from Animal where name = 'Dragon__16')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((113154)14166)') to (select from Animal where name = 'Dragon__6')
create vertex Animal set birthday = DATE("2008-09-07 00:00:00"), color = 'blue', name = 'Dragon__((0268)11117)', net_worth = 684.52, uuid = '0b2591c4-0021-b632-3246-b7d9bb296639'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)11117)') to (select from Animal where name = 'Dragon__(0268)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)11117)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)11117)') to (select from Animal where name = 'Dragon__11')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)11117)') to (select from Animal where name = 'Dragon__17')
create vertex Animal set birthday = DATE("2003-05-24 00:00:00"), color = 'yellow', name = 'Dragon__((((0268)347)(0268)(1415179)18)(113154)(1314198)15)', net_worth = 717.5, uuid = 'aedab7b5-e2aa-55a7-4951-03edfd05a5f5'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)(113154)(1314198)15)') to (select from Animal where name = 'Dragon__(((0268)347)(0268)(1415179)18)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)(113154)(1314198)15)') to (select from Animal where name = 'Dragon__(113154)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)(113154)(1314198)15)') to (select from Animal where name = 'Dragon__(1314198)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)(113154)(1314198)15)') to (select from Animal where name = 'Dragon__15')
create vertex Animal set birthday = DATE("2007-06-16 00:00:00"), color = 'indigo', name = 'Dragon__(((((0268)347)(0268)(1415179)18)(113154)(1314198)15)12142)', net_worth = 892.12, uuid = 'c06bad38-1d01-0478-c110-412c38431ed6'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)(113154)(1314198)15)12142)') to (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)(113154)(1314198)15)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)(113154)(1314198)15)12142)') to (select from Animal where name = 'Dragon__12')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)(113154)(1314198)15)12142)') to (select from Animal where name = 'Dragon__14')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)(113154)(1314198)15)12142)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set birthday = DATE("2012-12-19 00:00:00"), color = 'magenta', name = 'Dragon__(((((0268)347)1869)11187)(((0268)347)1869)08)', net_worth = 530.83, uuid = 'ca6cb87c-dfb8-7708-91d2-125a95e19cb6'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)(((0268)347)1869)08)') to (select from Animal where name = 'Dragon__((((0268)347)1869)11187)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)(((0268)347)1869)08)') to (select from Animal where name = 'Dragon__(((0268)347)1869)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)(((0268)347)1869)08)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)(((0268)347)1869)08)') to (select from Animal where name = 'Dragon__8')
create vertex Animal set birthday = DATE("2004-12-01 00:00:00"), color = 'orange', name = 'Dragon__(((0268)11117)(0268)122)', net_worth = 863.6, uuid = 'beb9c9e2-156e-3ae5-4fe4-b7355c29b6da'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)11117)(0268)122)') to (select from Animal where name = 'Dragon__((0268)11117)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)11117)(0268)122)') to (select from Animal where name = 'Dragon__(0268)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)11117)(0268)122)') to (select from Animal where name = 'Dragon__12')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((0268)11117)(0268)122)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set birthday = DATE("2014-12-07 00:00:00"), color = 'yellow', name = 'Dragon__(((1415179)1157)(0268)106)', net_worth = 590.23, uuid = 'fb2323e7-d6a2-c379-e0c6-a8a74748f7ea'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((1415179)1157)(0268)106)') to (select from Animal where name = 'Dragon__((1415179)1157)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((1415179)1157)(0268)106)') to (select from Animal where name = 'Dragon__(0268)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((1415179)1157)(0268)106)') to (select from Animal where name = 'Dragon__10')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((1415179)1157)(0268)106)') to (select from Animal where name = 'Dragon__6')
create vertex Animal set birthday = DATE("2002-04-18 00:00:00"), color = 'green', name = 'Dragon__((((((0268)347)1869)11187)(((0268)347)1869)08)((1415179)1157)113)', net_worth = 637.15, uuid = 'a11b26b0-0823-6adf-3f75-12c56e05724d'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)1869)11187)(((0268)347)1869)08)((1415179)1157)113)') to (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)(((0268)347)1869)08)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)1869)11187)(((0268)347)1869)08)((1415179)1157)113)') to (select from Animal where name = 'Dragon__((1415179)1157)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)1869)11187)(((0268)347)1869)08)((1415179)1157)113)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)1869)11187)(((0268)347)1869)08)((1415179)1157)113)') to (select from Animal where name = 'Dragon__13')
create vertex Animal set birthday = DATE("2018-02-16 00:00:00"), color = 'blue', name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)', net_worth = 955.3, uuid = '4202faf9-dceb-ef56-a31c-a36b059ebb2e'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)') to (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)((1415179)1157)46)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)') to (select from Animal where name = 'Dragon__((1415179)10136)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)') to (select from Animal where name = 'Dragon__(113154)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set birthday = DATE("2014-05-16 00:00:00"), color = 'magenta', name = 'Dragon__(((((0268)347)1869)11187)1134)', net_worth = 707.39, uuid = '7c3ad037-20d5-c16e-9611-39cfffbdfd47'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)1134)') to (select from Animal where name = 'Dragon__((((0268)347)1869)11187)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)1134)') to (select from Animal where name = 'Dragon__11')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)1134)') to (select from Animal where name = 'Dragon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)1134)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set birthday = DATE("2013-11-28 00:00:00"), color = 'blue', name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)(((((0268)347)1869)11187)1134)(((0268)347)(0268)(1415179)18)17)', net_worth = 547.27, uuid = '706146ff-becb-a4c8-b2c9-2c129bd91220'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)(((((0268)347)1869)11187)1134)(((0268)347)(0268)(1415179)18)17)') to (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)(((((0268)347)1869)11187)1134)(((0268)347)(0268)(1415179)18)17)') to (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)1134)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)(((((0268)347)1869)11187)1134)(((0268)347)(0268)(1415179)18)17)') to (select from Animal where name = 'Dragon__(((0268)347)(0268)(1415179)18)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)(((((0268)347)1869)11187)1134)(((0268)347)(0268)(1415179)18)17)') to (select from Animal where name = 'Dragon__17')
create vertex Animal set birthday = DATE("2015-04-20 00:00:00"), color = 'red', name = 'Dragon__((0268)1459)', net_worth = 950.13, uuid = 'c503ccb5-c6b4-195c-aa19-af268fa41d22'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)1459)') to (select from Animal where name = 'Dragon__(0268)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)1459)') to (select from Animal where name = 'Dragon__14')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)1459)') to (select from Animal where name = 'Dragon__5')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((0268)1459)') to (select from Animal where name = 'Dragon__9')
create vertex Animal set birthday = DATE("2010-05-03 00:00:00"), color = 'yellow', name = 'Dragon__((1314198)1135)', net_worth = 979.42, uuid = '72f78920-dd75-16f5-58aa-03838dff06d2'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1314198)1135)') to (select from Animal where name = 'Dragon__(1314198)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1314198)1135)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1314198)1135)') to (select from Animal where name = 'Dragon__13')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((1314198)1135)') to (select from Animal where name = 'Dragon__5')
create vertex Animal set birthday = DATE("2012-04-16 00:00:00"), color = 'orange', name = 'Dragon__(((1314198)1135)(1415179)118)', net_worth = 979.23, uuid = '44f06c4e-d87d-3afc-a370-5e8a021ac45b'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((1314198)1135)(1415179)118)') to (select from Animal where name = 'Dragon__((1314198)1135)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((1314198)1135)(1415179)118)') to (select from Animal where name = 'Dragon__(1415179)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((1314198)1135)(1415179)118)') to (select from Animal where name = 'Dragon__11')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((1314198)1135)(1415179)118)') to (select from Animal where name = 'Dragon__8')
create vertex Animal set birthday = DATE("2005-10-14 00:00:00"), color = 'green', name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)((((0268)347)1869)11187)(((1415179)1157)(0268)106)2)', net_worth = 448.81, uuid = '951a0518-47e7-7e2b-6b29-1a13637c3644'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)((((0268)347)1869)11187)(((1415179)1157)(0268)106)2)') to (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)((((0268)347)1869)11187)(((1415179)1157)(0268)106)2)') to (select from Animal where name = 'Dragon__((((0268)347)1869)11187)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)((((0268)347)1869)11187)(((1415179)1157)(0268)106)2)') to (select from Animal where name = 'Dragon__(((1415179)1157)(0268)106)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)((((0268)347)1869)11187)(((1415179)1157)(0268)106)2)') to (select from Animal where name = 'Dragon__2')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__0') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__1') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__2') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__3') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__4') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__5') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__6') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__7') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__8') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__9') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__10') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__11') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__12') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__13') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__14') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__15') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__16') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__17') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__18') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__19') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(1415179)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(0268)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((1415179)10136)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(113154)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((1415179)1157)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((0268)347)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(161879)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((0268)347)1869)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(1314198)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((113154)1039)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((0268)347)13152)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((0268)347)(0268)(1415179)18)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)((1415179)1157)46)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((0268)347)1869)11187)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((113154)14166)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((0268)11117)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((0268)347)(0268)(1415179)18)(113154)(1314198)15)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)(113154)(1314198)15)12142)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)(((0268)347)1869)08)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((0268)11117)(0268)122)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((1415179)1157)(0268)106)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((((0268)347)1869)11187)(((0268)347)1869)08)((1415179)1157)113)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((0268)347)1869)11187)1134)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)((1415179)10136)(113154)2)(((((0268)347)1869)11187)1134)(((0268)347)(0268)(1415179)18)17)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((0268)1459)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((1314198)1135)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((1314198)1135)(1415179)118)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((((0268)347)(0268)(1415179)18)((1415179)1157)46)(((0268)347)(0268)(1415179)18)(1415179)17)((((0268)347)1869)11187)(((1415179)1157)(0268)106)2)') to (select from Species where name = 'Dragon')
create vertex Animal set birthday = DATE("2004-04-24 00:00:00"), color = 'yellow', name = 'Hippogriff__0', net_worth = 904.14, uuid = 'ced4dd7c-b4ca-0142-3b23-9fd80d20f686'
create vertex Animal set birthday = DATE("2013-12-05 00:00:00"), color = 'yellow', name = 'Hippogriff__1', net_worth = 886.91, uuid = '44bfc434-481c-e3f9-7ff5-101d3f1cd31b'
create vertex Animal set birthday = DATE("2005-02-16 00:00:00"), color = 'blue', name = 'Hippogriff__2', net_worth = 250.39, uuid = '3fccb2c1-33d4-a096-5b78-01ea86343347'
create vertex Animal set birthday = DATE("2003-07-06 00:00:00"), color = 'red', name = 'Hippogriff__3', net_worth = 533.21, uuid = 'd8efb5c9-e7a2-d2d0-ca3c-405075fc1b10'
create vertex Animal set birthday = DATE("2017-11-01 00:00:00"), color = 'magenta', name = 'Hippogriff__4', net_worth = 746.87, uuid = 'db160641-2074-17e7-1a60-8f0d7e4132ad'
create vertex Animal set birthday = DATE("2004-01-22 00:00:00"), color = 'black', name = 'Hippogriff__5', net_worth = 586.03, uuid = 'f9154865-6996-7b5c-fc14-5cfe469a1289'
create vertex Animal set birthday = DATE("2004-09-26 00:00:00"), color = 'black', name = 'Hippogriff__6', net_worth = 661.5, uuid = 'cf21ae6a-82e2-f424-0dbc-ad25daace3a3'
create vertex Animal set birthday = DATE("2002-09-11 00:00:00"), color = 'red', name = 'Hippogriff__7', net_worth = 963.68, uuid = '827acd0d-e150-93b0-a07a-eb89998df20b'
create vertex Animal set birthday = DATE("2015-12-24 00:00:00"), color = 'red', name = 'Hippogriff__8', net_worth = 608.56, uuid = '40e5e8fa-b033-5368-a443-a7378072b635'
create vertex Animal set birthday = DATE("2005-10-26 00:00:00"), color = 'yellow', name = 'Hippogriff__9', net_worth = 349.0, uuid = '70bc3ec1-4d29-d77a-7939-10e656e16c2b'
create vertex Animal set birthday = DATE("2014-11-06 00:00:00"), color = 'black', name = 'Hippogriff__10', net_worth = 216.38, uuid = '80635ef2-e534-28bb-b20e-d71966b9b21b'
create vertex Animal set birthday = DATE("2008-08-02 00:00:00"), color = 'yellow', name = 'Hippogriff__11', net_worth = 729.5, uuid = '577aa515-eac5-03ff-79d1-b233a5c07ecf'
create vertex Animal set birthday = DATE("2011-11-28 00:00:00"), color = 'red', name = 'Hippogriff__12', net_worth = 943.27, uuid = 'b0fde8c9-7575-117c-41ca-37f5f7de1a61'
create vertex Animal set birthday = DATE("2018-01-18 00:00:00"), color = 'red', name = 'Hippogriff__13', net_worth = 928.45, uuid = 'cfd09276-9c01-7e5d-5c41-dfb5a94a29d3'
create vertex Animal set birthday = DATE("2000-07-10 00:00:00"), color = 'orange', name = 'Hippogriff__14', net_worth = 208.61, uuid = 'b311d9c4-1d86-fd12-c835-9b916e935faf'
create vertex Animal set birthday = DATE("2009-02-17 00:00:00"), color = 'orange', name = 'Hippogriff__15', net_worth = 407.68, uuid = '51bb91c1-3262-0328-624a-adaeebbcf1f6'
create vertex Animal set birthday = DATE("2001-11-01 00:00:00"), color = 'indigo', name = 'Hippogriff__16', net_worth = 647.64, uuid = 'dc7843b3-e919-b5aa-f0c9-9beaa0a1f43f'
create vertex Animal set birthday = DATE("2012-08-24 00:00:00"), color = 'green', name = 'Hippogriff__17', net_worth = 189.06, uuid = '15d0db43-80a1-7176-22b3-4047ee4b0498'
create vertex Animal set birthday = DATE("2012-04-28 00:00:00"), color = 'indigo', name = 'Hippogriff__18', net_worth = 608.96, uuid = '235f6be1-f8b5-5fb5-56d1-079c0fbc0318'
create vertex Animal set birthday = DATE("2014-11-15 00:00:00"), color = 'yellow', name = 'Hippogriff__19', net_worth = 558.92, uuid = 'a55dc720-e554-0022-4502-d7f854a1396c'
create vertex Animal set birthday = DATE("2002-03-27 00:00:00"), color = 'magenta', name = 'Hippogriff__(1012198)', net_worth = 294.2, uuid = 'c99d5f9e-c634-effd-f02d-d043d01acef6'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(1012198)') to (select from Animal where name = 'Hippogriff__10')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(1012198)') to (select from Animal where name = 'Hippogriff__12')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(1012198)') to (select from Animal where name = 'Hippogriff__19')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(1012198)') to (select from Animal where name = 'Hippogriff__8')
create vertex Animal set birthday = DATE("2018-12-25 00:00:00"), color = 'magenta', name = 'Hippogriff__(131548)', net_worth = 408.1, uuid = '02115503-1321-8ef7-cd43-cfeb89386b90'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(131548)') to (select from Animal where name = 'Hippogriff__13')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(131548)') to (select from Animal where name = 'Hippogriff__15')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(131548)') to (select from Animal where name = 'Hippogriff__4')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(131548)') to (select from Animal where name = 'Hippogriff__8')
create vertex Animal set birthday = DATE("2017-11-02 00:00:00"), color = 'blue', name = 'Hippogriff__(0101317)', net_worth = 782.01, uuid = '39a11816-fc7a-ad95-bfdf-8a9e9446d493'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(0101317)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(0101317)') to (select from Animal where name = 'Hippogriff__10')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(0101317)') to (select from Animal where name = 'Hippogriff__13')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(0101317)') to (select from Animal where name = 'Hippogriff__17')
create vertex Animal set birthday = DATE("2004-05-01 00:00:00"), color = 'green', name = 'Hippogriff__(16369)', net_worth = 636.35, uuid = '9398dbd6-16db-36e4-d4ae-34862b194984'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(16369)') to (select from Animal where name = 'Hippogriff__16')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(16369)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(16369)') to (select from Animal where name = 'Hippogriff__6')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(16369)') to (select from Animal where name = 'Hippogriff__9')
create vertex Animal set birthday = DATE("2006-10-03 00:00:00"), color = 'orange', name = 'Hippogriff__(01186)', net_worth = 207.1, uuid = 'd20eab0e-bd87-44d8-01a5-0ef1550c54d4'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(01186)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(01186)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(01186)') to (select from Animal where name = 'Hippogriff__18')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(01186)') to (select from Animal where name = 'Hippogriff__6')
create vertex Animal set birthday = DATE("2002-05-25 00:00:00"), color = 'indigo', name = 'Hippogriff__(1113172)', net_worth = 313.39, uuid = '84c65027-6d05-f2e3-8d20-dbea7ae398cf'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(1113172)') to (select from Animal where name = 'Hippogriff__11')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(1113172)') to (select from Animal where name = 'Hippogriff__13')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(1113172)') to (select from Animal where name = 'Hippogriff__17')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(1113172)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set birthday = DATE("2006-08-21 00:00:00"), color = 'magenta', name = 'Hippogriff__((0101317)0163)', net_worth = 402.12, uuid = '863c6992-116f-ebe7-aa0c-c3271daa42fc'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)0163)') to (select from Animal where name = 'Hippogriff__(0101317)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)0163)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)0163)') to (select from Animal where name = 'Hippogriff__16')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)0163)') to (select from Animal where name = 'Hippogriff__3')
create vertex Animal set birthday = DATE("2014-05-23 00:00:00"), color = 'black', name = 'Hippogriff__((0101317)(01186)(1012198)12)', net_worth = 6.89, uuid = '808ea422-c6f6-d1d5-3b77-ba5f586076e3'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)(01186)(1012198)12)') to (select from Animal where name = 'Hippogriff__(0101317)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)(01186)(1012198)12)') to (select from Animal where name = 'Hippogriff__(01186)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)(01186)(1012198)12)') to (select from Animal where name = 'Hippogriff__(1012198)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)(01186)(1012198)12)') to (select from Animal where name = 'Hippogriff__12')
create vertex Animal set birthday = DATE("2006-05-14 00:00:00"), color = 'red', name = 'Hippogriff__((131548)101316)', net_worth = 755.97, uuid = '91e54b3a-0a4e-6eb7-f97b-8d621c9527d0'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((131548)101316)') to (select from Animal where name = 'Hippogriff__(131548)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((131548)101316)') to (select from Animal where name = 'Hippogriff__10')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((131548)101316)') to (select from Animal where name = 'Hippogriff__13')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((131548)101316)') to (select from Animal where name = 'Hippogriff__16')
create vertex Animal set birthday = DATE("2018-08-28 00:00:00"), color = 'black', name = 'Hippogriff__((0101317)(1113172)(16369)12)', net_worth = 173.4, uuid = 'e9e4f06c-3689-0df9-7bd3-7c4b948c52c8'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)(1113172)(16369)12)') to (select from Animal where name = 'Hippogriff__(0101317)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)(1113172)(16369)12)') to (select from Animal where name = 'Hippogriff__(1113172)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)(1113172)(16369)12)') to (select from Animal where name = 'Hippogriff__(16369)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((0101317)(1113172)(16369)12)') to (select from Animal where name = 'Hippogriff__12')
create vertex Animal set birthday = DATE("2007-03-08 00:00:00"), color = 'blue', name = 'Hippogriff__(((0101317)(1113172)(16369)12)(1113172)1317)', net_worth = 241.79, uuid = '6df5e2aa-832c-b6a7-24e2-e13aa0e5bd8c'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(1113172)1317)') to (select from Animal where name = 'Hippogriff__((0101317)(1113172)(16369)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(1113172)1317)') to (select from Animal where name = 'Hippogriff__(1113172)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(1113172)1317)') to (select from Animal where name = 'Hippogriff__13')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(1113172)1317)') to (select from Animal where name = 'Hippogriff__17')
create vertex Animal set birthday = DATE("2002-10-16 00:00:00"), color = 'green', name = 'Hippogriff__(((131548)101316)111418)', net_worth = 536.52, uuid = 'a2157489-9fbd-4b9f-5675-6682996d6642'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((131548)101316)111418)') to (select from Animal where name = 'Hippogriff__((131548)101316)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((131548)101316)111418)') to (select from Animal where name = 'Hippogriff__11')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((131548)101316)111418)') to (select from Animal where name = 'Hippogriff__14')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((131548)101316)111418)') to (select from Animal where name = 'Hippogriff__18')
create vertex Animal set birthday = DATE("2003-11-09 00:00:00"), color = 'green', name = 'Hippogriff__(((0101317)(1113172)(16369)12)(0101317)153)', net_worth = 20.73, uuid = '4b32bc86-35d5-870d-e79d-1be27f29e86c'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(0101317)153)') to (select from Animal where name = 'Hippogriff__((0101317)(1113172)(16369)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(0101317)153)') to (select from Animal where name = 'Hippogriff__(0101317)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(0101317)153)') to (select from Animal where name = 'Hippogriff__15')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(0101317)153)') to (select from Animal where name = 'Hippogriff__3')
create vertex Animal set birthday = DATE("2002-01-28 00:00:00"), color = 'orange', name = 'Hippogriff__(((0101317)(01186)(1012198)12)1568)', net_worth = 762.9, uuid = '62a77dc7-b273-38fc-dfa6-9923b334ebbc'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(01186)(1012198)12)1568)') to (select from Animal where name = 'Hippogriff__((0101317)(01186)(1012198)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(01186)(1012198)12)1568)') to (select from Animal where name = 'Hippogriff__15')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(01186)(1012198)12)1568)') to (select from Animal where name = 'Hippogriff__6')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((0101317)(01186)(1012198)12)1568)') to (select from Animal where name = 'Hippogriff__8')
create vertex Animal set birthday = DATE("2001-01-28 00:00:00"), color = 'indigo', name = 'Hippogriff__((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)', net_worth = 628.14, uuid = '5ffe6c11-7b51-aca6-ea87-60aada4dda76'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)') to (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(1113172)1317)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)') to (select from Animal where name = 'Hippogriff__(1012198)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)') to (select from Animal where name = 'Hippogriff__10')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)') to (select from Animal where name = 'Hippogriff__18')
create vertex Animal set birthday = DATE("2011-05-04 00:00:00"), color = 'red', name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(16369)017)', net_worth = 892.09, uuid = 'bae8d99f-eee0-5fb7-d2d6-840d18711121'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(16369)017)') to (select from Animal where name = 'Hippogriff__(((0101317)(01186)(1012198)12)1568)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(16369)017)') to (select from Animal where name = 'Hippogriff__(16369)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(16369)017)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(16369)017)') to (select from Animal where name = 'Hippogriff__17')
create vertex Animal set birthday = DATE("2011-03-04 00:00:00"), color = 'blue', name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)', net_worth = 843.41, uuid = 'c9d9db15-7efa-4e99-4204-5f8c3a72a669'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)') to (select from Animal where name = 'Hippogriff__(((0101317)(01186)(1012198)12)1568)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)') to (select from Animal where name = 'Hippogriff__(((131548)101316)111418)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)') to (select from Animal where name = 'Hippogriff__19')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)') to (select from Animal where name = 'Hippogriff__7')
create vertex Animal set birthday = DATE("2013-08-20 00:00:00"), color = 'red', name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)', net_worth = 279.26, uuid = 'bdc5a588-d0ab-9ea4-c15f-47ca204e6817'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)') to (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(16369)017)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)') to (select from Animal where name = 'Hippogriff__(131548)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)') to (select from Animal where name = 'Hippogriff__15')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)') to (select from Animal where name = 'Hippogriff__7')
create vertex Animal set birthday = DATE("2009-01-09 00:00:00"), color = 'blue', name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)', net_worth = 219.98, uuid = '00dd28b3-acea-35a3-93d5-e33bbd869312'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)') to (select from Animal where name = 'Hippogriff__(((0101317)(01186)(1012198)12)1568)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)') to (select from Animal where name = 'Hippogriff__(((131548)101316)111418)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)') to (select from Animal where name = 'Hippogriff__(0101317)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)') to (select from Animal where name = 'Hippogriff__8')
create vertex Animal set birthday = DATE("2010-12-07 00:00:00"), color = 'green', name = 'Hippogriff__(((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)1269)', net_worth = 552.37, uuid = '598c8a5c-19b2-b595-3051-9f6ab51e3a7b'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)1269)') to (select from Animal where name = 'Hippogriff__((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)1269)') to (select from Animal where name = 'Hippogriff__12')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)1269)') to (select from Animal where name = 'Hippogriff__6')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)1269)') to (select from Animal where name = 'Hippogriff__9')
create vertex Animal set birthday = DATE("2017-07-22 00:00:00"), color = 'yellow', name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)', net_worth = 177.64, uuid = '75f80092-ea4f-44cf-eafd-080bdec8633f'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)') to (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)') to (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)') to (select from Animal where name = 'Hippogriff__15')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set birthday = DATE("2005-06-22 00:00:00"), color = 'black', name = 'Hippogriff__((1012198)13182)', net_worth = 988.6, uuid = '91b92f8b-8a84-9529-b662-f7edb5b85fb3'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((1012198)13182)') to (select from Animal where name = 'Hippogriff__(1012198)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((1012198)13182)') to (select from Animal where name = 'Hippogriff__13')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((1012198)13182)') to (select from Animal where name = 'Hippogriff__18')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((1012198)13182)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set birthday = DATE("2007-01-24 00:00:00"), color = 'red', name = 'Hippogriff__(((1012198)13182)1648)', net_worth = 212.61, uuid = '3ba68577-3396-4543-0843-9ba12afd65c3'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((1012198)13182)1648)') to (select from Animal where name = 'Hippogriff__((1012198)13182)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((1012198)13182)1648)') to (select from Animal where name = 'Hippogriff__16')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((1012198)13182)1648)') to (select from Animal where name = 'Hippogriff__4')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((1012198)13182)1648)') to (select from Animal where name = 'Hippogriff__8')
create vertex Animal set birthday = DATE("2017-09-14 00:00:00"), color = 'orange', name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)', net_worth = 630.3, uuid = '99cb37c7-6e7f-bad2-9efb-00b7a397b217'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)') to (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)') to (select from Animal where name = 'Hippogriff__(0101317)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)') to (select from Animal where name = 'Hippogriff__(131548)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)') to (select from Animal where name = 'Hippogriff__8')
create vertex Animal set birthday = DATE("2004-01-07 00:00:00"), color = 'magenta', name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)(((0101317)(1113172)(16369)12)(1113172)1317)15)', net_worth = 471.83, uuid = '70c742d0-3295-ba69-f987-3b5e08dfc975'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)(((0101317)(1113172)(16369)12)(1113172)1317)15)') to (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)(((0101317)(1113172)(16369)12)(1113172)1317)15)') to (select from Animal where name = 'Hippogriff__((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)(((0101317)(1113172)(16369)12)(1113172)1317)15)') to (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(1113172)1317)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)(((0101317)(1113172)(16369)12)(1113172)1317)15)') to (select from Animal where name = 'Hippogriff__15')
create vertex Animal set birthday = DATE("2009-02-24 00:00:00"), color = 'orange', name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)((0101317)(01186)(1012198)12)1314)', net_worth = 370.15, uuid = 'e1289e96-ebe3-387b-68cb-aa9e22d72fab'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)((0101317)(01186)(1012198)12)1314)') to (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)((0101317)(01186)(1012198)12)1314)') to (select from Animal where name = 'Hippogriff__((0101317)(01186)(1012198)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)((0101317)(01186)(1012198)12)1314)') to (select from Animal where name = 'Hippogriff__13')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)((0101317)(01186)(1012198)12)1314)') to (select from Animal where name = 'Hippogriff__14')
create vertex Animal set birthday = DATE("2009-06-21 00:00:00"), color = 'indigo', name = 'Hippogriff__((((131548)101316)111418)1435)', net_worth = 378.84, uuid = '310dfbf4-d741-8ae8-cfa7-1765e757155d'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)1435)') to (select from Animal where name = 'Hippogriff__(((131548)101316)111418)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)1435)') to (select from Animal where name = 'Hippogriff__14')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)1435)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)1435)') to (select from Animal where name = 'Hippogriff__5')
create vertex Animal set birthday = DATE("2011-11-13 00:00:00"), color = 'green', name = 'Hippogriff__((((131548)101316)111418)(1012198)113)', net_worth = 741.06, uuid = '9a347cda-d481-4f7f-3022-b8f186d6c424'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)(1012198)113)') to (select from Animal where name = 'Hippogriff__(((131548)101316)111418)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)(1012198)113)') to (select from Animal where name = 'Hippogriff__(1012198)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)(1012198)113)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)(1012198)113)') to (select from Animal where name = 'Hippogriff__13')
create vertex Animal set birthday = DATE("2008-02-11 00:00:00"), color = 'green', name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)(131548)57)', net_worth = 926.72, uuid = 'd6cadf41-2df1-fe3f-efd9-373e6c7f40f8'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)(131548)57)') to (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)(131548)57)') to (select from Animal where name = 'Hippogriff__(131548)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)(131548)57)') to (select from Animal where name = 'Hippogriff__5')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)(131548)57)') to (select from Animal where name = 'Hippogriff__7')
create vertex Animal set birthday = DATE("2014-04-16 00:00:00"), color = 'orange', name = 'Hippogriff__((((1012198)13182)1648)1224)', net_worth = 376.36, uuid = '16159755-96df-541f-cdd5-92a0aeff988b'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((1012198)13182)1648)1224)') to (select from Animal where name = 'Hippogriff__(((1012198)13182)1648)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((1012198)13182)1648)1224)') to (select from Animal where name = 'Hippogriff__12')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((1012198)13182)1648)1224)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((1012198)13182)1648)1224)') to (select from Animal where name = 'Hippogriff__4')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__0') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__1') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__2') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__3') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__4') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__5') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__6') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__7') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__8') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__9') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__10') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__11') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__12') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__13') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__14') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__15') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__16') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__17') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__18') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__19') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(1012198)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(131548)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(0101317)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(16369)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(01186)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(1113172)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((0101317)0163)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((0101317)(01186)(1012198)12)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((131548)101316)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((0101317)(1113172)(16369)12)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(1113172)1317)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((131548)101316)111418)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((0101317)(1113172)(16369)12)(0101317)153)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((0101317)(01186)(1012198)12)1568)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(16369)017)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)1269)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((1012198)13182)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((1012198)13182)1648)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)(0101317)(131548)8)((((0101317)(1113172)(16369)12)(1113172)1317)(1012198)1018)(((0101317)(1113172)(16369)12)(1113172)1317)15)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(16369)017)(131548)157)((0101317)(01186)(1012198)12)1314)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)1435)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((131548)101316)111418)(1012198)113)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)(0101317)8)((((0101317)(01186)(1012198)12)1568)(((131548)101316)111418)197)152)(131548)57)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((1012198)13182)1648)1224)') to (select from Species where name = 'Hippogriff')
