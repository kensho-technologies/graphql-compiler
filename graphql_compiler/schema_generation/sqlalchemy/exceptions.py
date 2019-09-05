# Copyright 2019-present Kensho Technologies, LLC.
from ..exceptions import SchemaError


class InvalidSQLEdgeReferenceError(SchemaError):
    """Raised when a SQL edge references a non-existent vertex or column."""


class SQLEdgeTypeMismatchError(SchemaError):
    """Raised when a SQL edge suggests join capabilities between two columns with distinct types."""


class SQLNameConflictError(SchemaError):
    """Raised when the are names conflicts between SQL edges and vertices."""
