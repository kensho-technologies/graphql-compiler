# Copyright 2019-present Kensho Technologies, LLC.
from dataclasses import dataclass
from typing import Generic, Tuple, TypeVar

from ..global_utils import ASTWithParameters, QueryStringWithParameters


QueryBundle = TypeVar("QueryBundle", QueryStringWithParameters, ASTWithParameters)


@dataclass
class PageAndRemainder(Generic[QueryBundle]):
    page: QueryBundle
    remainder: Tuple[QueryBundle, ...]
