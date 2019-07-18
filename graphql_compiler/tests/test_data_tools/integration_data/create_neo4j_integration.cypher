# Copyright 2019-present Kensho Technologies, LLC.
# delete all leftover nodes from previous tests
match (n) detach delete n
# Neo4j supports temporal types but Redisgraph doesn't. As a result, the birthday field doesn't
# exist in create_rediisgraph_integration.cypher.
create (:Animal {name: 'Animal 1', net_worth: 100.0, uuid: 'cfc6e625-8594-0927-468f-f53d864a7a51', birthday: DATE('1900-01-01')})
create (:Animal {name: 'Animal 2', net_worth: 200.0, uuid: 'cfc6e625-8594-0927-468f-f53d864a7a52', birthday: DATE('1950-02-02')})
create (:Animal {name: 'Animal 3', net_worth: 300.0, uuid: 'cfc6e625-8594-0927-468f-f53d864a7a53', birthday: DATE('1975-03-03')})
create (:Animal {name: 'Animal 4', net_worth: 400.0, uuid: 'cfc6e625-8594-0927-468f-f53d864a7a54', birthday: DATE('2000-04-04')})
create (:Species {name: 'Species 1', uuid: 'ce4f0889-ecdb-4e27-8ffa-3140eb507549'})
create (:Species {name: 'Species 2', uuid: '660b4d07-37fe-4eeb-bb9f-fbc3845e35a9'})
match (a:Species {name: 'Species 1'}), (b:Species {name: 'Species 2'}) create (a)-[:Entity_Related]->(b)
