from typing import Any, Callable, Dict, Iterable, Iterator, Tuple

from ...compiler.expressions import Expression
from ...compiler.metadata import QueryMetadataTable
from ..typedefs import DataContext, DataToken, InterpreterAdapter


ExpressionEvaluatorFunc = Callable[
    [
        InterpreterAdapter[DataToken],
        QueryMetadataTable,
        Dict[str, Any],
        str,
        Expression,
        Iterable[DataContext],
    ],
    Iterator[Tuple[DataContext, Any]],
]
