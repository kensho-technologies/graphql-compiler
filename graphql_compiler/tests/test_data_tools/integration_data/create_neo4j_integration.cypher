# Copyright 2019-present Kensho Technologies, LLC.
# delete all leftover nodes from previous tests
match (n) detach delete n
create (:Animal {name: 'Animal 1', net_worth: toFloat('100'), uuid: 'cfc6e625-8594-0927-468f-f53d864a7a51'})
create (:Animal {name: 'Animal 2', net_worth: toFloat('200'), uuid: 'cfc6e625-8594-0927-468f-f53d864a7a52'})
create (:Animal {name: 'Animal 3', net_worth: toFloat('300'), uuid: 'cfc6e625-8594-0927-468f-f53d864a7a53'})
create (:Animal {name: 'Animal 4', net_worth: toFloat('400'), uuid: 'cfc6e625-8594-0927-468f-f53d864a7a54'})
create (:Species {name: 'Species 1', uuid: 'ce4f0889-ecdb-4e27-8ffa-3140eb507549'})
create (:Species {name: 'Species 2', uuid: '660b4d07-37fe-4eeb-bb9f-fbc3845e35a9'})
match (a:Species {name: 'Species 1'}), (b:Species {name: 'Species 2'}) create (a)-[:Entity_Related]->(b)
