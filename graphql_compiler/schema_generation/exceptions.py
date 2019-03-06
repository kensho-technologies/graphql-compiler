# Copyright 2019-present Kensho Technologies, LLC.
class SchemaError(Exception):
    """Base class for all errors related to the schema."""


class InvalidClassError(SchemaError):
    """Raised for two reasons, disambiguated by their message:

        - Class A was expected to be a subclass of class B, but that was found to not be the case.
        - The requested class did not exist.

    In either case, the conclusion is the same -- this is a programming error,
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
