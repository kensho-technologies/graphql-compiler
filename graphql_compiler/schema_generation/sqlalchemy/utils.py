# Copyright 2019-present Kensho Technologies, LLC.
from ..exceptions import MissingPrimaryKeyError


def validate_that_tables_have_primary_keys(tables):
    """Validate that each SQLAlchemy Table object has a primary key."""
    for table in tables:
        if not table.primary_key:
            raise MissingPrimaryKeyError(
                "SQLAlchemy Table with name {} and schema {} is missing a "
                "primary key. Note that the primary keys in SQLAlchemy "
                "Table objects do not have to match the primary keys in"
                "the underlying row. They must simple be unique and "
                "non-null identifiers of each row.".format(table.name, table.schema)
            )


def validate_that_tables_belong_to_the_same_metadata_object(tables):
    """Validate that all the SQLAlchemy Table objects belong to the same MetaData object."""
    metadata = None
    for table in tables:
        if metadata is None:
            metadata = table.metadata
        else:
            if table.metadata is not metadata:
                raise AssertionError(
                    "Multiple SQLAlchemy MetaData objects used for schema " "generation."
                )
