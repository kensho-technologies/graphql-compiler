# Copyright 2019-present Kensho Technologies, LLC.
# Match query used to generate OrientDB records that are themselves used to generate GraphQL schema.
ORIENTDB_SCHEMA_RECORDS_QUERY = (
    'SELECT FROM (SELECT expand(classes) FROM metadata:schema) '
    'WHERE name NOT IN [\'ORole\', \'ORestricted\', \'OTriggered\', '
    '\'ORIDs\', \'OUser\', \'OIdentity\', \'OSchedule\', \'OFunction\']'
)
