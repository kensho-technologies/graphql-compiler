# Copyright 2018-present Kensho Technologies, LLC.
from collections import Counter
from decimal import Decimal

import pytest
import six
from snapshottest import TestCase

from .. import test_input_data
from ... import graphql_to_match
from ..test_helpers import get_schema


def convert_decimals_to_strings(value):
    """Convert all decimals to strings in the given scalar or tuple."""
    if isinstance(value, tuple):
        return tuple(str(element) for element in value)
    elif isinstance(value, Decimal):
        return str(value)
    elif isinstance(value, six.string_types):
        return value
    else:
        raise AssertionError(u'Received unexpected type {}. Expected one of tuple, Decimal or '
                             u'string: {}'.format(type(value).__name__, value))


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
    if len(row_dicts) == 0:
        raise AssertionError(u'Zero records returned. Trivial snapshot not allowed.')
    row_dicts_using_tuples = [
        {
            column_name: convert_decimals_to_strings(
                tuple(value) if isinstance(value, list) else value)
            for column_name, value in row.items()
        }
        for row in row_dicts
    ]
    row_frozensets = [frozenset(row_dict.items()) for row_dict in row_dicts_using_tuples]
    rows_multiset = Counter(row_frozensets)
    row_counters_frozenset = frozenset(rows_multiset.items())

    return row_counters_frozenset


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member

@pytest.mark.slow
class OrientDBUnparameterizedMatchQueryTests(TestCase):

    def setUp(self):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        self.maxDiff = None
        self.schema = get_schema()

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_immediate_output(self):
        test_data = test_input_data.immediate_output()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_immediate_output_custom_scalars(self):
        test_data = test_input_data.immediate_output_custom_scalars()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traverse_and_output(self):
        test_data = test_input_data.traverse_and_output()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional_traverse_after_mandatory_traverse(self):
        test_data = test_input_data.optional_traverse_after_mandatory_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_filter_on_optional_variable_equality(self):
        test_data = test_input_data.filter_on_optional_variable_equality()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_filter_on_optional_variable_name_or_alias(self):
        test_data = test_input_data.filter_on_optional_variable_name_or_alias()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_complex_optional_variables(self):
        test_data = test_input_data.complex_optional_variables()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_simple_fragment(self):
        test_data = test_input_data.simple_fragment()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_simple_union(self):
        test_data = test_input_data.simple_union()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional_on_union(self):
        test_data = test_input_data.optional_on_union()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_typename_output(self):
        test_data = test_input_data.typename_output()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_simple_recurse(self):
        test_data = test_input_data.simple_recurse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_recurse_within_fragment(self):
        test_data = test_input_data.recurse_within_fragment()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_recurse_with_immediate_type_coercion(self):
        test_data = test_input_data.recurse_with_immediate_type_coercion()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_in_collection_op_filter_with_tag(self):
        test_data = test_input_data.in_collection_op_filter_with_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_in_collection_op_filter_with_optional_tag(self):
        test_data = test_input_data.in_collection_op_filter_with_optional_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_not_in_collection_op_filter_with_tag(self):
        test_data = test_input_data.not_in_collection_op_filter_with_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_not_in_collection_op_filter_with_optional_tag(self):
        test_data = test_input_data.not_in_collection_op_filter_with_optional_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_intersects_op_filter_with_tag(self):
        test_data = test_input_data.intersects_op_filter_with_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_intersects_op_filter_with_optional_tag(self):
        test_data = test_input_data.intersects_op_filter_with_optional_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_contains_op_filter_with_tag(self):
        test_data = test_input_data.contains_op_filter_with_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_contains_op_filter_with_optional_tag(self):
        test_data = test_input_data.contains_op_filter_with_optional_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_not_contains_op_filter_with_tag(self):
        test_data = test_input_data.not_contains_op_filter_with_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_not_contains_op_filter_with_optional_tag(self):
        test_data = test_input_data.not_contains_op_filter_with_optional_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_has_substring_op_filter_with_optional_tag(self):
        test_data = test_input_data.has_substring_op_filter_with_optional_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_on_output_variable(self):
        test_data = test_input_data.fold_on_output_variable()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_after_traverse(self):
        test_data = test_input_data.fold_after_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_and_traverse(self):
        test_data = test_input_data.fold_and_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_and_deep_traverse(self):
        test_data = test_input_data.fold_and_deep_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traverse_and_fold_and_traverse(self):
        test_data = test_input_data.traverse_and_fold_and_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_multiple_outputs_in_same_fold(self):
        test_data = test_input_data.multiple_outputs_in_same_fold()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_multiple_outputs_in_same_fold_and_traverse(self):
        test_data = test_input_data.multiple_outputs_in_same_fold_and_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_multiple_folds(self):
        test_data = test_input_data.multiple_folds()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_multiple_folds_and_traverse(self):
        test_data = test_input_data.multiple_folds_and_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_date_and_datetime_fields(self):
        test_data = test_input_data.fold_date_and_datetime_fields()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_coercion_to_union_base_type_inside_fold(self):
        test_data = test_input_data.coercion_to_union_base_type_inside_fold()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_no_op_coercion_inside_fold(self):
        test_data = test_input_data.no_op_coercion_inside_fold()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_coercion_on_interface_within_fold_scope(self):
        test_data = test_input_data.coercion_on_interface_within_fold_scope()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_coercion_on_interface_within_fold_traversal(self):
        test_data = test_input_data.coercion_on_interface_within_fold_traversal()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_coercion_on_union_within_fold_scope(self):
        test_data = test_input_data.coercion_on_union_within_fold_scope()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional_and_traverse(self):
        test_data = test_input_data.optional_and_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional_and_deep_traverse(self):
        test_data = test_input_data.optional_and_deep_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traverse_and_optional_and_traverse(self):
        test_data = test_input_data.traverse_and_optional_and_traverse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_coercion_on_interface_within_optional_traversal(self):
        test_data = test_input_data.coercion_on_interface_within_optional_traversal()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_filter_on_optional_traversal_equality(self):
        test_data = test_input_data.filter_on_optional_traversal_equality()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_filter_on_optional_traversal_name_or_alias(self):
        test_data = test_input_data.filter_on_optional_traversal_name_or_alias()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_simple_optional_recurse(self):
        test_data = test_input_data.simple_optional_recurse()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_multiple_traverse_within_optional(self):
        test_data = test_input_data.multiple_traverse_within_optional()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional_and_fold(self):
        test_data = test_input_data.optional_and_fold()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_and_optional(self):
        test_data = test_input_data.fold_and_optional()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_optional_traversal_and_fold_traversal(self):
        test_data = test_input_data.optional_traversal_and_fold_traversal()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_fold_traversal_and_optional_traversal(self):
        test_data = test_input_data.fold_traversal_and_optional_traversal()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_coercion_and_filter_with_tag(self):
        test_data = test_input_data.coercion_and_filter_with_tag()
        sample_parameters = {}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)


@pytest.mark.slow
class OrientDBParameterizedMatchQueryTests(TestCase):

    def setUp(self):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        self.maxDiff = None
        self.schema = get_schema()

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_immediate_output_with_custom_scalar_filter(self):
        test_data = test_input_data.immediate_output_with_custom_scalar_filter()
        sample_parameters = {'min_worth': 500}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_multiple_filters(self):
        test_data = test_input_data.multiple_filters()
        sample_parameters = {'lower_bound': 'Nazgul', 'upper_bound': 'Pteranodon'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_traverse_filter_and_output(self):
        test_data = test_input_data.traverse_filter_and_output()
        sample_parameters = {'wanted': 'Nazgul__2'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_name_or_alias_filter_on_interface_type(self):
        test_data = test_input_data.name_or_alias_filter_on_interface_type()
        sample_parameters = {'wanted': 'Nazgul_1'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_output_source_and_complex_output(self):
        test_data = test_input_data.output_source_and_complex_output()
        sample_name = 'Nazgul__((((18_19_2_6)_1_19_6)_15_16_2)_14_8_9)'
        sample_parameters = {
            'wanted': sample_name
        }

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_filter_in_optional_block(self):
        test_data = test_input_data.filter_in_optional_block()
        sample_parameters = {'name': 'Nazgul__2'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_between_filter_on_simple_scalar(self):
        test_data = test_input_data.between_filter_on_simple_scalar()
        sample_parameters = {'lower': 'Nazgul', 'upper': 'Pteranodon'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_between_lowering_on_simple_scalar(self):
        test_data = test_input_data.between_lowering_on_simple_scalar()
        sample_parameters = {'lower': 'Nazgul', 'upper': 'Pteranodon'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_between_lowering_with_extra_filters(self):
        test_data = test_input_data.between_lowering_with_extra_filters()
        sample_fauna = [
            'Nazgul__7',
            'Nazgul__(((18_19_2_6)_1_19_6)_(1_12_14_19)_19_5)',
            'Nazgul__10',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)_0_13_19)',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_14_8_9)_(11_12_14_16)_17_18)',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)_(11_5_7_8)_(1_12_14_19)_6)',
            'Nazgul__((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)',
            'Nazgul__6',
            'Nazgul__5',
            'Nazgul__(10_18_2_8)',
            'Nazgul__(18_19_2_6)',
            'Nazgul__1',
            'Nazgul__(((18_19_2_6)_1_19_6)_15_16_2)',
            'Nazgul__11',
            'Nazgul__(1_12_14_19)',
            'Nazgul__14',
            'Nazgul__(((18_19_2_6)_1_19_6)_0_10_18)',
            'Nazgul__2',
            'Nazgul__((((18_19_2_6)_1_19_6)_15_16_2)_14_8_9)',
            'Nazgul__17',
            'Nazgul__((((18_19_2_6)_1_19_6)_(1_12_14_19)_19_5)_17_6_7)',
            'Nazgul__12',
            'Nazgul__(((18_19_2_6)_1_19_6)_1_19_3)',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_14_8_9)_(11_5_7_8)_16_19)',
            'Nazgul__16',
            'Nazgul__3',
            'Nazgul__15',
            'Nazgul__((((18_19_2_6)_1_19_6)_(1_12_14_19)_19_5)_0_19_4)',
        ]
        sample_parameters = {
            'lower': 'Nazgul',
            'upper': 'Pteranodon',
            'substring': '1_12',
            'fauna': sample_fauna,
        }

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_no_between_lowering_on_simple_scalar(self):
        test_data = test_input_data.no_between_lowering_on_simple_scalar()
        sample_parameters = {'lower0': 'Nazgul', 'lower1': 'Nazgul_3', 'upper': 'Pteranodon'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_complex_optional_variables_with_starting_filter(self):
        test_data = test_input_data.complex_optional_variables_with_starting_filter()
        sample_parameters = {'animal_name': 'Nazgul__((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_filter_on_fragment_in_union(self):
        test_data = test_input_data.filter_on_fragment_in_union()
        sample_parameters = {'wanted': 'Bacon'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_typename_filter(self):
        test_data = test_input_data.typename_filter()
        sample_parameters = {'base_cls': 'Food'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_filter_within_recurse(self):
        test_data = test_input_data.filter_within_recurse()
        sample_parameters = {'wanted': 'red'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_recurse_with_immediate_type_coercion_and_filter(self):
        test_data = test_input_data.recurse_with_immediate_type_coercion_and_filter()
        sample_parameters = {'color': 'red'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_in_collection_op_filter_with_variable(self):
        test_data = test_input_data.in_collection_op_filter_with_variable()
        sample_names = [
            'Nazgul__7',
            'Nazgul__(((18_19_2_6)_1_19_6)_(1_12_14_19)_19_5)',
            'Nazgul__10',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)_0_13_19)',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_14_8_9)_(11_12_14_16)_17_18)',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)_(11_5_7_8)_(1_12_14_19)_6)',
            'Nazgul__((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)',
            'Nazgul__6',
            'Nazgul__5',
            'Nazgul__(10_18_2_8)',
            'Nazgul__(18_19_2_6)',
            'Nazgul__1',
            'Nazgul__(((18_19_2_6)_1_19_6)_15_16_2)',
            'Nazgul__11',
            'Nazgul__(1_12_14_19)',
            'Nazgul__14',
            'Nazgul__(((18_19_2_6)_1_19_6)_0_10_18)',
            'Nazgul__2',
        ]
        sample_parameters = {'wanted': sample_names}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_not_in_collection_op_filter_with_variable(self):
        test_data = test_input_data.not_in_collection_op_filter_with_variable()
        sample_names = [
            'Nazgul__7',
            'Nazgul__(((18_19_2_6)_1_19_6)_(1_12_14_19)_19_5)',
            'Nazgul__10',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)_0_13_19)',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_14_8_9)_(11_12_14_16)_17_18)',
            'Nazgul__(((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)_(11_5_7_8)_(1_12_14_19)_6)',
            'Nazgul__((((18_19_2_6)_1_19_6)_15_16_2)_11_14_6)',
            'Nazgul__6',
            'Nazgul__5',
            'Nazgul__(10_18_2_8)',
            'Nazgul__(18_19_2_6)',
            'Nazgul__1',
            'Nazgul__(((18_19_2_6)_1_19_6)_15_16_2)',
            'Nazgul__11',
            'Nazgul__(1_12_14_19)',
            'Nazgul__14',
            'Nazgul__(((18_19_2_6)_1_19_6)_0_10_18)',
            'Nazgul__2',
        ]
        sample_parameters = {'wanted': sample_names}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_intersects_op_filter_with_variable(self):
        test_data = test_input_data.intersects_op_filter_with_variable()
        sample_names = [
            'Nazgul_1',
            'Nazgul_2',
            'Nazgul_3',
        ]
        sample_parameters = {'wanted': sample_names}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_contains_op_filter_with_variable(self):
        test_data = test_input_data.contains_op_filter_with_variable()
        sample_parameters = {'wanted': 'Nazgul_1'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_not_contains_op_filter_with_variable(self):
        test_data = test_input_data.not_contains_op_filter_with_variable()
        sample_parameters = {'wanted': 'Nazgul_1'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_has_substring_op_filter(self):
        test_data = test_input_data.has_substring_op_filter()
        sample_parameters = {'wanted': '6)_((1_12'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_has_edge_degree_op_filter(self):
        test_data = test_input_data.has_edge_degree_op_filter()
        sample_parameters = {'child_count': 9}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_has_edge_degree_op_filter_with_optional(self):
        test_data = test_input_data.has_edge_degree_op_filter_with_optional()

        sample_parameters = {'child_count': 1}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_has_edge_degree_op_filter_with_fold(self):
        test_data = test_input_data.has_edge_degree_op_filter_with_fold()
        sample_parameters = {'child_count': 9}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)

    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_filter_within_fold_scope(self):
        test_data = test_input_data.filter_within_fold_scope()
        sample_parameters = {'desired': 'Nazgul__2'}

        rows = execute_graphql(self.schema, test_data, self.orientdb_client, sample_parameters)

        self.assertMatchSnapshot(rows)


# pylint: enable=no-member
