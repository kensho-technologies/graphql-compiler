# Copyright 2017 Kensho Technologies, LLC.
from collections import Counter
import pytest
import six
from snapshottest import TestCase

from .. import test_input_data
from ... import graphql_to_match
from ..test_helpers import get_schema


def execute_graphql(schema, test_data, client):
    """Compile the GraphQL query to MATCH, execute it agains the test_db, and return the results."""
    if test_data.type_equivalence_hints:
        # For test convenience, we accept the type equivalence hints in string form.
        # Here, we convert them to the required GraphQL types.
        schema_based_type_equivalence_hints = {
            schema.get_type(key): schema.get_type(value)
            for key, value in six.iteritems(test_data.type_equivalence_hints)
        }
    else:
        schema_based_type_equivalence_hints = None

    result = graphql_to_match(schema, test_data.graphql_input, test_data.sample_parameters,
                              type_equivalence_hints=schema_based_type_equivalence_hints)

    # TODO(shankha): Make lists hashable <26-06-18>
    row_dicts = [row.oRecordData for row in client.command(result.query)]
    row_frozensets = [frozenset(row_dict.items()) for row_dict in row_dicts]
    rows_multiset = Counter(row_frozensets)
    row_counters_frozenset = frozenset(rows_multiset.items())

    return row_counters_frozenset


class OrientdbMatchQueryTests(TestCase):

    def setUp(self):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        self.maxDiff = None
        self.schema = get_schema()

    @pytest.mark.usefixtures('test_db')
    def test_immediate_output(self):
        test_data = test_input_data.immediate_output()

        rows = execute_graphql(self.schema, test_data, self.graph_client)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('test_db')
    def test_traverse_and_output(self):
        test_data = test_input_data.traverse_and_output()

        rows = execute_graphql(self.schema, test_data, self.graph_client)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('test_db')
    def test_traverse_filter_and_output(self):
        test_data = test_input_data.traverse_filter_and_output()

        rows = execute_graphql(self.schema, test_data, self.graph_client)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('test_db')
    def test_filter_in_optional_block(self):
        test_data = test_input_data.filter_in_optional_block()

        rows = execute_graphql(self.schema, test_data, self.graph_client)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('test_db')
    def test_optional_traverse_after_mandatory_traverse(self):
        test_data = test_input_data.optional_traverse_after_mandatory_traverse()

        rows = execute_graphql(self.schema, test_data, self.graph_client)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('test_db')
    def test_optional_and_deep_traverse(self):
        test_data = test_input_data.optional_and_deep_traverse()

        rows = execute_graphql(self.schema, test_data, self.graph_client)

        self.assertMatchSnapshot(rows)
