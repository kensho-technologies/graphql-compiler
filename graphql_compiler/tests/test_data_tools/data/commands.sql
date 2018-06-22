# Auto-generated output from `graphql_compiler/scripts/generate_test_sql/__init__.py`.
# Do not edit directly!
# Generated on 2018-06-22T14:30:37.332063 from git revision 66ee1b496875d2666ef46f9579f651a02bbe4a19.

create vertex Species set name = 'Nazgul', uuid = 'e3e70682-c209-4cac-629f-6fbed82c07cd'
create vertex Species set name = 'Pteranodon', uuid = '82e2e662-f728-b4fa-4248-5e3a0a5d2f34'
create vertex Species set name = 'Dragon', uuid = 'd4713d60-c8a7-0639-eb11-67b367a9c378'
create vertex Species set name = 'Hippogriff', uuid = '23a7711a-8133-2876-37eb-dcd9e87a1613'
create vertex Animal set name = 'Nazgul__0', uuid = 'e6f4590b-9a16-4106-cf6a-659eb4862b21'
create vertex Animal set name = 'Nazgul__1', uuid = '85776e9a-dd84-f39e-7154-5a137a1d5006'
create vertex Animal set name = 'Nazgul__2', uuid = 'd71037d1-b83e-90ec-17e0-aa3c03983ca8'
create vertex Animal set name = 'Nazgul__3', uuid = 'f7b0b7d2-cda8-056c-3d15-eef738c1962e'
create vertex Animal set name = 'Nazgul__4', uuid = '1759edc3-72ae-2244-8b01-63c1cd9d2b7d'
create vertex Animal set name = 'Nazgul__(023)', uuid = 'b4e1357d-4a84-eb03-8d1f-d9b74d2b9deb'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(023)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(023)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(023)') to (select from Animal where name = 'Nazgul__3')
create vertex Animal set name = 'Nazgul__(124)', uuid = '3dfabc08-935d-dd72-5129-fb7c6288e1a5'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(124)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(124)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(124)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__((023)(124)1)', uuid = 'a81ad477-fb36-75b8-9cde-b3e60870e15c'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)(124)1)') to (select from Animal where name = 'Nazgul__(023)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)(124)1)') to (select from Animal where name = 'Nazgul__(124)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)(124)1)') to (select from Animal where name = 'Nazgul__1')
create vertex Animal set name = 'Nazgul__(((023)(124)1)(124)0)', uuid = 'e07405eb-2156-63ab-c1f2-54b8adc0da7a'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)') to (select from Animal where name = 'Nazgul__((023)(124)1)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)') to (select from Animal where name = 'Nazgul__(124)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)') to (select from Animal where name = 'Nazgul__0')
create vertex Animal set name = 'Nazgul__((023)01)', uuid = 'aef9c00b-8a64-c1b9-d450-fe4aec4f217b'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)01)') to (select from Animal where name = 'Nazgul__(023)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)01)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)01)') to (select from Animal where name = 'Nazgul__1')
create vertex Animal set name = 'Nazgul__((((023)(124)1)(124)0)34)', uuid = '9466e472-6b5f-5241-f323-ca74d3447490'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)') to (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))', uuid = '1d878f9f-9cdf-5a86-5306-f3f515166570'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))') to (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))') to (select from Animal where name = 'Nazgul__((023)(124)1)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))') to (select from Animal where name = 'Nazgul__(023)')
create vertex Animal set name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))', uuid = '38701a14-b490-b608-1dfc-83524562be7f'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))') to (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))') to (select from Animal where name = 'Nazgul__((023)01)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))') to (select from Animal where name = 'Nazgul__(023)')
create vertex Animal set name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)', uuid = '38018b47-b29a-8b06-daf6-6c5f2577bffa'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)') to (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)') to (select from Animal where name = 'Nazgul__(023)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)') to (select from Animal where name = 'Nazgul__2')
create vertex Animal set name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))', uuid = 'a28f5ab0-1fdb-8b32-06d5-99e812f175ff'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))') to (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))') to (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))') to (select from Animal where name = 'Nazgul__((023)01)')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__0') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__1') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__2') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__3') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__4') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(023)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(124)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((023)(124)1)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((023)01)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))') to (select from Species where name = 'Nazgul')
create vertex Animal set name = 'Pteranodon__0', uuid = '1ea45cd6-9371-a71f-d480-865f9b38fe80'
create vertex Animal set name = 'Pteranodon__1', uuid = 'fb0323a1-d576-d415-5ec1-7dbe176ea1b1'
create vertex Animal set name = 'Pteranodon__2', uuid = '1fb797fa-b7d6-467b-2f5a-522af87f43fd'
create vertex Animal set name = 'Pteranodon__3', uuid = '11ebcd49-428a-1c22-d5fd-b76a19fbeb1d'
create vertex Animal set name = 'Pteranodon__4', uuid = '59acdd98-4d12-5e7f-a59c-ec98126cbc8f'
create vertex Animal set name = 'Pteranodon__(012)', uuid = '429817c5-3308-fb2e-642a-ad48fcfcfa81'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set name = 'Pteranodon__((012)13)', uuid = '402d0baf-878b-9f6b-57a1-cb712975d279'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)13)') to (select from Animal where name = 'Pteranodon__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)13)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)13)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__(134)', uuid = 'eae2025e-8233-9e23-dff3-334b91b15f5d'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(134)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(134)') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(134)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__((012)(134)3)', uuid = 'b0d9c2aa-8f83-7ef7-2746-0f22403d1f83'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)(134)3)') to (select from Animal where name = 'Pteranodon__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)(134)3)') to (select from Animal where name = 'Pteranodon__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)(134)3)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__((134)12)', uuid = '47e7f593-8b58-85ca-0bb2-c3f0bd30291a'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((134)12)') to (select from Animal where name = 'Pteranodon__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((134)12)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((134)12)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set name = 'Pteranodon__(((134)12)(012)4)', uuid = '4f6fa985-b732-d46f-21e1-50949efee464'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((134)12)(012)4)') to (select from Animal where name = 'Pteranodon__((134)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((134)12)(012)4)') to (select from Animal where name = 'Pteranodon__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((134)12)(012)4)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__(((012)13)01)', uuid = '559b5975-b2d6-50af-313b-32b798363189'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((012)13)01)') to (select from Animal where name = 'Pteranodon__((012)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((012)13)01)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((012)13)01)') to (select from Animal where name = 'Pteranodon__1')
create vertex Animal set name = 'Pteranodon__((((012)13)01)(134)3)', uuid = '720299e3-2a69-acc7-0bf9-c0efb5816b74'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)(134)3)') to (select from Animal where name = 'Pteranodon__(((012)13)01)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)(134)3)') to (select from Animal where name = 'Pteranodon__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)(134)3)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__((((012)13)01)24)', uuid = 'fa83ada4-a212-1ac5-f689-a4a5ffda0336'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)24)') to (select from Animal where name = 'Pteranodon__(((012)13)01)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)24)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)24)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)', uuid = '36a98d74-00de-59f5-50f0-fc2b6ae04d52'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)') to (select from Animal where name = 'Pteranodon__((((012)13)01)24)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)') to (select from Animal where name = 'Pteranodon__(((012)13)01)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__0') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__1') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__2') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__3') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__4') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(012)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((012)13)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(134)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((012)(134)3)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((134)12)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((134)12)(012)4)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((012)13)01)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((012)13)01)(134)3)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((012)13)01)24)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)') to (select from Species where name = 'Pteranodon')
create vertex Animal set name = 'Dragon__0', uuid = '19086515-9cb0-17c1-8741-ae91acfebb4b'
create vertex Animal set name = 'Dragon__1', uuid = 'fa7ff8bf-b044-284a-47ac-f2f64d6b234f'
create vertex Animal set name = 'Dragon__2', uuid = 'ec3aa314-da9b-b017-79c1-47c719a5711b'
create vertex Animal set name = 'Dragon__3', uuid = '04c14982-d9ea-d926-4745-dd9e27896389'
create vertex Animal set name = 'Dragon__4', uuid = 'a7c5cb87-9b8b-71a1-b38a-05fbf61164ce'
create vertex Animal set name = 'Dragon__(134)', uuid = '35354579-2da4-4da1-89b5-b368df14c612'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(134)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(134)') to (select from Animal where name = 'Dragon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(134)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set name = 'Dragon__(024)', uuid = '555a4085-4578-bab3-26a9-74652371ea2c'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(024)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(024)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(024)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set name = 'Dragon__((024)02)', uuid = '09215f4f-9edb-95f2-c787-ddfb5697f17c'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)02)') to (select from Animal where name = 'Dragon__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)02)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)02)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set name = 'Dragon__((024)14)', uuid = '5c646036-4a1e-b1b7-955d-0e77fb5eb866'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)14)') to (select from Animal where name = 'Dragon__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)14)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)14)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set name = 'Dragon__(((024)02)((024)14)2)', uuid = '1bd09448-6a2b-3200-4c9a-0ae15419eefc'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)02)((024)14)2)') to (select from Animal where name = 'Dragon__((024)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)02)((024)14)2)') to (select from Animal where name = 'Dragon__((024)14)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)02)((024)14)2)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))', uuid = '4d4985dc-09ae-dbd0-6d31-6b4a7f6b8793'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))') to (select from Animal where name = 'Dragon__(((024)02)((024)14)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))') to (select from Animal where name = 'Dragon__((024)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))') to (select from Animal where name = 'Dragon__((024)14)')
create vertex Animal set name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)', uuid = '38974df5-bff7-73ce-32b2-c49215ace7a1'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)') to (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)') to (select from Animal where name = 'Dragon__(((024)02)((024)14)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set name = 'Dragon__((024)01)', uuid = '4a31b243-84dd-6da6-8e75-1eb764d09913'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)01)') to (select from Animal where name = 'Dragon__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)01)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)01)') to (select from Animal where name = 'Dragon__1')
create vertex Animal set name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))', uuid = '5e4af862-156a-f458-6c4c-3935379deda1'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))') to (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))') to (select from Animal where name = 'Dragon__(((024)02)((024)14)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))') to (select from Animal where name = 'Dragon__((024)02)')
create vertex Animal set name = 'Dragon__((((024)02)((024)14)2)24)', uuid = '1d7173e5-5bc7-fdeb-3123-4efe6e648043'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)24)') to (select from Animal where name = 'Dragon__(((024)02)((024)14)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)24)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)24)') to (select from Animal where name = 'Dragon__4')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__0') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__1') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__2') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__3') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__4') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(134)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(024)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((024)02)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((024)14)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((024)02)((024)14)2)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((024)01)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)24)') to (select from Species where name = 'Dragon')
create vertex Animal set name = 'Hippogriff__0', uuid = 'b3b68b57-da54-f267-dd13-8266d26d5396'
create vertex Animal set name = 'Hippogriff__1', uuid = '65e04993-7f41-1fed-1e70-e79933a1d1c2'
create vertex Animal set name = 'Hippogriff__2', uuid = '25777cf0-9f98-2188-3744-da64cc249558'
create vertex Animal set name = 'Hippogriff__3', uuid = '905c053b-25fd-acbe-7ce7-1b48fba52e59'
create vertex Animal set name = 'Hippogriff__4', uuid = 'e345ac72-eac3-9204-ade7-cef37ed2ec2f'
create vertex Animal set name = 'Hippogriff__(234)', uuid = 'ccc93ff7-10fc-e97d-786e-30efce9b2e70'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(234)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(234)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(234)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__((234)04)', uuid = '4cea2df0-0a66-dc4e-2168-1081399f8a8f'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)04)') to (select from Animal where name = 'Hippogriff__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)04)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)04)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__(((234)04)23)', uuid = '809f2923-87a1-798f-e6ad-dd9e61d9fe39'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((234)04)23)') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((234)04)23)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((234)04)23)') to (select from Animal where name = 'Hippogriff__3')
create vertex Animal set name = 'Hippogriff__((234)14)', uuid = '34c3494a-c12e-a9b8-e7e1-3ed86d265dd8'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)14)') to (select from Animal where name = 'Hippogriff__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)14)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)14)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__((((234)04)23)((234)04)((234)14))', uuid = '10cc8711-552a-e5ca-4124-405b91fcfe88'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))') to (select from Animal where name = 'Hippogriff__(((234)04)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))') to (select from Animal where name = 'Hippogriff__((234)14)')
create vertex Animal set name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)', uuid = '0ff030b8-6238-d0a0-cf5e-9ea362584ab3'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)') to (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)', uuid = '5582a3bd-d476-fe38-babd-4745497e9f1a'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)') to (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)') to (select from Animal where name = 'Hippogriff__3')
create vertex Animal set name = 'Hippogriff__((((234)04)23)((234)04)0)', uuid = 'b2ddc481-ac6d-5df8-14e5-064cb799ae8e'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)') to (select from Animal where name = 'Hippogriff__(((234)04)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)') to (select from Animal where name = 'Hippogriff__0')
create vertex Animal set name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))', uuid = '62fda854-775e-0ec3-9c9d-03f309018aee'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))') to (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))') to (select from Animal where name = 'Hippogriff__(234)')
create vertex Animal set name = 'Hippogriff__((((234)04)23)01)', uuid = '52ebdac5-a145-7899-21f8-c1569e0df45b'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)01)') to (select from Animal where name = 'Hippogriff__(((234)04)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)01)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)01)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__0') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__1') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__2') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__3') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__4') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(234)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((234)04)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((234)04)23)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((234)14)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((234)04)23)01)') to (select from Species where name = 'Hippogriff')
