# Auto-generated output from `graphql_compiler/scripts/generate_test_sql/__init__.py`.
# Do not edit directly!
# Generated on 2018-06-25T11:14:20.634354 from compiler version 1.5.0.

create vertex Species set name = 'Nazgul', uuid = 'e3e70682-c209-4cac-629f-6fbed82c07cd'
create vertex Species set name = 'Pteranodon', uuid = '82e2e662-f728-b4fa-4248-5e3a0a5d2f34'
create vertex Species set name = 'Dragon', uuid = 'd4713d60-c8a7-0639-eb11-67b367a9c378'
create vertex Species set name = 'Hippogriff', uuid = '23a7711a-8133-2876-37eb-dcd9e87a1613'
create vertex Animal set name = 'Nazgul__0', uuid = 'e6f4590b-9a16-4106-cf6a-659eb4862b21'
create vertex Animal set name = 'Nazgul__1', uuid = '85776e9a-dd84-f39e-7154-5a137a1d5006'
create vertex Animal set name = 'Nazgul__2', uuid = 'd71037d1-b83e-90ec-17e0-aa3c03983ca8'
create vertex Animal set name = 'Nazgul__3', uuid = 'f7b0b7d2-cda8-056c-3d15-eef738c1962e'
create vertex Animal set name = 'Nazgul__4', uuid = '1759edc3-72ae-2244-8b01-63c1cd9d2b7d'
create vertex Animal set name = 'Nazgul__(234)', uuid = '8d1fd9b7-4d2b-9deb-1beb-37117d41e602'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(234)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(234)') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(234)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__((234)12)', uuid = '79fdef7c-4293-0b33-a81a-d477fb3675b8'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)12)') to (select from Animal where name = 'Nazgul__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)12)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)12)') to (select from Animal where name = 'Nazgul__2')
create vertex Animal set name = 'Nazgul__((234)04)', uuid = '864a7a50-b48d-73f1-d67e-55fd642bfa42'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)04)') to (select from Animal where name = 'Nazgul__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)04)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)04)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__(((234)12)14)', uuid = 'f323ca74-d344-7490-96fd-35d0adf20806'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)12)14)') to (select from Animal where name = 'Nazgul__((234)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)12)14)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)12)14)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__((234)34)', uuid = '9cdf5a86-5306-f3f5-1516-65705b7c709a'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)34)') to (select from Animal where name = 'Nazgul__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)34)') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((234)34)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__(((234)12)(234)4)', uuid = '4562be7f-bb42-e0b2-0426-465e3e37952d'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)12)(234)4)') to (select from Animal where name = 'Nazgul__((234)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)12)(234)4)') to (select from Animal where name = 'Nazgul__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)12)(234)4)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__(((234)04)13)', uuid = '38018b47-b29a-8b06-daf6-6c5f2577bffa'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)04)13)') to (select from Animal where name = 'Nazgul__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)04)13)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((234)04)13)') to (select from Animal where name = 'Nazgul__3')
create vertex Animal set name = 'Nazgul__((((234)04)13)((234)12)((234)34))', uuid = '06d599e8-12f1-75ff-ae3b-16ec9a27d858'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((234)04)13)((234)12)((234)34))') to (select from Animal where name = 'Nazgul__(((234)04)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((234)04)13)((234)12)((234)34))') to (select from Animal where name = 'Nazgul__((234)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((234)04)13)((234)12)((234)34))') to (select from Animal where name = 'Nazgul__((234)34)')
create vertex Animal set name = 'Nazgul__((((234)12)14)((234)04)((234)12))', uuid = '0589f877-9b02-5244-0950-fd131db53334'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((234)12)14)((234)04)((234)12))') to (select from Animal where name = 'Nazgul__(((234)12)14)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((234)12)14)((234)04)((234)12))') to (select from Animal where name = 'Nazgul__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((234)12)14)((234)04)((234)12))') to (select from Animal where name = 'Nazgul__((234)12)')
create vertex Animal set name = 'Nazgul__(((((234)12)14)((234)04)((234)12))12)', uuid = '11ebcd49-428a-1c22-d5fd-b76a19fbeb1d'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((234)12)14)((234)04)((234)12))12)') to (select from Animal where name = 'Nazgul__((((234)12)14)((234)04)((234)12))')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((234)12)14)((234)04)((234)12))12)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((234)12)14)((234)04)((234)12))12)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__0') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__1') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__2') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__3') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__4') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(234)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((234)12)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((234)04)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((234)12)14)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((234)34)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((234)12)(234)4)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((234)04)13)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((234)04)13)((234)12)((234)34))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((234)12)14)((234)04)((234)12))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((234)12)14)((234)04)((234)12))12)') to (select from Species where name = 'Nazgul')
create vertex Animal set name = 'Pteranodon__0', uuid = '59acdd98-4d12-5e7f-a59c-ec98126cbc8f'
create vertex Animal set name = 'Pteranodon__1', uuid = '7795e986-80ee-526e-0fa0-7a3f2e295065'
create vertex Animal set name = 'Pteranodon__2', uuid = 'fcfcfa81-b306-d700-19d5-f97098b33c6e'
create vertex Animal set name = 'Pteranodon__3', uuid = 'ad1b8f60-c9e4-dab2-0edc-6d2bc470f0e7'
create vertex Animal set name = 'Pteranodon__4', uuid = '878b9f6b-57a1-cb71-2975-d279d86dbf11'
create vertex Animal set name = 'Pteranodon__(013)', uuid = 'eae2025e-8233-9e23-dff3-334b91b15f5d'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(013)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(013)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(013)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__(123)', uuid = '032f06ca-b0d9-c2aa-8f83-7ef727460f22'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(123)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(123)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(123)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__((013)02)', uuid = 'b732d46f-21e1-5094-9efe-e464da90f534'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((013)02)') to (select from Animal where name = 'Pteranodon__(013)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((013)02)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((013)02)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set name = 'Pteranodon__(((013)02)23)', uuid = 'b2d650af-313b-32b7-9836-31890063e42f'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((013)02)23)') to (select from Animal where name = 'Pteranodon__((013)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((013)02)23)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((013)02)23)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__((((013)02)23)13)', uuid = '105ada6b-7202-99e3-2a69-acc70bf9c0ef'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((013)02)23)13)') to (select from Animal where name = 'Pteranodon__(((013)02)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((013)02)23)13)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((013)02)23)13)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__(((((013)02)23)13)((013)02)4)', uuid = 'c167733f-9a9e-4310-8fb8-3babe8754cd3'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((013)02)23)13)((013)02)4)') to (select from Animal where name = 'Pteranodon__((((013)02)23)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((013)02)23)13)((013)02)4)') to (select from Animal where name = 'Pteranodon__((013)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((013)02)23)13)((013)02)4)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__(((((013)02)23)13)24)', uuid = 'fa83ada4-a212-1ac5-f689-a4a5ffda0336'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((013)02)23)13)24)') to (select from Animal where name = 'Pteranodon__((((013)02)23)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((013)02)23)13)24)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((013)02)23)13)24)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__((((((013)02)23)13)((013)02)4)01)', uuid = '50f0fc2b-6ae0-4d52-adb3-28cbf3158c0c'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((013)02)23)13)((013)02)4)01)') to (select from Animal where name = 'Pteranodon__(((((013)02)23)13)((013)02)4)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((013)02)23)13)((013)02)4)01)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((((013)02)23)13)((013)02)4)01)') to (select from Animal where name = 'Pteranodon__1')
create vertex Animal set name = 'Pteranodon__((((013)02)23)02)', uuid = '9cb017c1-8741-ae91-acfe-bb4bd29e8693'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((013)02)23)02)') to (select from Animal where name = 'Pteranodon__(((013)02)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((013)02)23)02)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((013)02)23)02)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set name = 'Pteranodon__(((((013)02)23)02)((013)02)2)', uuid = 'fa7ff8bf-b044-284a-47ac-f2f64d6b234f'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((013)02)23)02)((013)02)2)') to (select from Animal where name = 'Pteranodon__((((013)02)23)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((013)02)23)02)((013)02)2)') to (select from Animal where name = 'Pteranodon__((013)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((013)02)23)02)((013)02)2)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__0') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__1') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__2') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__3') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__4') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(013)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(123)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((013)02)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((013)02)23)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((013)02)23)13)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((013)02)23)13)((013)02)4)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((013)02)23)13)24)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((((013)02)23)13)((013)02)4)01)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((013)02)23)02)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((013)02)23)02)((013)02)2)') to (select from Species where name = 'Pteranodon')
create vertex Animal set name = 'Dragon__0', uuid = 'ec3aa314-da9b-b017-79c1-47c719a5711b'
create vertex Animal set name = 'Dragon__1', uuid = '04c14982-d9ea-d926-4745-dd9e27896389'
create vertex Animal set name = 'Dragon__2', uuid = 'a7c5cb87-9b8b-71a1-b38a-05fbf61164ce'
create vertex Animal set name = 'Dragon__3', uuid = '89b5b368-df14-c612-5f58-d5b56f790959'
create vertex Animal set name = 'Dragon__4', uuid = '4a814d53-964d-db77-6025-f0ae35354579'
create vertex Animal set name = 'Dragon__(013)', uuid = '4505f4f6-0a8c-46c7-0921-5f4f9edb95f2'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(013)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(013)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(013)') to (select from Animal where name = 'Dragon__3')
create vertex Animal set name = 'Dragon__(012)', uuid = '4b1cb8bd-2130-260c-8c69-778ffd42f697'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(012)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(012)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(012)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set name = 'Dragon__((012)12)', uuid = '7b2e1b82-e89d-c815-8f92-8dc519724ce3'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((012)12)') to (select from Animal where name = 'Dragon__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((012)12)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((012)12)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set name = 'Dragon__((013)24)', uuid = 'b318ad4c-1db2-b452-7aa5-6a181fd3c017'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((013)24)') to (select from Animal where name = 'Dragon__(013)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((013)24)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((013)24)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set name = 'Dragon__((013)23)', uuid = 'ceca2ee3-10da-8a95-1640-8169a38d8afc'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((013)23)') to (select from Animal where name = 'Dragon__(013)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((013)23)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((013)23)') to (select from Animal where name = 'Dragon__3')
create vertex Animal set name = 'Dragon__(((013)23)13)', uuid = '84dd6da6-8e75-1eb7-64d0-9913191b8adf'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((013)23)13)') to (select from Animal where name = 'Dragon__((013)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((013)23)13)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((013)23)13)') to (select from Animal where name = 'Dragon__3')
create vertex Animal set name = 'Dragon__((((013)23)13)(013)4)', uuid = '156af458-6c4c-3935-379d-eda1ade6c5e9'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((013)23)13)(013)4)') to (select from Animal where name = 'Dragon__(((013)23)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((013)23)13)(013)4)') to (select from Animal where name = 'Dragon__(013)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((013)23)13)(013)4)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set name = 'Dragon__((((013)23)13)(013)2)', uuid = '5bc7fdeb-3123-4efe-6e64-80432aa50f4e'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((013)23)13)(013)2)') to (select from Animal where name = 'Dragon__(((013)23)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((013)23)13)(013)2)') to (select from Animal where name = 'Dragon__(013)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((013)23)13)(013)2)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set name = 'Dragon__((((013)23)13)((012)12)0)', uuid = '65e04993-7f41-1fed-1e70-e79933a1d1c2'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((013)23)13)((012)12)0)') to (select from Animal where name = 'Dragon__(((013)23)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((013)23)13)((012)12)0)') to (select from Animal where name = 'Dragon__((012)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((013)23)13)((012)12)0)') to (select from Animal where name = 'Dragon__0')
create vertex Animal set name = 'Dragon__(((((013)23)13)(013)4)02)', uuid = '1ac902ee-2577-7cf0-9f98-21883744da64'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((013)23)13)(013)4)02)') to (select from Animal where name = 'Dragon__((((013)23)13)(013)4)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((013)23)13)(013)4)02)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((013)23)13)(013)4)02)') to (select from Animal where name = 'Dragon__2')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__0') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__1') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__2') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__3') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__4') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(013)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(012)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((012)12)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((013)24)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((013)23)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((013)23)13)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((013)23)13)(013)4)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((013)23)13)(013)2)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((013)23)13)((012)12)0)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((013)23)13)(013)4)02)') to (select from Species where name = 'Dragon')
create vertex Animal set name = 'Hippogriff__0', uuid = '856f3d95-e0ae-1a1b-6c59-6216ae0fdbc8'
create vertex Animal set name = 'Hippogriff__1', uuid = 'd17034ce-5179-7350-e625-6403bf3df0bb'
create vertex Animal set name = 'Hippogriff__2', uuid = 'dfde2281-25fb-5f3d-866d-7002091472ad'
create vertex Animal set name = 'Hippogriff__3', uuid = 'd7a3283c-27e9-69e2-c8bf-23fb9a431f7a'
create vertex Animal set name = 'Hippogriff__4', uuid = '10fc9eee-0a17-27f7-ea5f-24b6de6fec4b'
create vertex Animal set name = 'Hippogriff__(012)', uuid = 'f8f8f071-d360-da69-6af7-9ad2993ec8c6'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(012)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(012)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(012)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set name = 'Hippogriff__((012)24)', uuid = 'cc4da021-dd62-0222-d9ef-e28b3bcb50b3'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((012)24)') to (select from Animal where name = 'Hippogriff__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((012)24)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((012)24)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__((012)04)', uuid = '552ae5ca-4124-405b-91fc-fe8881c16e98'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((012)04)') to (select from Animal where name = 'Hippogriff__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((012)04)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((012)04)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__(134)', uuid = 'cf5e9ea3-6258-4ab3-6877-7babc5c14262'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(134)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(134)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(134)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__((012)(134)0)', uuid = '5582a3bd-d476-fe38-babd-4745497e9f1a'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((012)(134)0)') to (select from Animal where name = 'Hippogriff__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((012)(134)0)') to (select from Animal where name = 'Hippogriff__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((012)(134)0)') to (select from Animal where name = 'Hippogriff__0')
create vertex Animal set name = 'Hippogriff__(((012)(134)0)14)', uuid = 'b799ae8e-9a1a-7d6f-dd02-e100e3d48408'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)(134)0)14)') to (select from Animal where name = 'Hippogriff__((012)(134)0)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)(134)0)14)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)(134)0)14)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__(((012)04)(134)1)', uuid = '775e0ec3-9c9d-03f3-0901-8aee69407be7'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)04)(134)1)') to (select from Animal where name = 'Hippogriff__((012)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)04)(134)1)') to (select from Animal where name = 'Hippogriff__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)04)(134)1)') to (select from Animal where name = 'Hippogriff__1')
create vertex Animal set name = 'Hippogriff__(((012)04)(012)1)', uuid = '9e0df45b-992a-34a1-084f-a819052daad3'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)04)(012)1)') to (select from Animal where name = 'Hippogriff__((012)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)04)(012)1)') to (select from Animal where name = 'Hippogriff__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)04)(012)1)') to (select from Animal where name = 'Hippogriff__1')
create vertex Animal set name = 'Hippogriff__(((012)24)(134)1)', uuid = 'e19b5837-1c6a-4b5e-7d85-9725c707aef9'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)24)(134)1)') to (select from Animal where name = 'Hippogriff__((012)24)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)24)(134)1)') to (select from Animal where name = 'Hippogriff__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)24)(134)1)') to (select from Animal where name = 'Hippogriff__1')
create vertex Animal set name = 'Hippogriff__(((012)04)((012)24)(134))', uuid = '306aa871-feef-71cb-c915-d113dc45488d'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)04)((012)24)(134))') to (select from Animal where name = 'Hippogriff__((012)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)04)((012)24)(134))') to (select from Animal where name = 'Hippogriff__((012)24)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((012)04)((012)24)(134))') to (select from Animal where name = 'Hippogriff__(134)')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__0') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__1') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__2') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__3') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__4') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(012)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((012)24)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((012)04)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(134)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((012)(134)0)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((012)(134)0)14)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((012)04)(134)1)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((012)04)(012)1)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((012)24)(134)1)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((012)04)((012)24)(134))') to (select from Species where name = 'Hippogriff')
