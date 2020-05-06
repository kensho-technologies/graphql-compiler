# Copyright 2019-present Kensho Technologies, LLC.
from typing import Iterable, List, Set

from sqlalchemy import Table

from ..exceptions import MissingPrimaryKeyError


def validate_that_tables_have_primary_keys(tables: Iterable[Table]) -> None:
    """Validate that each SQLAlchemy Table object has a primary key."""
    tables_missing_primary_keys: Set[Table] = set()
    for table in tables:
        if not table.primary_key:
            tables_missing_primary_keys.add(table)
    if tables_missing_primary_keys:
        error_message: str = (
            "At least one SQLAlchemy Table is missing a "
            "primary key. Note that the primary keys in SQLAlchemy "
            "Table objects do not have to match the primary keys in "
            "the underlying row. They must simply be unique and "
            "non-null identifiers of each row. The tables missing primary "
            "keys have names and schemas as follows: "
        )
        faulty_tables: List[str] = [
            "name: {} schema: {}".format(table.name, table.schema)
            for table in tables_missing_primary_keys
        ]
        error_message += " ".join(faulty_tables)
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
