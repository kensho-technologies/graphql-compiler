# Copyright 2018-present Kensho Technologies, LLC.

from . import test_input_data
from ..compiler.compiler_frontend import graphql_to_ir
from ..compiler.helpers import Location
from ..compiler.metadata import FilterInfo, RecurseInfo
from .test_helpers import get_schema


def check_explain_info(graphql_test, expected):
    """Verify query produces expected explain infos."""
    schema = get_schema()
    ir_and_metadata = graphql_to_ir(schema, graphql_test().graphql_input)
    meta = ir_and_metadata.query_metadata_table
    for loc, eis in expected:
        if meta.get_explain_infos(loc) != eis:
            raise AssertionError
    if len(expected) != len(meta._explain_infos):
        raise AssertionError


def test_filter():
    check_explain_info(test_input_data.traverse_filter_and_output,
                       [
                           (Location(('Animal', 'out_Animal_ParentOf'), None, 1),
                            [FilterInfo(field_name='out_Animal_ParentOf',
                                        op_name='name_or_alias',
                                        args=['$wanted'])]),
                       ])


def test_filters():
    check_explain_info(test_input_data.complex_optional_traversal_variables,
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
                       ])


def test_fold():
    check_explain_info(test_input_data.coercion_filters_and_multiple_outputs_within_fold_scope,
                       [])


def test_recurse():
    check_explain_info(test_input_data.simple_recurse,
                       [
                           (Location(('Animal',), None, 1),
                            [RecurseInfo(depth=1)]),
                       ])
