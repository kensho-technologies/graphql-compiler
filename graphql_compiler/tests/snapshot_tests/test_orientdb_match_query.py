# Copyright 2017 Kensho Technologies, LLC.
from collections import Counter

import pytest
import six
from snapshottest import TestCase

from .. import test_input_data
from ... import graphql_to_match
from ..test_helpers import get_schema


def execute_graphql(schema, test_data, client, sample_parameters):
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

    result = graphql_to_match(schema, test_data.graphql_input, sample_parameters,
                              type_equivalence_hints=schema_based_type_equivalence_hints)

    # We need to preprocess the results to be agnostic of the returned order.
    # For this we perform the following steps
    # - convert lists (returned from @fold scopes) to tuples to make them hashable
    # - convert each row dict to a frozenset of its items
    # - create a Counter (multi-set) of the row frozensets
    # - convert the multi-set to a frozenset of its items
    row_dicts = [row.oRecordData for row in client.command(result.query)]
    row_dicts_using_tuples = [
        {
            column_name: tuple(value) if isinstance(value, list) else value
            for column_name, value in row.items()
        }
        for row in row_dicts
    ]
    row_frozensets = [frozenset(row_dict.items()) for row_dict in row_dicts_using_tuples]
    rows_multiset = Counter(row_frozensets)
    row_counters_frozenset = frozenset(rows_multiset.items())

    return row_counters_frozenset


# The following TestCase class uses the 'graph_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member


class OrientDBMatchQueryTests(TestCase):

    def setUp(self):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        self.maxDiff = None
        self.schema = get_schema()

    @pytest.mark.usefixtures('graph_client')
    def test_immediate_output(self):
        test_data = test_input_data.immediate_output()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.graph_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('graph_client')
    def test_traverse_and_output(self):
        test_data = test_input_data.traverse_and_output()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.graph_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('graph_client')
    def test_traverse_filter_and_output(self):
        test_data = test_input_data.traverse_filter_and_output()
        sample_parameters = {'wanted': 'Nazgul__2'}

        rows = execute_graphql(self.schema, test_data, self.graph_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('graph_client')
    def test_filter_in_optional_block(self):
        test_data = test_input_data.filter_in_optional_block()
        sample_parameters = {'name': 'Nazgul__2'}

        rows = execute_graphql(self.schema, test_data, self.graph_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('graph_client')
    def test_optional_traverse_after_mandatory_traverse(self):
        test_data = test_input_data.optional_traverse_after_mandatory_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.graph_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('graph_client')
    def test_optional_and_deep_traverse(self):
        test_data = test_input_data.optional_and_deep_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.graph_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('graph_client')
    def test_fold_on_output_variable(self):
        test_data = test_input_data.fold_on_output_variable()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.graph_client, sample_parameters)

        self.assertMatchSnapshot(rows)


# pylint: enable=no-member
