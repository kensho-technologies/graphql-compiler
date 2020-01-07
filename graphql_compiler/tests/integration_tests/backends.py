# Copyright 2018-present Kensho Technologies, LLC.

POSTGRES = u"postgresql"
MYSQL = u"mysql"
MARIADB = u"mariadb"
MSSQL = u"mssql"
SQLITE = u"sqlite"
ORIENTDB = u"orientdb"
NEO4J = u"neo4j"
REDISGRAPH = u"redisgraph"


SQL_BACKENDS = {
    POSTGRES,
    MYSQL,
    MARIADB,
    MSSQL,
    SQLITE,
}

MATCH_BACKENDS = {
    ORIENTDB,
}

# Split Neo4j and RedisGraph because RedisGraph doesn't support all Neo4j features.
NEO4J_BACKENDS = {
    NEO4J,
}

REDISGRAPH_BACKENDS = {
    REDISGRAPH,
}

# TODO: Add integration tests for all supported backends.
BACKENDS_TO_TEST = [
    ORIENTDB,
    MSSQL,
    NEO4J,
    REDISGRAPH,
]
