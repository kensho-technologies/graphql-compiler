# Copyright 2018-present Kensho Technologies, LLC.
create vertex Animal set name = 'Animal 1', net_worth = Decimal('100'), uuid = 'cfc6e625-8594-0927-468f-f53d864a7a51'
create vertex Animal set name = 'Animal 2', net_worth = Decimal('200'), uuid = 'cfc6e625-8594-0927-468f-f53d864a7a52'
create vertex Animal set name = 'Animal 3', net_worth = Decimal('300'), uuid = 'cfc6e625-8594-0927-468f-f53d864a7a53'
create vertex Animal set name = 'Animal 4', net_worth = Decimal('400'), uuid = 'cfc6e625-8594-0927-468f-f53d864a7a54'
create vertex Location set name = 'Location 1', uuid = 'cfc6e625-8594-0927-468f-f53d864a7a55'
create vertex Location set name = 'Location 2', uuid = 'cfc6e625-8594-0927-468f-f53d864a7a56'
create vertex Location set name = 'Location 3', uuid = 'cfc6e625-8594-0927-468f-f53d864a7a57'
create vertex Location set name = 'Location 4', uuid = 'cfc6e625-8594-0927-468f-f53d864a7a58'
create edge Animal_LivesIn from (select from Animal where name = 'Animal 1') to (select from Location where name = 'Location 1')
create edge Animal_LivesIn from (select from Animal where name = 'Animal 2') to (select from Location where name = 'Location 2')
create edge Animal_LivesIn from (select from Animal where name = 'Animal 3') to (select from Location where name = 'Location 3')
create edge Animal_LivesIn from (select from Animal where name = 'Animal 4') to (select from Location where name = 'Location 4')
