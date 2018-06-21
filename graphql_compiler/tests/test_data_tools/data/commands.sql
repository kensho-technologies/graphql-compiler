# Auto-generated output from `graphql_compiler/scripts/generate_test_sql/__init__.py`.
# Do not edit directly!
# Generated on 2018-06-21T17:27:56.536873 from git revision 86af32173f90fc63bfeef87d6f75edafd0d53b6a.

create vertex Species set uuid = 'e3e70682-c209-4cac-629f-6fbed82c07cd', name = 'Nazgul'
create vertex Species set uuid = '82e2e662-f728-b4fa-4248-5e3a0a5d2f34', name = 'Pteranodon'
create vertex Species set uuid = 'd4713d60-c8a7-0639-eb11-67b367a9c378', name = 'Dragon'
create vertex Species set uuid = '23a7711a-8133-2876-37eb-dcd9e87a1613', name = 'Hippogriff'
create vertex Animal set uuid = 'e6f4590b-9a16-4106-cf6a-659eb4862b21', name = 'Nazgul__0'
create vertex Animal set uuid = '85776e9a-dd84-f39e-7154-5a137a1d5006', name = 'Nazgul__1'
create vertex Animal set uuid = 'd71037d1-b83e-90ec-17e0-aa3c03983ca8', name = 'Nazgul__2'
create vertex Animal set uuid = 'f7b0b7d2-cda8-056c-3d15-eef738c1962e', name = 'Nazgul__3'
create vertex Animal set uuid = '1759edc3-72ae-2244-8b01-63c1cd9d2b7d', name = 'Nazgul__4'
create vertex Animal set uuid = 'b4e1357d-4a84-eb03-8d1f-d9b74d2b9deb', name = 'Nazgul__(203)'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(203)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(203)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(203)') to (select from Animal where name = 'Nazgul__3')
create vertex Animal set uuid = '3dfabc08-935d-dd72-5129-fb7c6288e1a5', name = 'Nazgul__(214)'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(214)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(214)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(214)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set uuid = 'a81ad477-fb36-75b8-9cde-b3e60870e15c', name = 'Nazgul__((203)1(214))'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((203)1(214))') to (select from Animal where name = 'Nazgul__(203)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((203)1(214))') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((203)1(214))') to (select from Animal where name = 'Nazgul__(214)')
create vertex Animal set uuid = 'e07405eb-2156-63ab-c1f2-54b8adc0da7a', name = 'Nazgul__(0(214)((203)1(214)))'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0(214)((203)1(214)))') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0(214)((203)1(214)))') to (select from Animal where name = 'Nazgul__(214)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0(214)((203)1(214)))') to (select from Animal where name = 'Nazgul__((203)1(214))')
create vertex Animal set uuid = 'aef9c00b-8a64-c1b9-d450-fe4aec4f217b', name = 'Nazgul__(0(203)1)'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0(203)1)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0(203)1)') to (select from Animal where name = 'Nazgul__(203)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(0(203)1)') to (select from Animal where name = 'Nazgul__1')
create vertex Animal set uuid = '9466e472-6b5f-5241-f323-ca74d3447490', name = 'Nazgul__((0(214)((203)1(214)))34)'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((0(214)((203)1(214)))34)') to (select from Animal where name = 'Nazgul__(0(214)((203)1(214)))')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((0(214)((203)1(214)))34)') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((0(214)((203)1(214)))34)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set uuid = '1d878f9f-9cdf-5a86-5306-f3f515166570', name = 'Nazgul__(((0(214)((203)1(214)))34)(203)((203)1(214)))'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((0(214)((203)1(214)))34)(203)((203)1(214)))') to (select from Animal where name = 'Nazgul__((0(214)((203)1(214)))34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((0(214)((203)1(214)))34)(203)((203)1(214)))') to (select from Animal where name = 'Nazgul__(203)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((0(214)((203)1(214)))34)(203)((203)1(214)))') to (select from Animal where name = 'Nazgul__((203)1(214))')
create vertex Animal set uuid = '38701a14-b490-b608-1dfc-83524562be7f', name = 'Nazgul__((203)((0(214)((203)1(214)))34)(0(203)1))'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((203)((0(214)((203)1(214)))34)(0(203)1))') to (select from Animal where name = 'Nazgul__(203)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((203)((0(214)((203)1(214)))34)(0(203)1))') to (select from Animal where name = 'Nazgul__((0(214)((203)1(214)))34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((203)((0(214)((203)1(214)))34)(0(203)1))') to (select from Animal where name = 'Nazgul__(0(203)1)')
create vertex Animal set uuid = '38018b47-b29a-8b06-daf6-6c5f2577bffa', name = 'Nazgul__(2((203)((0(214)((203)1(214)))34)(0(203)1))(203))'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(2((203)((0(214)((203)1(214)))34)(0(203)1))(203))') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(2((203)((0(214)((203)1(214)))34)(0(203)1))(203))') to (select from Animal where name = 'Nazgul__((203)((0(214)((203)1(214)))34)(0(203)1))')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(2((203)((0(214)((203)1(214)))34)(0(203)1))(203))') to (select from Animal where name = 'Nazgul__(203)')
create vertex Animal set uuid = 'a28f5ab0-1fdb-8b32-06d5-99e812f175ff', name = 'Nazgul__(((0(214)((203)1(214)))34)(0(203)1)(2((203)((0(214)((203)1(214)))34)(0(203)1))(203)))'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((0(214)((203)1(214)))34)(0(203)1)(2((203)((0(214)((203)1(214)))34)(0(203)1))(203)))') to (select from Animal where name = 'Nazgul__((0(214)((203)1(214)))34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((0(214)((203)1(214)))34)(0(203)1)(2((203)((0(214)((203)1(214)))34)(0(203)1))(203)))') to (select from Animal where name = 'Nazgul__(0(203)1)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((0(214)((203)1(214)))34)(0(203)1)(2((203)((0(214)((203)1(214)))34)(0(203)1))(203)))') to (select from Animal where name = 'Nazgul__(2((203)((0(214)((203)1(214)))34)(0(203)1))(203))')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__0') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__1') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__2') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__3') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__4') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(203)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(214)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((203)1(214))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(0(214)((203)1(214)))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(0(203)1)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((0(214)((203)1(214)))34)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((0(214)((203)1(214)))34)(203)((203)1(214)))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((203)((0(214)((203)1(214)))34)(0(203)1))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(2((203)((0(214)((203)1(214)))34)(0(203)1))(203))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((0(214)((203)1(214)))34)(0(203)1)(2((203)((0(214)((203)1(214)))34)(0(203)1))(203)))') to (select from Species where name = 'Nazgul')
create vertex Animal set uuid = '1ea45cd6-9371-a71f-d480-865f9b38fe80', name = 'Pteranodon__0'
create vertex Animal set uuid = 'fb0323a1-d576-d415-5ec1-7dbe176ea1b1', name = 'Pteranodon__1'
create vertex Animal set uuid = '1fb797fa-b7d6-467b-2f5a-522af87f43fd', name = 'Pteranodon__2'
create vertex Animal set uuid = '11ebcd49-428a-1c22-d5fd-b76a19fbeb1d', name = 'Pteranodon__3'
create vertex Animal set uuid = '59acdd98-4d12-5e7f-a59c-ec98126cbc8f', name = 'Pteranodon__4'
create vertex Animal set uuid = '429817c5-3308-fb2e-642a-ad48fcfcfa81', name = 'Pteranodon__(102)'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(102)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(102)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(102)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set uuid = '402d0baf-878b-9f6b-57a1-cb712975d279', name = 'Pteranodon__(13(102))'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(13(102))') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(13(102))') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(13(102))') to (select from Animal where name = 'Pteranodon__(102)')
create vertex Animal set uuid = 'eae2025e-8233-9e23-dff3-334b91b15f5d', name = 'Pteranodon__(314)'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(314)') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(314)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(314)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set uuid = 'b0d9c2aa-8f83-7ef7-2746-0f22403d1f83', name = 'Pteranodon__((314)3(102))'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((314)3(102))') to (select from Animal where name = 'Pteranodon__(314)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((314)3(102))') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((314)3(102))') to (select from Animal where name = 'Pteranodon__(102)')
create vertex Animal set uuid = '47e7f593-8b58-85ca-0bb2-c3f0bd30291a', name = 'Pteranodon__((314)12)'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((314)12)') to (select from Animal where name = 'Pteranodon__(314)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((314)12)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((314)12)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set uuid = '4f6fa985-b732-d46f-21e1-50949efee464', name = 'Pteranodon__(((314)12)4(102))'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((314)12)4(102))') to (select from Animal where name = 'Pteranodon__((314)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((314)12)4(102))') to (select from Animal where name = 'Pteranodon__4')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((314)12)4(102))') to (select from Animal where name = 'Pteranodon__(102)')
create vertex Animal set uuid = '559b5975-b2d6-50af-313b-32b798363189', name = 'Pteranodon__(1(13(102))0)'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1(13(102))0)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1(13(102))0)') to (select from Animal where name = 'Pteranodon__(13(102))')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1(13(102))0)') to (select from Animal where name = 'Pteranodon__0')
create vertex Animal set uuid = '720299e3-2a69-acc7-0bf9-c0efb5816b74', name = 'Pteranodon__((314)3(1(13(102))0))'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((314)3(1(13(102))0))') to (select from Animal where name = 'Pteranodon__(314)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((314)3(1(13(102))0))') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((314)3(1(13(102))0))') to (select from Animal where name = 'Pteranodon__(1(13(102))0)')
create vertex Animal set uuid = 'fa83ada4-a212-1ac5-f689-a4a5ffda0336', name = 'Pteranodon__((1(13(102))0)42)'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((1(13(102))0)42)') to (select from Animal where name = 'Pteranodon__(1(13(102))0)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((1(13(102))0)42)') to (select from Animal where name = 'Pteranodon__4')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((1(13(102))0)42)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set uuid = '36a98d74-00de-59f5-50f0-fc2b6ae04d52', name = 'Pteranodon__(((1(13(102))0)42)(1(13(102))0)2)'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1(13(102))0)42)(1(13(102))0)2)') to (select from Animal where name = 'Pteranodon__((1(13(102))0)42)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1(13(102))0)42)(1(13(102))0)2)') to (select from Animal where name = 'Pteranodon__(1(13(102))0)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((1(13(102))0)42)(1(13(102))0)2)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__0') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__1') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__2') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__3') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__4') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(102)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(13(102))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(314)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((314)3(102))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((314)12)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((314)12)4(102))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(1(13(102))0)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((314)3(1(13(102))0))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((1(13(102))0)42)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((1(13(102))0)42)(1(13(102))0)2)') to (select from Species where name = 'Pteranodon')
create vertex Animal set uuid = '19086515-9cb0-17c1-8741-ae91acfebb4b', name = 'Dragon__0'
create vertex Animal set uuid = 'fa7ff8bf-b044-284a-47ac-f2f64d6b234f', name = 'Dragon__1'
create vertex Animal set uuid = 'ec3aa314-da9b-b017-79c1-47c719a5711b', name = 'Dragon__2'
create vertex Animal set uuid = '04c14982-d9ea-d926-4745-dd9e27896389', name = 'Dragon__3'
create vertex Animal set uuid = 'a7c5cb87-9b8b-71a1-b38a-05fbf61164ce', name = 'Dragon__4'
create vertex Animal set uuid = '35354579-2da4-4da1-89b5-b368df14c612', name = 'Dragon__(134)'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(134)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(134)') to (select from Animal where name = 'Dragon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(134)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set uuid = '555a4085-4578-bab3-26a9-74652371ea2c', name = 'Dragon__(240)'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(240)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(240)') to (select from Animal where name = 'Dragon__4')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(240)') to (select from Animal where name = 'Dragon__0')
create vertex Animal set uuid = '09215f4f-9edb-95f2-c787-ddfb5697f17c', name = 'Dragon__(2(240)0)'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2(240)0)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2(240)0)') to (select from Animal where name = 'Dragon__(240)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2(240)0)') to (select from Animal where name = 'Dragon__0')
create vertex Animal set uuid = '5c646036-4a1e-b1b7-955d-0e77fb5eb866', name = 'Dragon__(1(240)4)'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1(240)4)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1(240)4)') to (select from Animal where name = 'Dragon__(240)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1(240)4)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set uuid = '1bd09448-6a2b-3200-4c9a-0ae15419eefc', name = 'Dragon__(2(1(240)4)(2(240)0))'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2(1(240)4)(2(240)0))') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2(1(240)4)(2(240)0))') to (select from Animal where name = 'Dragon__(1(240)4)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2(1(240)4)(2(240)0))') to (select from Animal where name = 'Dragon__(2(240)0)')
create vertex Animal set uuid = '4d4985dc-09ae-dbd0-6d31-6b4a7f6b8793', name = 'Dragon__((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))') to (select from Animal where name = 'Dragon__(2(1(240)4)(2(240)0))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))') to (select from Animal where name = 'Dragon__(1(240)4)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))') to (select from Animal where name = 'Dragon__(2(240)0)')
create vertex Animal set uuid = '38974df5-bff7-73ce-32b2-c49215ace7a1', name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))2)'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))2)') to (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))2)') to (select from Animal where name = 'Dragon__(2(1(240)4)(2(240)0))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))2)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set uuid = '4a31b243-84dd-6da6-8e75-1eb764d09913', name = 'Dragon__(1(240)0)'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1(240)0)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1(240)0)') to (select from Animal where name = 'Dragon__(240)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(1(240)0)') to (select from Animal where name = 'Dragon__0')
create vertex Animal set uuid = '5e4af862-156a-f458-6c4c-3935379deda1', name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))(2(240)0))'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))(2(240)0))') to (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))(2(240)0))') to (select from Animal where name = 'Dragon__(2(1(240)4)(2(240)0))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))(2(240)0))') to (select from Animal where name = 'Dragon__(2(240)0)')
create vertex Animal set uuid = '1d7173e5-5bc7-fdeb-3123-4efe6e648043', name = 'Dragon__((2(1(240)4)(2(240)0))24)'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))24)') to (select from Animal where name = 'Dragon__(2(1(240)4)(2(240)0))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))24)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))24)') to (select from Animal where name = 'Dragon__4')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__0') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__1') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__2') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__3') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__4') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(134)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(240)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(2(240)0)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(1(240)4)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(2(1(240)4)(2(240)0))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))2)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(1(240)0)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((2(1(240)4)(2(240)0))(1(240)4)(2(240)0))(2(1(240)4)(2(240)0))(2(240)0))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((2(1(240)4)(2(240)0))24)') to (select from Species where name = 'Dragon')
create vertex Animal set uuid = 'b3b68b57-da54-f267-dd13-8266d26d5396', name = 'Hippogriff__0'
create vertex Animal set uuid = '65e04993-7f41-1fed-1e70-e79933a1d1c2', name = 'Hippogriff__1'
create vertex Animal set uuid = '25777cf0-9f98-2188-3744-da64cc249558', name = 'Hippogriff__2'
create vertex Animal set uuid = '905c053b-25fd-acbe-7ce7-1b48fba52e59', name = 'Hippogriff__3'
create vertex Animal set uuid = 'e345ac72-eac3-9204-ade7-cef37ed2ec2f', name = 'Hippogriff__4'
create vertex Animal set uuid = 'ccc93ff7-10fc-e97d-786e-30efce9b2e70', name = 'Hippogriff__(432)'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(432)') to (select from Animal where name = 'Hippogriff__4')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(432)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(432)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set uuid = '4cea2df0-0a66-dc4e-2168-1081399f8a8f', name = 'Hippogriff__(40(432))'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(40(432))') to (select from Animal where name = 'Hippogriff__4')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(40(432))') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(40(432))') to (select from Animal where name = 'Hippogriff__(432)')
create vertex Animal set uuid = '809f2923-87a1-798f-e6ad-dd9e61d9fe39', name = 'Hippogriff__((40(432))32)'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((40(432))32)') to (select from Animal where name = 'Hippogriff__(40(432))')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((40(432))32)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((40(432))32)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set uuid = '34c3494a-c12e-a9b8-e7e1-3ed86d265dd8', name = 'Hippogriff__(4(432)1)'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(4(432)1)') to (select from Animal where name = 'Hippogriff__4')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(4(432)1)') to (select from Animal where name = 'Hippogriff__(432)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(4(432)1)') to (select from Animal where name = 'Hippogriff__1')
create vertex Animal set uuid = '10cc8711-552a-e5ca-4124-405b91fcfe88', name = 'Hippogriff__((40(432))(4(432)1)((40(432))32))'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((40(432))(4(432)1)((40(432))32))') to (select from Animal where name = 'Hippogriff__(40(432))')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((40(432))(4(432)1)((40(432))32))') to (select from Animal where name = 'Hippogriff__(4(432)1)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((40(432))(4(432)1)((40(432))32))') to (select from Animal where name = 'Hippogriff__((40(432))32)')
create vertex Animal set uuid = '0ff030b8-6238-d0a0-cf5e-9ea362584ab3', name = 'Hippogriff__(4((40(432))(4(432)1)((40(432))32))(40(432)))'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(4((40(432))(4(432)1)((40(432))32))(40(432)))') to (select from Animal where name = 'Hippogriff__4')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(4((40(432))(4(432)1)((40(432))32))(40(432)))') to (select from Animal where name = 'Hippogriff__((40(432))(4(432)1)((40(432))32))')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(4((40(432))(4(432)1)((40(432))32))(40(432)))') to (select from Animal where name = 'Hippogriff__(40(432))')
create vertex Animal set uuid = '5582a3bd-d476-fe38-babd-4745497e9f1a', name = 'Hippogriff__(3(4((40(432))(4(432)1)((40(432))32))(40(432)))2)'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(3(4((40(432))(4(432)1)((40(432))32))(40(432)))2)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(3(4((40(432))(4(432)1)((40(432))32))(40(432)))2)') to (select from Animal where name = 'Hippogriff__(4((40(432))(4(432)1)((40(432))32))(40(432)))')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(3(4((40(432))(4(432)1)((40(432))32))(40(432)))2)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set uuid = 'b2ddc481-ac6d-5df8-14e5-064cb799ae8e', name = 'Hippogriff__((40(432))0((40(432))32))'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((40(432))0((40(432))32))') to (select from Animal where name = 'Hippogriff__(40(432))')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((40(432))0((40(432))32))') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((40(432))0((40(432))32))') to (select from Animal where name = 'Hippogriff__((40(432))32)')
create vertex Animal set uuid = '62fda854-775e-0ec3-9c9d-03f309018aee', name = 'Hippogriff__(((40(432))0((40(432))32))(432)(40(432)))'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((40(432))0((40(432))32))(432)(40(432)))') to (select from Animal where name = 'Hippogriff__((40(432))0((40(432))32))')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((40(432))0((40(432))32))(432)(40(432)))') to (select from Animal where name = 'Hippogriff__(432)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((40(432))0((40(432))32))(432)(40(432)))') to (select from Animal where name = 'Hippogriff__(40(432))')
create vertex Animal set uuid = '52ebdac5-a145-7899-21f8-c1569e0df45b', name = 'Hippogriff__(0((40(432))32)1)'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(0((40(432))32)1)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(0((40(432))32)1)') to (select from Animal where name = 'Hippogriff__((40(432))32)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(0((40(432))32)1)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__0') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__1') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__2') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__3') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__4') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(432)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(40(432))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((40(432))32)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(4(432)1)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((40(432))(4(432)1)((40(432))32))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(4((40(432))(4(432)1)((40(432))32))(40(432)))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(3(4((40(432))(4(432)1)((40(432))32))(40(432)))2)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((40(432))0((40(432))32))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((40(432))0((40(432))32))(432)(40(432)))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(0((40(432))32)1)') to (select from Species where name = 'Hippogriff')
