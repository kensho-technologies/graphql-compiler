# Copyright 2018-present Kensho Technologies, LLC.
"""Transform a tree representation of an SQL query into an executable SQLAlchemy query."""


def emit_code_from_ir(sql_query_tree, compiler_metadata):
    """Return a SQLAlchemy Query from a passed tree representation of an SQL query."""
    raise NotImplementedError(u'SQL query emitting is not yet supported.')
