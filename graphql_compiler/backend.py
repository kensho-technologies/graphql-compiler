# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

import sqlalchemy

from .compiler import (
    emit_cypher, emit_gremlin, emit_match, emit_sql, ir_lowering_cypher, ir_lowering_gremlin,
    ir_lowering_match, ir_lowering_sql
)
from .query_running import run_sql_query
from .schema import schema_info


# A backend is a compilation target (a language we can compile to)
#
# This class defines all the necessary and sufficient functionality a backend should implement
# in order to fit into our generic testing framework.
Backend = namedtuple('Backend', (
    # String, the internal name of this language.
    'language',

    # The subclass of SchemaInfo appropriate for this backend.
    'SchemaInfoClass',

    # Given a SchemaInfoClass and an IR that respects its schema, return a lowered IR with
    # the same semantics.
    'lower_func',

    # Given a SchemaInfoClass and a lowered IR that respects its schema, emit a query
    # in this language with the same semantics.
    'emit_func',

    # The type of object sufficient to make databse calls with retries.
    'ConnectionPoolClass',

    # Given a ConnectionPoolClass, a compilation result and query parameters, return a
    # result formatted as a list of dicts.
    'run_func',
))


gremlin_backend = Backend(
    language='Gremlin',
    SchemaInfoClass=schema_info.CommonSchemaInfo,
    lower_func=ir_lowering_gremlin.lower_ir,
    emit_func=emit_gremlin.emit_code_from_ir,
    ConnectionPoolClass=NotImplementedError,
    run_func=NotImplementedError,
)

match_backend = Backend(
    language='MATCH',
    SchemaInfoClass=schema_info.CommonSchemaInfo,
    lower_func=ir_lowering_match.lower_ir,
    emit_func=emit_match.emit_code_from_ir,
    ConnectionPoolClass=NotImplementedError,
    run_func=NotImplementedError,
)

cypher_backend = Backend(
    language='Cypher',
    SchemaInfoClass=schema_info.CommonSchemaInfo,
    lower_func=ir_lowering_cypher.lower_ir,
    emit_func=emit_cypher.emit_code_from_ir,
    ConnectionPoolClass=NotImplementedError,
    run_func=NotImplementedError,
)

sql_backend = Backend(
    language='SQL',
    SchemaInfoClass=schema_info.SQLAlchemySchemaInfo,
    lower_func=ir_lowering_sql.lower_ir,
    emit_func=emit_sql.emit_code_from_ir,
    ConnectionPoolClass=sqlalchemy.engine.Engine,
    run_func=run_sql_query,
)
