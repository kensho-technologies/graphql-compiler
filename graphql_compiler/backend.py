from compiler import (
    emit_cypher, emit_gremlin, emit_match, emit_sql, ir_lowering_cypher, ir_lowering_gremlin,
    ir_lowering_match, ir_lowering_sql
)
from compiler.compiler_frontend import graphql_to_ir

from schema import schema_info


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

    # Given a connection pool and a query in this language, run the query with retries
    # and return the results.
    'run_func',

    # An instance of SchemaInfoClass whose schema is the test_schema.
    'test_schema_info',

    # Given a SchemaInfo and a connection pool to a database, modify the database such
    # that the schema_inspector will be able to reconstruct the same schema.
    'setup_schema'

    # Given a SchemaInfo, a Data, and a connection pool to a database with the same schema,
    # modify the database such that the data_inspector will reconstruct the same data.
    'setup_data'
))


gremlin_backend = Backend(
    language='Gremlin'
    schemaInfoClass=schema_info.CommonSchemaInfo,
    lower_func=ir_lowering_gremlin.lower_ir,
    emit_func=emit_gremlin.emit_code_from_ir,
    test_schema_info=NotImplementedError(),
    setup_schema=NotImplementedError(),
    setup_data=NotImplementedError(),
)

match_backend = Backend(
    language='MATCH'
    schemaInfoClass=schema_info.CommonSchemaInfo,
    lower_func=ir_lowering_match.lower_ir,
    emit_func=emit_match.emit_code_from_ir,
    test_schema_info=NotImplementedError(),
    setup_schema=NotImplementedError(),
    setup_data=NotImplementedError(),
)

cypher_backend = Backend(
    language='Cypher'
    schemaInfoClass=schema_info.CommonSchemaInfo,
    lower_func=ir_lowering_cypher.lower_ir,
    emit_func=emit_cypher.emit_code_from_ir,
    test_schema_info=NotImplementedError(),
    setup_schema=NotImplementedError(),
    setup_data=NotImplementedError(),
)

sql_backend = Backend(
    language='SQL',
    schemaInfoClass=schema_info.SqlAlchemySchemaInfo,
    lower_func=ir_lowering_sql.lower_ir,
    emit_func=emit_sql.emit_sql,
    test_schema_info=get_sqlalchemy_schema_info(),
    setup_schema=NotImplementedError(),
    setup_data=NotImplementedError(),
)
