# Copyright 2019-present Kensho Technologies, LLC.
from ..exceptions import SchemaError


class InvalidSQLEdgeReferenceError(SchemaError):
    """Raised when a SQL edge references a non-existent vertex or column."""
