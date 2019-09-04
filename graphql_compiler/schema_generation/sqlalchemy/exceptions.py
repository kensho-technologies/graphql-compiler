from ..exceptions import SchemaError


class InvalidSQLEdgeReferenceError(SchemaError):
    """Raised when a SQL edge references a non-existent vertex or column."""

class SQLEdgeTypeMismatchError(SchemaError):
    """Raised when a SQL edge suggests join capabilities between two columns with distinct types."""

class InvalidDialectError(SchemaError):
    """Raised when a column type is of a different dialect than the SQLAlchemySchemaInfo one."""

