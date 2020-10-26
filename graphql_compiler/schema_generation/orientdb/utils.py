# Copyright 2019-present Kensho Technologies, LLC.

# Match query used to generate OrientDB records that are themselves used to generate GraphQL schema.
ORIENTDB_SCHEMA_RECORDS_QUERY = (
    "SELECT FROM (SELECT expand(classes) FROM metadata:schema) "
    "WHERE name NOT IN ['ORole', 'ORestricted', 'OTriggered', "
    "'ORIDs', 'OUser', 'OIdentity', 'OSchedule', 'OFunction']"
)

ORIENTDB_INDEX_RECORDS_QUERY = (
    "SELECT name, type, indexDefinition, metadata FROM ("
    "SELECT expand(indexes) FROM metadata:indexmanager"
    ") WHERE type IN "
    "['UNIQUE', 'NOTUNIQUE', 'UNIQUE_HASH_INDEX', 'NOTUNIQUE_HASH_INDEX']"
)
