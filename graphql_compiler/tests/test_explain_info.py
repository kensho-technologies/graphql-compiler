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
            self.assertEqual(filters, expected_filters.get(location, []))
            if filters:
                del expected_filters[location]
            # Do recurse match with expected for this location?
            recurse = meta.get_recurse_info(location)
            self.assertEqual(recurse, expected_recurses.get(location, None))
            if recurse:
                del expected_recurses[location]
        # Any expected infos missing?
        self.assertEqual(0, len(expected_filters))
        self.assertEqual(0, len(expected_recurses))

    def test_filter(self):
        self.check(test_input_data.traverse_filter_and_output,
                   [
                       (Location(('Animal', 'out_Animal_ParentOf'), None, 1),
                        [FilterInfo(field_name='out_Animal_ParentOf',
                                    op_name='name_or_alias',
                                    args=['$wanted'])]),
                   ],
                   [
                   ])

    def test_filters(self):
        self.check(test_input_data.complex_optional_traversal_variables,
                   [
                       (Location(('Animal',), None, 1),
                        [FilterInfo(field_name='name',
                                    op_name='=',
                                    args=['$animal_name'])]),
                       (Location(('Animal', 'in_Animal_ParentOf', 'out_Animal_FedAt'), None, 1),
                        [FilterInfo(field_name='name',
                                    op_name='=',
                                    args=['%parent_fed_at_event']),
                         FilterInfo(field_name='event_date',
                                    op_name='between',
                                    args=['%other_child_fed_at', '%parent_fed_at'])]),
                   ],
                   [
                   ])

    def test_fold(self):
        self.check(test_input_data.coercion_filters_and_multiple_outputs_within_fold_scope,
                   [],
                   [])

    def test_recurse(self):
        self.check(test_input_data.simple_recurse,
                   [
                   ],
                   [
                       (Location(('Animal',), None, 1),
                        RecurseInfo(depth=1)),
                   ])
