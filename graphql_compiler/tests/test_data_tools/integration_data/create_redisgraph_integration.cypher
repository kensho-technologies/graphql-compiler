# Copyright 2019-present Kensho Technologies, LLC.
# This data is almost identical to the neo4j integration test data except for the first line, which doesn't appear in
# the neo4j data:
create (n)
# The Redisgraph DB doesn't exist until we create a node, but doesn't go away if we delete all the nodes in the graph.
# Now we can remove all the old data that might be in the DB.
# Refer to Github issue: https://github.com/RedisGraph/RedisGraph/issues/551
match (n) delete n

# The other difference is that Redisgraph doesn't support toFloat (and other casting functions) so those are removed.
create (:Animal {name: 'Animal 1', net_worth: 100.0, uuid: 'cfc6e625-8594-0927-468f-f53d864a7a51'})
create (:Animal {name: 'Animal 2', net_worth: 200.0, uuid: 'cfc6e625-8594-0927-468f-f53d864a7a52'})
create (:Animal {name: 'Animal 3', net_worth: 300.0, uuid: 'cfc6e625-8594-0927-468f-f53d864a7a53'})
create (:Animal {name: 'Animal 4', net_worth: 400.0, uuid: 'cfc6e625-8594-0927-468f-f53d864a7a54'})
create (:Species {name: 'Species 1', uuid: 'ce4f0889-ecdb-4e27-8ffa-3140eb507549'})
create (:Species {name: 'Species 2', uuid: '660b4d07-37fe-4eeb-bb9f-fbc3845e35a9'})
match (a:Species {name: 'Species 1'}), (b:Species {name: 'Species 2'}) create (a)-[:Entity_Related]->(b)
