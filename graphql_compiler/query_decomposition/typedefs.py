@dataclass(frozen=True)
class Filter:
    field: str
    operator: str
    value: str

@dataclass(frozen=True)
class Node:

    # TODO make sure samples are sorted by primary key columns.
    # - Y tho? What if we're joining to this edge via non-primary column?
    #   - Maybe because the primary key could be sequential
    # - Actually the sorting key can only change precision.
    samples: Samples
    primary_key: Tuple[str]
    filters: List[Any]

@dataclass(frozen=True)
class JoinProtocol:
    from_columns: List[str]
    to_columns: List[str]
    optional: bool
    recurse_depth: Optional[int]

    def __post_init__(self) -> None:
        """Validate fields."""
        pass

@dataclass(frozen=True)
class BoundedQuery:
    root: Node
    extensions: "List[Tuple(JoinProtocol, BoundedQuery)]"


@dataclass(frozen=True)
class UnboundedQueryEvidence:
    problems: List[Tuple(Span, Problem)]

@dataclass(frozen=True)
class UnboundedByExpandingNodes(UnboundedQueryEvidence):
    expanding_nodes: List[Any]

@dataclass(frozen=True)
class UnboundedByOptionalRoot(UnboundedQueryEvidence):
    optional_location: Any


# TODO what else do I need in the inputs?
# 1. Samples for each table involved, or Statistics object with get_samples function
# 2. Should I do validation here? Why not reuse metadata table?
#
# 1. analysis.types
# 2. analysis.fold-scope-roots
BoundedRepresentationAttempt = Union[BoundedQuery, UnboundedQueryEvidence]
def try_express_as_bounded_query(query: ASTWithParameters) -> BoundedExpressionAttempt:
    raise NotImplementedError("...")


@dataclass(frozen=True)
class BoundedSubqueryDecomposition:
    root: BoundedQuery
    expansions: "List[Tuple(Traversal, BoundedQuery)]"

def decompose_to_bounded_subqueries(query: ASTWithParameters) -> BoundedSubqueryDecomposition:
    raise NotImplementedError("...")
