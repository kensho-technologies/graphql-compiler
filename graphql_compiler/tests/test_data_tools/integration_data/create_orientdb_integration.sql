# Copyright 2018-present Kensho Technologies, LLC.
create vertex Animal set name = 'Animal 1', net_worth = Decimal('100'), uuid = 'cfc6e625-8594-0927-468f-f53d864a7a51'
create vertex Animal set name = 'Animal 2', net_worth = Decimal('200'), uuid = 'cfc6e625-8594-0927-468f-f53d864a7a52'
create vertex Animal set name = 'Animal 3', net_worth = Decimal('300'), uuid = 'cfc6e625-8594-0927-468f-f53d864a7a53'
create vertex Animal set name = 'Animal 4', net_worth = Decimal('400'), uuid = 'cfc6e625-8594-0927-468f-f53d864a7a54'
create vertex Species set name = 'Species 1', uuid = 'ce4f0889-ecdb-4e27-8ffa-3140eb507549'
create vertex Species set name = 'Species 2', uuid = '660b4d07-37fe-4eeb-bb9f-fbc3845e35a9'
create edge out_Entity_Related from (select from Species where name = 'Species 1') to (select from Species where name = 'Species 2')
