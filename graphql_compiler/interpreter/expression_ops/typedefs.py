from typing import Any, Callable, Dict, Iterable, Tuple

from ...compiler.expressions import Expression
from ..typedefs import DataContext, DataToken, InterpreterAdapter


ExpressionEvaluatorFunc = Callable[
    [
        InterpreterAdapter[DataToken],
        Dict[str, Any],
        Expression,
        Iterable[DataContext]
    ],
    Iterable[Tuple[DataContext, Any]]
]
