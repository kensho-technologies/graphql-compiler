# Auto-generated output from `generate_test_sql/__init__.py`.
# Do not edit directly!
# Generated on 2018-07-17T16:32:43.635844 from compiler version 1.7.0.

create vertex Species set limbs = 9, name = 'Nazgul', uuid = '0a5d2f34-6baa-9455-e3e7-0682c2094cac'
create vertex Species set limbs = 10, name = 'Pteranodon', uuid = '81332876-37eb-dcd9-e87a-1613e443df78'
create vertex Species set limbs = 4, name = 'Dragon', uuid = 'cca5a5a1-9e4d-6e3c-1846-d424c17c6279'
create vertex Species set limbs = 10, name = 'Hippogriff', uuid = 'af19922a-d9b8-a714-e61a-441c12e0c8b2'
create vertex Animal set birthday = DATE("2012-03-16 00:00:00"), color = 'green', name = 'Nazgul__0', net_worth = 442.69, uuid = '5a921187-19c7-8df4-8f4f-f31e78de5857'
create vertex Animal set birthday = DATE("2006-09-20 00:00:00"), color = 'orange', name = 'Nazgul__1', net_worth = 62.98, uuid = '9ca5499d-004a-e545-a011-6be5ab0c1681'
create vertex Animal set birthday = DATE("2018-11-28 00:00:00"), color = 'red', name = 'Nazgul__2', net_worth = 489.28, uuid = '8b0163c1-cd9d-2b7d-247a-8333f7b0b7d2'
create vertex Animal set birthday = DATE("2015-07-27 00:00:00"), color = 'magenta', name = 'Nazgul__3', net_worth = 603.18, uuid = 'b4e1357d-4a84-eb03-8d1f-d9b74d2b9deb'
create vertex Animal set birthday = DATE("2003-03-18 00:00:00"), color = 'green', name = 'Nazgul__4', net_worth = 656.65, uuid = '935ddd72-5129-fb7c-6288-e1a5cc457821'
create vertex Animal set birthday = DATE("2017-08-27 00:00:00"), color = 'orange', name = 'Nazgul__(024)', net_worth = 579.69, uuid = 'cfc6e625-8594-0927-468f-f53d864a7a50'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(024)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(024)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(024)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set birthday = DATE("2002-08-10 00:00:00"), color = 'green', name = 'Nazgul__(234)', net_worth = 190.37, uuid = '5b7c709a-cb17-5a5a-fb82-860deabca8d0'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(234)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(234)') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(234)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set birthday = DATE("2001-02-20 00:00:00"), color = 'orange', name = 'Nazgul__(013)', net_worth = 45.23, uuid = '552116dd-2ba4-b180-cb69-ca385f3f5638'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(013)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(013)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(013)') to (select from Animal where name = 'Nazgul__3')
create vertex Animal set birthday = DATE("2007-12-02 00:00:00"), color = 'yellow', name = 'Nazgul__((234)34)', net_worth = 21.63, uuid = '9371a71f-d480-865f-9b38-fe803042e325'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)34)') to (select from Animal where name = 'Nazgul__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)34)') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)34)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set birthday = DATE("2005-06-02 00:00:00"), color = 'red', name = 'Nazgul__(((234)34)01)', net_worth = 467.13, uuid = '11ebcd49-428a-1c22-d5fd-b76a19fbeb1d'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)34)01)') to (select from Animal where name = 'Nazgul__((234)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)34)01)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)34)01)') to (select from Animal where name = 'Nazgul__1')
create vertex Animal set birthday = DATE("2017-03-19 00:00:00"), color = 'orange', name = 'Nazgul__((024)(234)3)', net_worth = 966.54, uuid = 'bb4a06cb-e786-ab37-5bca-47be429817c5'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((024)(234)3)') to (select from Animal where name = 'Nazgul__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((024)(234)3)') to (select from Animal where name = 'Nazgul__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((024)(234)3)') to (select from Animal where name = 'Nazgul__3')
create vertex Animal set birthday = DATE("2007-07-15 00:00:00"), color = 'yellow', name = 'Nazgul__((013)(234)0)', net_worth = 311.44, uuid = '2cc0f859-aa65-24ab-713b-7e05ebe21368'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((013)(234)0)') to (select from Animal where name = 'Nazgul__(013)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((013)(234)0)') to (select from Animal where name = 'Nazgul__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((013)(234)0)') to (select from Animal where name = 'Nazgul__0')
create vertex Animal set birthday = DATE("2007-08-01 00:00:00"), color = 'yellow', name = 'Nazgul__((((234)34)01)24)', net_worth = 192.3, uuid = 'b732d46f-21e1-5094-9efe-e464da90f534'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((234)34)01)24)') to (select from Animal where name = 'Nazgul__(((234)34)01)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((234)34)01)24)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((234)34)01)24)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set birthday = DATE("2002-07-14 00:00:00"), color = 'green', name = 'Nazgul__((013)24)', net_worth = 561.4, uuid = '720299e3-2a69-acc7-0bf9-c0efb5816b74'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((013)24)') to (select from Animal where name = 'Nazgul__(013)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((013)24)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((013)24)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set birthday = DATE("2018-08-03 00:00:00"), color = 'blue', name = 'Nazgul__(((013)(234)0)((024)(234)3)(024))', net_worth = 725.55, uuid = 'cffa6cdd-f963-a7ef-e001-11e5d29dc5df'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((013)(234)0)((024)(234)3)(024))') to (select from Animal where name = 'Nazgul__((013)(234)0)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((013)(234)0)((024)(234)3)(024))') to (select from Animal where name = 'Nazgul__((024)(234)3)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((013)(234)0)((024)(234)3)(024))') to (select from Animal where name = 'Nazgul__(024)')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__0') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__1') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__2') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__3') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__4') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(024)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(234)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(013)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((234)34)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((234)34)01)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((024)(234)3)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((013)(234)0)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((234)34)01)24)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((013)24)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((013)(234)0)((024)(234)3)(024))') to (select from Species where name = 'Nazgul')
create vertex Animal set birthday = DATE("2000-10-15 00:00:00"), color = 'black', name = 'Pteranodon__0', net_worth = 97.78, uuid = '36a98d74-00de-59f5-50f0-fc2b6ae04d52'
create vertex Animal set birthday = DATE("2016-05-03 00:00:00"), color = 'red', name = 'Pteranodon__1', net_worth = 274.71, uuid = 'fa7ff8bf-b044-284a-47ac-f2f64d6b234f'
create vertex Animal set birthday = DATE("2012-07-27 00:00:00"), color = 'red', name = 'Pteranodon__2', net_worth = 938.43, uuid = '04c14982-d9ea-d926-4745-dd9e27896389'
create vertex Animal set birthday = DATE("2017-08-11 00:00:00"), color = 'black', name = 'Pteranodon__3', net_worth = 537.92, uuid = 'a7c5cb87-9b8b-71a1-b38a-05fbf61164ce'
create vertex Animal set birthday = DATE("2005-05-11 00:00:00"), color = 'blue', name = 'Pteranodon__4', net_worth = 93.7, uuid = '4a814d53-964d-db77-6025-f0ae35354579'
create vertex Animal set birthday = DATE("2010-04-14 00:00:00"), color = 'yellow', name = 'Pteranodon__(034)', net_worth = 239.7, uuid = '4a1eb1b7-955d-0e77-fb5e-b8662640211e'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(034)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(034)') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(034)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set birthday = DATE("2002-07-14 00:00:00"), color = 'green', name = 'Pteranodon__((034)02)', net_worth = 337.08, uuid = 'd5e73e3f-6736-17d9-4d7b-d307122411e6'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((034)02)') to (select from Animal where name = 'Pteranodon__(034)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((034)02)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((034)02)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set birthday = DATE("2013-11-26 00:00:00"), color = 'green', name = 'Pteranodon__((034)04)', net_worth = 626.74, uuid = '6d316b4a-7f6b-8793-b318-ad4c1db2b452'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((034)04)') to (select from Animal where name = 'Pteranodon__(034)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((034)04)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((034)04)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set birthday = DATE("2009-06-14 00:00:00"), color = 'yellow', name = 'Pteranodon__(((034)02)((034)04)3)', net_worth = 584.88, uuid = '0202861c-6283-0869-0fa7-ee0538974df5'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((034)02)((034)04)3)') to (select from Animal where name = 'Pteranodon__((034)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((034)02)((034)04)3)') to (select from Animal where name = 'Pteranodon__((034)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((034)02)((034)04)3)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set birthday = DATE("2016-09-26 00:00:00"), color = 'red', name = 'Pteranodon__(((034)02)23)', net_worth = 451.61, uuid = '5bc7fdeb-3123-4efe-6e64-80432aa50f4e'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((034)02)23)') to (select from Animal where name = 'Pteranodon__((034)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((034)02)23)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((034)02)23)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set birthday = DATE("2007-07-05 00:00:00"), color = 'blue', name = 'Pteranodon__(((034)02)13)', net_worth = 988.68, uuid = '25777cf0-9f98-2188-3744-da64cc249558'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((034)02)13)') to (select from Animal where name = 'Pteranodon__((034)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((034)02)13)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((034)02)13)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set birthday = DATE("2016-11-28 00:00:00"), color = 'black', name = 'Pteranodon__((((034)02)13)13)', net_worth = 635.06, uuid = '856f3d95-e0ae-1a1b-6c59-6216ae0fdbc8'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((034)02)13)13)') to (select from Animal where name = 'Pteranodon__(((034)02)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((034)02)13)13)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((034)02)13)13)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set birthday = DATE("2016-08-05 00:00:00"), color = 'magenta', name = 'Pteranodon__((((034)02)13)(((034)02)23)(034))', net_worth = 379.0, uuid = '52631db9-d170-34ce-5179-7350e6256403'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((034)02)13)(((034)02)23)(034))') to (select from Animal where name = 'Pteranodon__(((034)02)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((034)02)13)(((034)02)23)(034))') to (select from Animal where name = 'Pteranodon__(((034)02)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((034)02)13)(((034)02)23)(034))') to (select from Animal where name = 'Pteranodon__(034)')
create vertex Animal set birthday = DATE("2014-06-25 00:00:00"), color = 'green', name = 'Pteranodon__((((034)02)((034)04)3)(034)3)', net_worth = 800.64, uuid = '21681081-399f-8a8f-10fc-9eee0a1727f7'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((034)02)((034)04)3)(034)3)') to (select from Animal where name = 'Pteranodon__(((034)02)((034)04)3)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((034)02)((034)04)3)(034)3)') to (select from Animal where name = 'Pteranodon__(034)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((034)02)((034)04)3)(034)3)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set birthday = DATE("2012-10-22 00:00:00"), color = 'magenta', name = 'Pteranodon__(((((034)02)13)(((034)02)23)(034))(034)4)', net_worth = 990.53, uuid = '809f2923-87a1-798f-e6ad-dd9e61d9fe39'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((034)02)13)(((034)02)23)(034))(034)4)') to (select from Animal where name = 'Pteranodon__((((034)02)13)(((034)02)23)(034))')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((034)02)13)(((034)02)23)(034))(034)4)') to (select from Animal where name = 'Pteranodon__(034)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((034)02)13)(((034)02)23)(034))(034)4)') to (select from Animal where name = 'Pteranodon__4')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__0') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__1') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__2') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__3') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__4') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(034)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((034)02)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((034)04)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((034)02)((034)04)3)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((034)02)23)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((034)02)13)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((034)02)13)13)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((034)02)13)(((034)02)23)(034))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((034)02)((034)04)3)(034)3)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((034)02)13)(((034)02)23)(034))(034)4)') to (select from Species where name = 'Pteranodon')
create vertex Animal set birthday = DATE("2017-06-28 00:00:00"), color = 'green', name = 'Dragon__0', net_worth = 845.49, uuid = 'c12ea9b8-e7e1-3ed8-6d26-5dd8bf391fbb'
create vertex Animal set birthday = DATE("2015-08-01 00:00:00"), color = 'orange', name = 'Dragon__1', net_worth = 181.96, uuid = '961d8dcf-9b80-86da-6379-4035f8e45086'
create vertex Animal set birthday = DATE("2004-10-22 00:00:00"), color = 'yellow', name = 'Dragon__2', net_worth = 384.15, uuid = '552ae5ca-4124-405b-91fc-fe8881c16e98'
create vertex Animal set birthday = DATE("2009-11-21 00:00:00"), color = 'yellow', name = 'Dragon__3', net_worth = 673.54, uuid = '0932f5b6-f11d-dff7-0e37-05265582a3bd'
create vertex Animal set birthday = DATE("2008-06-03 00:00:00"), color = 'red', name = 'Dragon__4', net_worth = 778.14, uuid = '5a4f4145-fc98-c279-cf6f-111c26c06e67'
create vertex Animal set birthday = DATE("2008-08-10 00:00:00"), color = 'magenta', name = 'Dragon__(024)', net_worth = 124.32, uuid = 'e19b5837-1c6a-4b5e-7d85-9725c707aef9'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(024)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(024)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(024)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set birthday = DATE("2008-10-13 00:00:00"), color = 'orange', name = 'Dragon__((024)34)', net_worth = 789.55, uuid = '306aa871-feef-71cb-c915-d113dc45488d'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)34)') to (select from Animal where name = 'Dragon__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)34)') to (select from Animal where name = 'Dragon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)34)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set birthday = DATE("2002-11-12 00:00:00"), color = 'indigo', name = 'Dragon__(((024)34)04)', net_worth = 84.03, uuid = '81d1bf06-6b8c-66f2-8611-f583b2d10e3d'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)34)04)') to (select from Animal where name = 'Dragon__((024)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)34)04)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)34)04)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set birthday = DATE("2016-04-08 00:00:00"), color = 'yellow', name = 'Dragon__((((024)34)04)02)', net_worth = 352.5, uuid = '6ac1ca75-afb9-18c8-6e5b-ac20725c2675'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)34)04)02)') to (select from Animal where name = 'Dragon__(((024)34)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)34)04)02)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)34)04)02)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set birthday = DATE("2001-11-06 00:00:00"), color = 'orange', name = 'Dragon__((024)12)', net_worth = 204.79, uuid = 'f96d4403-d48c-93f3-028d-042b2d8b5b41'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)12)') to (select from Animal where name = 'Dragon__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)12)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)12)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set birthday = DATE("2004-02-13 00:00:00"), color = 'indigo', name = 'Dragon__(((((024)34)04)02)((024)34)0)', net_worth = 476.69, uuid = 'b080e003-5e7f-503c-4b13-47f601d6d903'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)34)04)02)((024)34)0)') to (select from Animal where name = 'Dragon__((((024)34)04)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)34)04)02)((024)34)0)') to (select from Animal where name = 'Dragon__((024)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)34)04)02)((024)34)0)') to (select from Animal where name = 'Dragon__0')
create vertex Animal set birthday = DATE("2017-12-23 00:00:00"), color = 'blue', name = 'Dragon__(((((024)34)04)02)23)', net_worth = 315.89, uuid = '94b28b9d-8881-9f42-1a42-b62914afe646'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)34)04)02)23)') to (select from Animal where name = 'Dragon__((((024)34)04)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)34)04)02)23)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)34)04)02)23)') to (select from Animal where name = 'Dragon__3')
create vertex Animal set birthday = DATE("2007-09-04 00:00:00"), color = 'magenta', name = 'Dragon__((((((024)34)04)02)23)((((024)34)04)02)2)', net_worth = 299.38, uuid = 'dc68d4fd-0bd7-696f-a9c7-2e7b6b770df1'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((024)34)04)02)23)((((024)34)04)02)2)') to (select from Animal where name = 'Dragon__(((((024)34)04)02)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((024)34)04)02)23)((((024)34)04)02)2)') to (select from Animal where name = 'Dragon__((((024)34)04)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((024)34)04)02)23)((((024)34)04)02)2)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set birthday = DATE("2007-12-02 00:00:00"), color = 'yellow', name = 'Dragon__((((((024)34)04)02)23)((024)34)(024))', net_worth = 408.62, uuid = '15a5712c-5ac4-b6c7-a310-34dd4c4b91fe'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((024)34)04)02)23)((024)34)(024))') to (select from Animal where name = 'Dragon__(((((024)34)04)02)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((024)34)04)02)23)((024)34)(024))') to (select from Animal where name = 'Dragon__((024)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((((024)34)04)02)23)((024)34)(024))') to (select from Animal where name = 'Dragon__(024)')
create vertex Animal set birthday = DATE("2003-02-04 00:00:00"), color = 'red', name = 'Dragon__(((024)12)(024)3)', net_worth = 605.54, uuid = 'f3cc9d8a-4b16-78e4-5f20-f4063438b4e4'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)12)(024)3)') to (select from Animal where name = 'Dragon__((024)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)12)(024)3)') to (select from Animal where name = 'Dragon__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)12)(024)3)') to (select from Animal where name = 'Dragon__3')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__0') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__1') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__2') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__3') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__4') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(024)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((024)34)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((024)34)04)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((024)34)04)02)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((024)12)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((024)34)04)02)((024)34)0)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((024)34)04)02)23)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((((024)34)04)02)23)((((024)34)04)02)2)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((((024)34)04)02)23)((024)34)(024))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((024)12)(024)3)') to (select from Species where name = 'Dragon')
create vertex Animal set birthday = DATE("2018-05-15 00:00:00"), color = 'blue', name = 'Hippogriff__0', net_worth = 355.36, uuid = '6bf4d047-c484-1a8d-2f75-1bde66163e5b'
create vertex Animal set birthday = DATE("2014-08-16 00:00:00"), color = 'green', name = 'Hippogriff__1', net_worth = 156.22, uuid = '01fda698-7646-57ca-9e65-736c72f774b1'
create vertex Animal set birthday = DATE("2004-04-22 00:00:00"), color = 'red', name = 'Hippogriff__2', net_worth = 908.77, uuid = '656fa7e6-b5c0-3f6f-94e4-cc44e3fbdbda'
create vertex Animal set birthday = DATE("2004-12-05 00:00:00"), color = 'magenta', name = 'Hippogriff__3', net_worth = 414.83, uuid = '57030ede-889c-8ae2-4e3c-0f2d4332559d'
create vertex Animal set birthday = DATE("2012-05-22 00:00:00"), color = 'yellow', name = 'Hippogriff__4', net_worth = 788.17, uuid = '88083ebc-35d4-cd35-a08c-3a0085e74250'
create vertex Animal set birthday = DATE("2008-07-09 00:00:00"), color = 'yellow', name = 'Hippogriff__(134)', net_worth = 632.11, uuid = '1eda4209-b270-af55-1f90-78d52835bcdb'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(134)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(134)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(134)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set birthday = DATE("2008-11-01 00:00:00"), color = 'red', name = 'Hippogriff__((134)14)', net_worth = 526.82, uuid = '9f032cdc-e328-66d3-0d6a-78b07eda9ab9'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((134)14)') to (select from Animal where name = 'Hippogriff__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((134)14)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((134)14)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set birthday = DATE("2002-01-08 00:00:00"), color = 'green', name = 'Hippogriff__((134)03)', net_worth = 640.37, uuid = '65264961-ab44-14ae-ecb3-d561bdf0b015'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((134)03)') to (select from Animal where name = 'Hippogriff__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((134)03)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((134)03)') to (select from Animal where name = 'Hippogriff__3')
create vertex Animal set birthday = DATE("2006-03-12 00:00:00"), color = 'yellow', name = 'Hippogriff__(((134)14)02)', net_worth = 897.2, uuid = '1aff71ae-30f2-c485-49b5-64fb92a651d7'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((134)14)02)') to (select from Animal where name = 'Hippogriff__((134)14)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((134)14)02)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((134)14)02)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set birthday = DATE("2015-06-06 00:00:00"), color = 'black', name = 'Hippogriff__((((134)14)02)34)', net_worth = 709.99, uuid = '7df0fe6b-ce8d-75f2-6d62-e40c638d521a'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((134)14)02)34)') to (select from Animal where name = 'Hippogriff__(((134)14)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((134)14)02)34)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((134)14)02)34)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set birthday = DATE("2009-12-27 00:00:00"), color = 'black', name = 'Hippogriff__(((((134)14)02)34)(134)0)', net_worth = 929.75, uuid = '7552c6e8-6953-a115-5a62-ddc4e2091f49'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((134)14)02)34)(134)0)') to (select from Animal where name = 'Hippogriff__((((134)14)02)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((134)14)02)34)(134)0)') to (select from Animal where name = 'Hippogriff__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((134)14)02)34)(134)0)') to (select from Animal where name = 'Hippogriff__0')
create vertex Animal set birthday = DATE("2000-05-09 00:00:00"), color = 'red', name = 'Hippogriff__((((((134)14)02)34)(134)0)(134)4)', net_worth = 7.13, uuid = '56525ce0-3725-bd0c-79c4-5c38b440ffe0'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((134)14)02)34)(134)0)(134)4)') to (select from Animal where name = 'Hippogriff__(((((134)14)02)34)(134)0)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((134)14)02)34)(134)0)(134)4)') to (select from Animal where name = 'Hippogriff__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((134)14)02)34)(134)0)(134)4)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set birthday = DATE("2006-02-25 00:00:00"), color = 'yellow', name = 'Hippogriff__(024)', net_worth = 794.79, uuid = 'ebe0572c-8ec9-ea98-6581-f9349bcfb1c4'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(024)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(024)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(024)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set birthday = DATE("2016-05-24 00:00:00"), color = 'red', name = 'Hippogriff__((134)34)', net_worth = 251.27, uuid = '30ac79dd-0b5a-afef-85a1-282a0761585b'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((134)34)') to (select from Animal where name = 'Hippogriff__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((134)34)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((134)34)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set birthday = DATE("2000-10-28 00:00:00"), color = 'black', name = 'Hippogriff__((((((134)14)02)34)(134)0)((134)14)3)', net_worth = 460.51, uuid = '75ff93f0-025b-7c5f-1284-b9d78d4e2753'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((134)14)02)34)(134)0)((134)14)3)') to (select from Animal where name = 'Hippogriff__(((((134)14)02)34)(134)0)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((134)14)02)34)(134)0)((134)14)3)') to (select from Animal where name = 'Hippogriff__((134)14)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((134)14)02)34)(134)0)((134)14)3)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__0') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__1') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__2') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__3') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__4') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(134)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((134)14)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((134)03)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((134)14)02)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((134)14)02)34)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((((134)14)02)34)(134)0)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((((134)14)02)34)(134)0)(134)4)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(024)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((134)34)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((((134)14)02)34)(134)0)((134)14)3)') to (select from Species where name = 'Hippogriff')
