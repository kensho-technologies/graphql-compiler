# Copyright 2018-present Kensho Technologies, LLC.
from typing import Callable, List, Tuple
import unittest

from graphql import GraphQLList, GraphQLString

from . import test_input_data
from ..compiler.compiler_frontend import graphql_to_ir
from ..compiler.helpers import BaseLocation, FoldScopeLocation, Location
from ..compiler.metadata import FilterInfo, OutputInfo, RecurseInfo
from ..global_utils import is_same_type
from ..schema import GraphQLDate, GraphQLDateTime
from .test_helpers import get_schema


class ExplainInfoTests(unittest.TestCase):
    """Ensure we get correct information about filters and recursion."""

    def setUp(self) -> None:
        """Initialize the test schema once for all tests."""
        self.schema = get_schema()

    def compare_output_info(self, expected: OutputInfo, received: OutputInfo) -> None:
        """Compare two OutputInfo objects, using proper GraphQL type comparison operators."""
        self.assertEqual(expected.location, received.location)
        self.assertTrue(is_same_type(expected.type, received.type))
        self.assertEqual(expected.optional, received.optional)

    def check(
        self,
        graphql_test: Callable[[], test_input_data.CommonTestData],
        expected_filter_list: List[Tuple[BaseLocation, List[FilterInfo]]],
        expected_recurse_list: List[Tuple[BaseLocation, List[RecurseInfo]]],
        expected_output_list: List[Tuple[str, OutputInfo]],
    ) -> None:
        """Verify query produces expected explain infos."""
        ir_and_metadata = graphql_to_ir(self.schema, graphql_test().graphql_input)
        meta = ir_and_metadata.query_metadata_table

        # Unfortunately literal dicts don't accept Location() as keys
        expected_filters = dict(expected_filter_list)
        expected_recurses = dict(expected_recurse_list)
        expected_outputs = dict(expected_output_list)

        for location, _ in meta.registered_locations:
            # Do filters match with expected for this location?
            filters = meta.get_filter_infos(location)
            self.assertEqual(expected_filters.get(location, []), filters)
            if filters:
                del expected_filters[location]
            # Do recurse match with expected for this location?
            recurse = meta.get_recurse_infos(location)
            self.assertEqual(expected_recurses.get(location, []), recurse)
            if recurse:
                del expected_recurses[location]

        for output_name, output_info in meta.outputs:
            # Does output info match with expected?
            self.assertIn(output_name, expected_outputs)
            self.compare_output_info(expected_outputs[output_name], output_info)
            if output_info:
                del expected_outputs[output_name]

        # Any expected infos missing?
        self.assertEqual(0, len(expected_filters))
        self.assertEqual(0, len(expected_recurses))
        self.assertEqual(0, len(expected_outputs))

    def test_immediate_output(self) -> None:
        out_name = "animal_name"
        out_info = OutputInfo(
            location=Location(("Animal",), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        self.check(test_input_data.immediate_output, [], [], [(out_name, out_info)])

    def test_output_source_and_complex_output(self) -> None:
        loc = Location(("Animal",), None, 1)
        filters = [
            FilterInfo(fields=("name",), op_name="=", args=("$wanted",)),
        ]

        out_name1 = "animal_name"
        out_info1 = OutputInfo(
            location=Location(("Animal",), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        out_name2 = "parent_name"
        out_info2 = OutputInfo(
            location=Location(("Animal", "out_Animal_ParentOf"), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        self.check(
            test_input_data.output_source_and_complex_output,
            [(loc, filters)],
            [],
            [(out_name1, out_info1), (out_name2, out_info2)],
        )

    def test_traverse_filter_and_output(self) -> None:
        loc = Location(("Animal", "out_Animal_ParentOf"), None, 1)
        filters = [
            FilterInfo(fields=("name", "alias"), op_name="name_or_alias", args=("$wanted",)),
        ]
        out_name = "parent_name"
        out_info = OutputInfo(
            location=Location(("Animal", "out_Animal_ParentOf"), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        self.check(
            test_input_data.traverse_filter_and_output, [(loc, filters)], [], [(out_name, out_info)]
        )

    def test_complex_optional_traversal_variables(self) -> None:
        loc1 = Location(("Animal",), None, 1)
        filters1 = [
            FilterInfo(fields=("name",), op_name="=", args=("$animal_name",)),
        ]

        loc2 = Location(("Animal", "in_Animal_ParentOf", "out_Animal_FedAt"), None, 1)
        filters2 = [
            FilterInfo(fields=("name",), op_name="=", args=("%parent_fed_at_event",)),
            FilterInfo(
                fields=("event_date",),
                op_name="between",
                args=("%other_child_fed_at", "%parent_fed_at"),
            ),
        ]
        out_name1 = "parent_fed_at"
        out_loc1 = Location(("Animal", "out_Animal_ParentOf", "out_Animal_FedAt"), "event_date", 1)
        out_info1 = OutputInfo(
            location=out_loc1,
            type=GraphQLDateTime,
            optional=True,
        )

        out_name2 = "other_child_fed_at"
        out_loc2 = Location(
            ("Animal", "out_Animal_ParentOf", "in_Animal_ParentOf", "out_Animal_FedAt"),
            "event_date",
            1,
        )
        out_info2 = OutputInfo(
            location=out_loc2,
            type=GraphQLDateTime,
            optional=True,
        )

        out_name3 = "grandchild_fed_at"
        out_loc3 = Location(("Animal", "in_Animal_ParentOf", "out_Animal_FedAt"), "event_date", 1)
        out_info3 = OutputInfo(
            location=out_loc3,
            type=GraphQLDateTime,
            optional=False,
        )

        self.check(
            test_input_data.complex_optional_traversal_variables,
            [(loc1, filters1), (loc2, filters2)],
            [],
            [(out_name1, out_info1), (out_name2, out_info2), (out_name3, out_info3)],
        )

    def test_coercion_filters_and_multiple_outputs_within_fold_scope(self) -> None:
        loc = FoldScopeLocation(Location(("Animal",), None, 1), (("out", "Entity_Related"),), None)
        filters = [
            FilterInfo(fields=("name",), op_name="has_substring", args=("$substring",)),
            FilterInfo(fields=("birthday",), op_name="<=", args=("$latest",)),
        ]

        out_name1 = "name"
        out_info1 = OutputInfo(
            location=Location(("Animal",), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        out_name2 = "related_animals"
        out_loc2 = FoldScopeLocation(
            Location(("Animal",), None, 1), (("out", "Entity_Related"),), "name"
        )
        out_info2 = OutputInfo(
            location=out_loc2,
            type=GraphQLList(GraphQLString),
            optional=False,
        )

        out_name3 = "related_birthdays"
        out_loc3 = FoldScopeLocation(
            Location(("Animal",), None, 1), (("out", "Entity_Related"),), "birthday"
        )
        out_info3 = OutputInfo(
            location=out_loc3,
            type=GraphQLList(GraphQLDate),
            optional=False,
        )

        self.check(
            test_input_data.coercion_filters_and_multiple_outputs_within_fold_scope,
            [(loc, filters)],
            [],
            [(out_name1, out_info1), (out_name2, out_info2), (out_name3, out_info3)],
        )

    def test_multiple_filters(self) -> None:
        loc = Location(("Animal",), None, 1)
        filters = [
            FilterInfo(fields=("name",), op_name=">=", args=("$lower_bound",)),
            FilterInfo(fields=("name",), op_name="<", args=("$upper_bound",)),
        ]

        out_name = "animal_name"
        out_info = OutputInfo(
            location=Location(("Animal",), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        self.check(test_input_data.multiple_filters, [(loc, filters)], [], [(out_name, out_info)])

    def test_has_edge_degree_op_filter(self) -> None:
        loc = Location(("Animal",), None, 1)
        filters = [
            FilterInfo(
                fields=("in_Animal_ParentOf",), op_name="has_edge_degree", args=("$child_count",)
            )
        ]

        out_name1 = "animal_name"
        out_info1 = OutputInfo(
            location=Location(("Animal",), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        out_name2 = "child_name"
        out_info2 = OutputInfo(
            location=Location(("Animal", "in_Animal_ParentOf"), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        self.check(
            test_input_data.has_edge_degree_op_filter,
            [(loc, filters)],
            [],
            [(out_name1, out_info1), (out_name2, out_info2)],
        )

    def test_simple_recurse(self) -> None:
        loc = Location(("Animal",), None, 1)
        recurses = [RecurseInfo(edge_direction="out", edge_name="Animal_ParentOf", depth=1)]

        out_name = "relation_name"
        out_info = OutputInfo(
            location=Location(("Animal", "out_Animal_ParentOf"), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        self.check(test_input_data.simple_recurse, [], [(loc, recurses)], [(out_name, out_info)])

    def test_two_consecutive_recurses(self) -> None:
        loc = Location(("Animal",), None, 1)
        filters = [
            FilterInfo(
                fields=("name", "alias"), op_name="name_or_alias", args=("$animal_name_or_alias",)
            )
        ]
        recurses = [
            RecurseInfo(edge_direction="out", edge_name="Animal_ParentOf", depth=2),
            RecurseInfo(edge_direction="in", edge_name="Animal_ParentOf", depth=2),
        ]

        out_name1 = "animal_name"
        out_info1 = OutputInfo(
            location=Location(("Animal",), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        out_name2 = "important_event"
        out_info2 = OutputInfo(
            location=Location(("Animal", "out_Animal_ImportantEvent"), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        out_name3 = "ancestor_name"
        out_info3 = OutputInfo(
            location=Location(("Animal", "out_Animal_ParentOf"), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        out_name4 = "descendent_name"
        out_info4 = OutputInfo(
            location=Location(("Animal", "in_Animal_ParentOf"), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        expected_outputs = [
            (out_name1, out_info1),
            (out_name2, out_info2),
            (out_name3, out_info3),
            (out_name4, out_info4),
        ]

        self.check(
            test_input_data.two_consecutive_recurses,
            [(loc, filters)],
            [(loc, recurses)],
            expected_outputs,
        )

    def test_filter_on_optional_traversal_name_or_alias(self) -> None:
        loc = Location(("Animal", "out_Animal_ParentOf"), None, 1)
        filters = [
            FilterInfo(
                fields=("name", "alias"), op_name="name_or_alias", args=("%grandchild_name",)
            )
        ]

        out_name = "parent_name"
        out_info = OutputInfo(
            location=Location(("Animal", "out_Animal_ParentOf"), "name", 1),
            type=GraphQLString,
            optional=False,
        )

        self.check(
            test_input_data.filter_on_optional_traversal_name_or_alias,
            [(loc, filters)],
            [],
            [(out_name, out_info)],
        )
