# Copyright 2018-present Kensho Technologies, LLC.
import unittest

from . import test_input_data
from ..compiler.compiler_frontend import graphql_to_ir
from ..compiler.helpers import Location
from ..compiler.metadata import FilterInfo, RecurseInfo
from .test_helpers import get_schema


class ExplainInfoTests(unittest.TestCase):
    """Ensure we get correct information about filters and recursion."""

    def setUp(self):
        """Initialize the test schema once for all tests."""
        self.schema = get_schema()

    def check(self, graphql_test, expected_filters, expected_recurses):
        """Verify query produces expected explain infos."""
        ir_and_metadata = graphql_to_ir(self.schema, graphql_test().graphql_input)
        meta = ir_and_metadata.query_metadata_table
        # Unfortunately literal dicts don't accept Location() as keys
        expected_filters = dict(expected_filters)
        expected_recurses = dict(expected_recurses)
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
        # Any expected infos missing?
        self.assertEqual(0, len(expected_filters))
        self.assertEqual(0, len(expected_recurses))

    def test_traverse_filter_and_output(self):
        loc = Location(('Animal', 'out_Animal_ParentOf'), None, 1)
        filters = [
            FilterInfo(fields=('name', 'alias'), op_name='name_or_alias', args=('$wanted',)),
        ]

        self.check(test_input_data.traverse_filter_and_output,
                   [(loc, filters)],
                   [])

    def test_complex_optional_traversal_variables(self):
        loc1 = Location(('Animal',), None, 1)
        filters1 = [
            FilterInfo(fields=('name',), op_name='=', args=('$animal_name',)),
        ]

        loc2 = Location(('Animal', 'in_Animal_ParentOf', 'out_Animal_FedAt'), None, 1)
        filters2 = [
            FilterInfo(fields=('name',), op_name='=', args=('%parent_fed_at_event',)),
            FilterInfo(fields=('event_date',),
                       op_name='between',
                       args=('%other_child_fed_at', '%parent_fed_at')),
        ]

        self.check(test_input_data.complex_optional_traversal_variables,
                   [(loc1, filters1), (loc2, filters2)],
                   [])

    def test_coercion_filters_and_multiple_outputs_within_fold_scope(self):
        self.check(test_input_data.coercion_filters_and_multiple_outputs_within_fold_scope,
                   [],
                   [])

    def test_multiple_filters(self):
        loc = Location(('Animal',), None, 1)
        filters = [
            FilterInfo(fields=('name',), op_name='>=', args=('$lower_bound',)),
            FilterInfo(fields=('name',), op_name='<', args=('$upper_bound',))
        ]

        self.check(test_input_data.multiple_filters,
                   [(loc, filters)],
                   [])

    def test_has_edge_degree_op_filter(self):
        loc = Location(('Animal',), None, 1)
        filters = [
            FilterInfo(fields=('in_Animal_ParentOf',),
                       op_name='has_edge_degree',
                       args=('$child_count',))
        ]

        self.check(test_input_data.has_edge_degree_op_filter,
                   [(loc, filters)],
                   [])

    def test_simple_recurse(self):
        loc = Location(('Animal',), None, 1)
        recurses = [
            RecurseInfo(edge_direction='out', edge_name='Animal_ParentOf', depth=1)
        ]

        self.check(test_input_data.simple_recurse,
                   [],
                   [(loc, recurses)])

    def test_two_consecutive_recurses(self):
        loc = Location(('Animal',), None, 1)
        filters = [
            FilterInfo(fields=('name', 'alias'),
                       op_name='name_or_alias',
                       args=('$animal_name_or_alias',))
        ]
        recurses = [
            RecurseInfo(edge_direction='out', edge_name='Animal_ParentOf', depth=2),
            RecurseInfo(edge_direction='in', edge_name='Animal_ParentOf', depth=2)
        ]

        self.check(test_input_data.two_consecutive_recurses,
                   [(loc, filters)],
                   [(loc, recurses)])

    def test_filter_on_optional_traversal_name_or_alias(self):
        loc = Location(('Animal', 'out_Animal_ParentOf'), None, 1)
        filters = [
            FilterInfo(fields=('name', 'alias'),
                       op_name='name_or_alias',
                       args=('%grandchild_name',))
        ]

        self.check(test_input_data.filter_on_optional_traversal_name_or_alias,
                   [(loc, filters)],
                   [])
