from typing import Any, Callable, Dict, Iterable, Iterator, Optional, Tuple

from ...compiler.expressions import Expression
from ...compiler.helpers import Location
from ...compiler.metadata import QueryMetadataTable
from ..typedefs import DataContext, DataToken, InterpreterAdapter


ExpressionEvaluatorFunc = Callable[
    [
        InterpreterAdapter[DataToken],
        QueryMetadataTable,
        Dict[str, Any],
        Optional[Location],
        Expression,
        Iterable[DataContext],
    ],
    Iterator[Tuple[DataContext, Any]],
]
