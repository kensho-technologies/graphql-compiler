# Copyright 2019-present Kensho Technologies, LLC.
from ..exceptions import MissingPrimaryKeyError


def validate_that_tables_have_primary_keys(tables):
    """Validate that each SQLAlchemy Table object has a primary key."""
    tables_missing_primary_keys = set()
    for table in tables:
        if not table.primary_key:
            tables_missing_primary_keys.add(table)
    if tables_missing_primary_keys:
        error_message = (
            "At least one SQLAlchemy Table is missing a "
            "primary key. Note that the primary keys in SQLAlchemy "
            "Table objects do not have to match the primary keys in "
            "the underlying row. They must simply be unique and "
            "non-null identifiers of each row. The tables missing primary "
            "keys have names and schemas as follows: "
        )
        for table in tables_missing_primary_keys:
            error_message += "name: {} schema: {} ".format(table.name, table.schema)
        raise MissingPrimaryKeyError(error_message)


def validate_that_tables_belong_to_the_same_metadata_object(tables):
    """Validate that all the SQLAlchemy Table objects belong to the same MetaData object."""
    metadata = None
    for table in tables:
        if metadata is None:
            metadata = table.metadata
        else:
            if table.metadata is not metadata:
                raise AssertionError(
                    "Multiple SQLAlchemy MetaData objects used for schema generation."
                )
