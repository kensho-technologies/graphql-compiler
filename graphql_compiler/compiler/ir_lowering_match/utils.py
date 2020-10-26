# Copyright 2018-present Kensho Technologies, LLC.
from collections import namedtuple
import itertools
from typing import Callable, Collection, Dict, List, Optional, Set, Union

import six

from ...schema import is_vertex_field_name
from ..blocks import CoerceType, Filter
from ..expressions import (
    BinaryComposition,
    Expression,
    ExpressionT,
    GlobalContextField,
    Literal,
    LocalField,
    NullLiteral,
    TrueLiteral,
    UnaryTransformation,
    ZeroLiteral,
)
from ..helpers import Location, get_only_element_from_collection
from ..ir_lowering_common.common import SimpleOptionalLocationInfo
from ..metadata import QueryMetadataTable


def convert_coerce_type_to_instanceof_filter(coerce_type_block: CoerceType) -> Filter:
    """Create an "INSTANCEOF" Filter block from a CoerceType block."""
    coerce_type_target = get_only_element_from_collection(coerce_type_block.target_class)

    # INSTANCEOF requires the target class to be passed in as a string,
    # so we make the target class a string literal.
    new_predicate = BinaryComposition(
        "INSTANCEOF", LocalField("@this", None), Literal(coerce_type_target)
    )

    return Filter(new_predicate)


def convert_coerce_type_and_add_to_where_block(
    coerce_type_block: CoerceType, where_block: Filter
) -> Filter:
    """Create an "INSTANCEOF" Filter from a CoerceType, adding to an existing Filter if any."""
    instanceof_filter = convert_coerce_type_to_instanceof_filter(coerce_type_block)

    if where_block:
        # There was already a Filter block -- we'll merge the two predicates together.
        return Filter(BinaryComposition("&&", instanceof_filter.predicate, where_block.predicate))
    else:
        return instanceof_filter


def expression_list_to_conjunction(expression_list: Collection[Expression]) -> Expression:
    """Convert a list of expressions to an Expression that is the conjunction of all of them."""
    if not isinstance(expression_list, list):
        raise AssertionError("Expected `list`, Received {}.".format(expression_list))

    if len(expression_list) == 0:
        return TrueLiteral

    if not isinstance(expression_list[0], Expression):
        raise AssertionError(
            "Non-Expression object {} found in expression_list".format(expression_list[0])
        )
    if len(expression_list) == 1:
        return expression_list[0]
    else:
        return BinaryComposition(
            "&&", expression_list[0], expression_list_to_conjunction(expression_list[1:])
        )


class BetweenClause(Expression):
    """A `BETWEEN` Expression, constraining a field value to lie within a lower and upper bound."""

    def __init__(self, field: LocalField, lower_bound: Expression, upper_bound: Expression) -> None:
        """Construct an expression that is true when the field value is within the given bounds.

        Args:
            field: LocalField Expression, denoting the field in consideration
            lower_bound: lower bound constraint for given field
            upper_bound: upper bound constraint for given field

        Returns:
            a new BetweenClause object
        """
        super(BetweenClause, self).__init__(field, lower_bound, upper_bound)
        self.field = field
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.validate()

    def validate(self) -> None:
        """Validate that the Between Expression is correctly representable."""
        if not isinstance(self.field, LocalField):
            raise TypeError(
                "Expected LocalField field, got: {} {}".format(
                    type(self.field).__name__, self.field
                )
            )

        if not isinstance(self.lower_bound, Expression):
            raise TypeError(
                "Expected Expression lower_bound, got: {} {}".format(
                    type(self.lower_bound).__name__, self.lower_bound
                )
            )

        if not isinstance(self.upper_bound, Expression):
            raise TypeError(
                "Expected Expression upper_bound, got: {} {}".format(
                    type(self.upper_bound).__name__, self.upper_bound
                )
            )

    def visit_and_update(self, visitor_fn: Callable[[Expression], ExpressionT]) -> ExpressionT:
        """Create an updated version (if needed) of BetweenClause via the visitor pattern."""
        new_lower_bound = self.lower_bound.visit_and_update(visitor_fn)
        new_upper_bound = self.upper_bound.visit_and_update(visitor_fn)

        if new_lower_bound is not self.lower_bound or new_upper_bound is not self.upper_bound:
            return visitor_fn(BetweenClause(self.field, new_lower_bound, new_upper_bound))
        else:
            return visitor_fn(self)

    def to_match(self) -> str:
        """Return a unicode object with the MATCH representation of this BetweenClause."""
        template = "({field_name} BETWEEN {lower_bound} AND {upper_bound})"
        return template.format(
            field_name=self.field.to_match(),
            lower_bound=self.lower_bound.to_match(),
            upper_bound=self.upper_bound.to_match(),
        )


def filter_edge_field_non_existence(
    edge_expression: Union[LocalField, GlobalContextField]
) -> BinaryComposition:
    """Return an Expression that is True iff the specified edge (edge_expression) does not exist."""
    # When an edge does not exist at a given vertex, OrientDB represents that in one of two ways:
    #   - the edge's field does not exist (is null) on the vertex document, or
    #   - the edge's field does exist, but is an empty list.
    # We check both of these possibilities.
    if not isinstance(edge_expression, (LocalField, GlobalContextField)):
        raise AssertionError(
            "Received invalid edge_expression {} of type {}."
            "Expected LocalField or GlobalContextField.".format(
                edge_expression, type(edge_expression).__name__
            )
        )
    if isinstance(edge_expression, LocalField):
        if not is_vertex_field_name(edge_expression.field_name):
            raise AssertionError(
                "Received LocalField edge_expression {} with non-edge field_name "
                "{}.".format(edge_expression, edge_expression.field_name)
            )

    field_null_check = BinaryComposition("=", edge_expression, NullLiteral)

    local_field_size = UnaryTransformation("size", edge_expression)
    field_size_check = BinaryComposition("=", local_field_size, ZeroLiteral)

    return BinaryComposition("||", field_null_check, field_size_check)


def _filter_orientdb_simple_optional_edge(
    query_metadata_table: QueryMetadataTable,
    optional_edge_location: Location,
    inner_location: Location,
) -> BinaryComposition:
    """Return an Expression that is False for rows that don't follow the @optional specification.

    OrientDB does not filter correctly within optionals. Namely, a result where the optional edge
    DOES EXIST will be returned regardless of whether the inner filter is satisfed.
    To mitigate this, we add a final filter to reject such results.
    A valid result must satisfy either of the following:
    - The location within the optional exists (the filter will have been applied in this case)
    - The optional edge field does not exist at the root location of the optional traverse
    So, if the inner location within the optional was never visited, it must be the case that
    the corresponding edge field does not exist at all.

    Example:
        A MATCH traversal which starts at location `Animal___1`, and follows the optional edge
        `out_Animal_ParentOf` to the location `Animal__out_Animal_ParentOf___1`
        results in the following filtering Expression:
        (
            (
                (Animal___1.out_Animal_ParentOf IS null)
                OR
                (Animal___1.out_Animal_ParentOf.size() = 0)
            )
            OR
            (Animal__out_Animal_ParentOf___1 IS NOT null)
        )
        Here, the `optional_edge_location` is `Animal___1.out_Animal_ParentOf`.

    Args:
        query_metadata_table: QueryMetadataTable object containing all metadata collected during
                              query processing, including location metadata (e.g. which locations
                              are folded or optional).
        optional_edge_location: Location object representing the optional edge field
        inner_location: Location object within the corresponding optional traverse

    Returns:
        Expression that evaluates to False for rows that do not follow the @optional specification
    """
    location_info = query_metadata_table.get_location_info(inner_location)
    inner_location_name, _ = inner_location.get_location_name()
    inner_local_field = LocalField(inner_location_name, location_info.type)
    inner_location_existence = BinaryComposition("!=", inner_local_field, NullLiteral)

    # The optional_edge_location here is actually referring to the edge field itself.
    # This is definitely non-standard, but required to get the proper semantics.
    # To get its type, we construct the location of the vertex field on the other side of the edge.
    if optional_edge_location.field is None:
        raise AssertionError(
            f"optional_edge_location.field was unexpectedly set to None for "
            f"location {optional_edge_location}. This is a bug!"
        )
    vertex_location = optional_edge_location.at_vertex().navigate_to_subpath(
        optional_edge_location.field
    )
    location_type = query_metadata_table.get_location_info(vertex_location).type

    edge_context_field = GlobalContextField(optional_edge_location, location_type)
    edge_field_non_existence = filter_edge_field_non_existence(edge_context_field)

    return BinaryComposition("||", edge_field_non_existence, inner_location_existence)


def construct_where_filter_predicate(
    query_metadata_table: QueryMetadataTable,
    simple_optional_root_info: Dict[Location, SimpleOptionalLocationInfo],
) -> Expression:
    """Return an Expression that is True if and only if each simple optional filter is True.

    Construct filters for each simple optional, that are True if and only if `edge_field` does
    not exist in the `simple_optional_root_location` OR the `inner_location` is not defined.
    Return an Expression that evaluates to True if and only if *all* of the aforementioned filters
    evaluate to True (conjunction).

    Args:
        query_metadata_table: QueryMetadataTable object containing all metadata collected during
                              query processing, including location metadata (e.g. which locations
                              are folded or optional).
        simple_optional_root_info: dict mapping from simple_optional_root_location -> dict
                                   containing keys
                                   - 'inner_location': Location object correspoding to the
                                                       unique MarkLocation present within a
                                                       simple @optional (one that does not
                                                       expand vertex fields) scope
                                   - 'edge_field': string representing the optional edge being
                                                   traversed
                                   where simple_optional_root_to_inner_location is the location
                                   preceding the @optional scope
    Returns:
        a new Expression object
    """
    inner_location_name_to_where_filter: Dict[str, BinaryComposition] = {}
    for root_location, root_info_dict in six.iteritems(simple_optional_root_info):
        inner_location = root_info_dict["inner_location"]
        inner_location_name, _ = inner_location.get_location_name()
        edge_field = root_info_dict["edge_field"]

        optional_edge_location = root_location.navigate_to_field(edge_field)
        optional_edge_where_filter = _filter_orientdb_simple_optional_edge(
            query_metadata_table, optional_edge_location, inner_location
        )
        inner_location_name_to_where_filter[inner_location_name] = optional_edge_where_filter

    # Sort expressions by inner_location_name to obtain deterministic order
    where_filter_expressions = [
        inner_location_name_to_where_filter[key]
        for key in sorted(inner_location_name_to_where_filter.keys())
    ]

    return expression_list_to_conjunction(where_filter_expressions)


###
# A CompoundMatchQuery is a representation of several MatchQuery objects containing
#   - match_queries: a list MatchQuery objects
CompoundMatchQuery = namedtuple("CompoundMatchQuery", ("match_queries"))


class OptionalTraversalTree(object):
    def __init__(self, complex_optional_roots: List[Location]):
        """Initialize empty tree of optional root Locations (elements of complex_optional_roots).

        This object construst a tree of complex optional roots. These are locations preceding an
        @optional traverse that expand vertex fields within. Simple @optional traverses i.e.
        ones that do not expand vertex fields within them are excluded.

        Args:
            complex_optional_roots: list of @optional locations (location preceding an @optional
                                    traverse) that expand vertex fields within
        """
        self._location_to_children: Dict[Optional[Location], Set[Location]] = {
            optional_root_location: set() for optional_root_location in complex_optional_roots
        }
        self._root_location: Optional[Location] = None
        self._location_to_children[self._root_location] = set()

    def insert(self, optional_root_locations_path: List[Location]) -> None:
        """Insert a path of optional Locations into the tree.

        Each OptionalTraversalTree object contains child Location objects as keys mapping to
        other OptionalTraversalTree objects.

        Args:
            optional_root_locations_path: list of optional root Locations all except the last
                                          of which must be present in complex_optional_roots
        """
        encountered_simple_optional = False
        parent_location = self._root_location
        for optional_root_location in optional_root_locations_path:
            if encountered_simple_optional:
                raise AssertionError(
                    "Encountered simple optional root location {} in path, but"
                    "further locations are present. This should not happen: {}".format(
                        optional_root_location, optional_root_locations_path
                    )
                )

            if optional_root_location not in self._location_to_children:
                # Simple optionals are ignored.
                # There should be no complex optionals after a simple optional.
                encountered_simple_optional = True
            else:
                self._location_to_children[parent_location].add(optional_root_location)
                parent_location = optional_root_location

    def get_all_rooted_subtrees_as_lists(
        self, start_location: Optional[Location] = None
    ) -> List[List[Location]]:
        """Return a list of all rooted subtrees (each as a list of Location objects)."""
        if start_location is not None and start_location not in self._location_to_children:
            raise AssertionError(
                "Received invalid start_location {} that was not present "
                "in the tree. Present root locations of complex @optional "
                "queries (ones that expand vertex fields within) are: {}".format(
                    start_location, self._location_to_children.keys()
                )
            )

        if start_location is None:
            start_location = self._root_location

        if len(self._location_to_children[start_location]) == 0:
            # Node with no children only returns a singleton list containing the null set.
            return [[]]

        current_children = sorted(self._location_to_children[start_location])

        # Recursively find all rooted subtrees of each of the children of the current node.
        location_to_list_of_subtrees = {
            location: list(self.get_all_rooted_subtrees_as_lists(location))
            for location in current_children
        }

        # All subsets of direct child Location objects
        all_location_subsets = [
            list(subset)
            for subset in itertools.chain(
                *[
                    itertools.combinations(current_children, x)
                    for x in range(0, len(current_children) + 1)
                ]
            )
        ]

        # For every possible subset of the children, and every combination of the chosen
        # subtrees within, create a list of subtree Location lists.
        new_subtrees_as_lists: List[List[Location]] = []
        for location_subset in all_location_subsets:
            all_child_subtree_possibilities = [
                location_to_list_of_subtrees[location] for location in location_subset
            ]
            all_child_subtree_combinations = itertools.product(*all_child_subtree_possibilities)

            for child_subtree_combination in all_child_subtree_combinations:
                merged_child_subtree_combination = list(itertools.chain(*child_subtree_combination))
                new_subtree_as_list = location_subset + merged_child_subtree_combination
                new_subtrees_as_lists.append(new_subtree_as_list)

        return new_subtrees_as_lists


def construct_optional_traversal_tree(
    complex_optional_roots: List[Location],
    location_to_optional_roots: Dict[Location, List[Location]],
) -> OptionalTraversalTree:
    """Return a tree of complex optional root locations.

    Args:
        complex_optional_roots: list of @optional locations (location immmediately preceding
                                an @optional Traverse) that expand vertex fields
        location_to_optional_roots: dict mapping from location -> optional_roots where location is
                                    within some number of @optionals and optional_roots is a list
                                    of optional root locations preceding the successive @optional
                                    scopes within which the location resides

    Returns:
        OptionalTraversalTree object representing the tree of complex optional roots
    """
    tree = OptionalTraversalTree(complex_optional_roots)
    for optional_root_locations_stack in six.itervalues(location_to_optional_roots):
        tree.insert(list(optional_root_locations_stack))

    return tree
