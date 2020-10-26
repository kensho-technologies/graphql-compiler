# Copyright 2019-present Kensho Technologies, LLC.
from dataclasses import dataclass
from typing import Generic, Tuple, TypeVar

from ..global_utils import ASTWithParameters, QueryStringWithParameters


# A representation of a query and its arguments, convenient for a particular use-case.
QueryBundle = TypeVar("QueryBundle", QueryStringWithParameters, ASTWithParameters)


@dataclass
class PageAndRemainder(Generic[QueryBundle]):
    """The result of pagination."""

    # A query
    whole_query: QueryBundle

    # Desired page size
    page_size: int

    # A query containing a single page of results of the whole_query
    one_page: QueryBundle

    # A list of queries, that are disjoint with one_page and mutually disjoint, such
    # that the union of the one_page and remainder queries describes the whole_query.
    # If the whole_query already fits within a page, the remainder is an empty tuple.
    # If not, the remainder is nonempty, usually containing one query. The remainder
    # contains more than one query when multiple pagination filters are used in the
    # query plan. In that case, it is impossible to describe the remainder with a
    # single query.
    remainder: Tuple[QueryBundle, ...]
