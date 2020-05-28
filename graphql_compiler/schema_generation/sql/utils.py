# Copyright 2019-present Kensho Technologies, LLC.
from typing import Iterable, Set

from sqlalchemy import Table

from ..exceptions import MissingPrimaryKeyError


def validate_that_tables_have_primary_keys(tables: Iterable[Table]) -> None:
    """Validate that each SQLAlchemy Table object has a primary key."""
    tables_missing_primary_keys: Set[str] = set()
    for table in tables:
        if not table.primary_key:
            tables_missing_primary_keys.add(table.fullname)
    if tables_missing_primary_keys:
        raise MissingPrimaryKeyError(
            "At least one SQLAlchemy Table is missing a "
            "primary key. Note that the primary keys in SQLAlchemy "
            "Table objects do not have to match the primary keys in "
            "the underlying row. They must simply be unique and "
            f"non-null identifiers of each row. Tables missing primary keys: "
            f"{tables_missing_primary_keys}"
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
                    "Multiple SQLAlchemy MetaData objects used for schema generation."
                )
