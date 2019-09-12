# Copyright 2019-present Kensho Technologies, LLC.
class SchemaError(Exception):
    """Base class for all errors related to the schema."""


class InvalidClassError(SchemaError):
    """Raised when the requested class did not exist or fulfill certain requirements.

    Possible reasons include:
        - Class A was expected to be a subclass of class B, but that was found to not be the case.
        - The requested class was expected to be abstract, but it was not.
        - The requested class did not exist.

    In each of the cases, the conclusion is the same -- this is a programming error,
    and there is nothing the code can do to recover.
    """


class InvalidPropertyError(SchemaError):
    """Raised when a class was expected to have a given property that did not actually exist."""


class IllegalSchemaStateError(SchemaError):
    """Raised when the schema loaded from OrientDB is in an illegal state.

    When loading the OrientDB schema, we check various invariants. For example,
    we check that all non-abstract edge classes must define what types of vertices they connect.
    These invariants must hold during steady-state operation, but may sometimes be
    temporarily violated -- for example, during the process of applying new schema to the database.
    This exception is raised in such situations.

    Therefore, if the exception is raised during testing or during steady-state operation
    of the graph, it indicates a bug of some sort. If the exception is encountered during
    deploys or other activities that may cause schema changes to the database,
    it is probably ephemeral and the operation in question may be retried.
    """


class EmptySchemaError(SchemaError):
    """Raised when there are no visible vertex types to import into the GraphQL schema object."""


class InvalidSQLEdgeError(SchemaError):
    """Raised when a SQL edge provided during SQLAlchemySchemaInfo generation is invalid.

    This may be raised if the provided SQL edge refers to a non-existent vertex, or a non-exist
    column in a table. In the future, this class might encompass other sort of issues in
    specified SQL edges. For instance, it might be raised if an edge implies that we could execute
    a SQL join between two columns, but the columns have non-comparable types.
    """


class MissingPrimaryKeyError(SchemaError):
    """Raised when a SQLAlchemy Table object is missing a primary key.

    The compiler requires that each SQLAlchemy Table object in the SQLALchemySchemaInfo
    has a primary key. However, the primary key in the SQLAlchemy Table object need not be the
    primary key in the underlying table. It may simply be a non-null and unique identifier of each
    row.
    """
