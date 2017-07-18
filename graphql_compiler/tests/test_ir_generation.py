# Copyright 2017 Kensho Technologies, Inc.
import unittest

from graphql import GraphQLID, GraphQLList, GraphQLString
import pytest

from ..compiler import blocks, expressions, helpers
from ..compiler.compiler_frontend import OutputMetadata, graphql_to_ir
from ..schema import GraphQLDate, GraphQLDateTime
from .test_helpers import compare_input_metadata, compare_ir_blocks, get_schema


def check_test_data(test_case, graphql_input, expected_blocks,
                    expected_output_metadata, expected_input_metadata, expected_location_types):
    """Assert that the GraphQL input generates all expected IR data."""
    received_blocks, output_metadata, input_metadata, location_types = \
        graphql_to_ir(test_case.schema, graphql_input)

    compare_ir_blocks(test_case, expected_blocks, received_blocks)
    test_case.assertEquals(expected_output_metadata, output_metadata)
    compare_input_metadata(test_case, expected_input_metadata, input_metadata)
    test_case.assertEquals(expected_location_types, comparable_location_types(location_types))


def comparable_location_types(location_types):
    """Convert the dict of Location -> GraphQL object type into a dict of Location -> basestring."""
    return {
        location: graphql_type.name
        for location, graphql_type in location_types.iteritems()
    }


class IrGenerationTests(unittest.TestCase):
    """Ensure valid inputs produce correct IR."""

    def setUp(self):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        self.maxDiff = None
        self.schema = get_schema()

    def test_immediate_output(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString)
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_immediate_filter_and_output(self):
        # Ensure that all basic comparison operators output correct code in this simple case.
        comparison_operators = {u'=', u'!=', u'>', u'<', u'>=', u'<='}

        for operator in comparison_operators:
            graphql_input = '''{
                Animal {
                    name @filter(op_name: "%s", value: ["$wanted"]) @output(out_name: "animal_name")
                }
            }''' % (operator,)

            base_location = helpers.Location(('Animal',))

            expected_blocks = [
                blocks.QueryRoot({'Animal'}),
                blocks.Filter(expressions.BinaryComposition(
                    operator, expressions.LocalField('name'),
                    expressions.Variable('$wanted', GraphQLString))),
                blocks.MarkLocation(base_location),
                blocks.ConstructResult({
                    'animal_name': expressions.OutputContextField(
                        base_location.navigate_to_field('name'), GraphQLString)
                }),
            ]
            expected_output_metadata = {
                'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            }
            expected_input_metadata = {
                'wanted': GraphQLString,
            }
            expected_location_types = {
                base_location: 'Animal',
            }

            check_test_data(self, graphql_input, expected_blocks,
                            expected_output_metadata, expected_input_metadata,
                            expected_location_types)

    def test_traverse_and_output(self):
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf {
                    name @output(out_name: "parent_name")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'parent_name': expressions.OutputContextField(
                    child_location.navigate_to_field('name'), GraphQLString)
            }),
        ]
        expected_output_metadata = {
            'parent_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_optional_traverse_after_mandatory_traverse(self):
        graphql_input = '''{
            Animal {
                out_Animal_OfSpecies {
                    name @output(out_name: "species_name")
                }
                out_Animal_ParentOf @optional {
                    name @output(out_name: "child_name")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        revisited_base_location = base_location.revisit()
        twice_revisited_base_location = revisited_base_location.revisit()
        species_location = base_location.navigate_to_subpath('out_Animal_OfSpecies')
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_OfSpecies'),
            blocks.MarkLocation(species_location),
            blocks.Backtrack(base_location),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse('out', 'Animal_ParentOf', optional=True),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location, optional=True),
            blocks.MarkLocation(twice_revisited_base_location),
            blocks.ConstructResult({
                'species_name': expressions.OutputContextField(
                    species_location.navigate_to_field('name'), GraphQLString),
                'child_name': expressions.TernaryConditional(
                    expressions.ContextFieldExistence(child_location),
                    expressions.OutputContextField(
                        child_location.navigate_to_field('name'), GraphQLString),
                    expressions.NullLiteral),
            }),
        ]
        expected_output_metadata = {
            'species_name': OutputMetadata(type=GraphQLString, optional=False),
            'child_name': OutputMetadata(type=GraphQLString, optional=True),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            species_location: 'Species',
            revisited_base_location: 'Animal',
            child_location: 'Animal',
            twice_revisited_base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_traverse_filter_and_output(self):
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                    name @output(out_name: "parent_name")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(
                        u'=',
                        expressions.LocalField('name'),
                        expressions.Variable('$wanted', GraphQLString)
                    ), expressions.BinaryComposition(
                        u'contains',
                        expressions.LocalField('alias'),
                        expressions.Variable('$wanted', GraphQLString)
                    )
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'parent_name': expressions.OutputContextField(
                    child_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'parent_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_output_source_and_complex_output(self):
        graphql_input = '''{
            Animal {
                name @filter(op_name: "=", value: ["$wanted"]) @output(out_name: "animal_name")
                out_Animal_ParentOf @output_source {
                    name @output(out_name: "parent_name")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'=',
                    expressions.LocalField('name'),
                    expressions.Variable('$wanted', GraphQLString)
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.MarkLocation(child_location),
            blocks.OutputSource(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'parent_name': expressions.OutputContextField(
                    child_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'parent_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_filter_on_optional_variable_equality(self):
        # The operand in the @filter directive originates from an optional block.
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf {
                    out_Animal_FedAt @optional {
                        name @tag(tag_name: "child_fed_at_event")
                    }
                }
                out_Animal_FedAt @output_source {
                    name @filter(op_name: "=", value: ["%child_fed_at_event"])
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')
        child_fed_at_location = child_location.navigate_to_subpath('out_Animal_FedAt')
        child_revisited_location = child_location.revisit()
        animal_fed_at_location = base_location.navigate_to_subpath('out_Animal_FedAt')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.MarkLocation(child_location),
            blocks.Traverse('out', 'Animal_FedAt', optional=True),
            blocks.MarkLocation(child_fed_at_location),
            blocks.Backtrack(child_location, optional=True),
            blocks.MarkLocation(child_revisited_location),
            blocks.Backtrack(base_location),
            blocks.Traverse('out', 'Animal_FedAt'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(
                        u'=',
                        expressions.ContextFieldExistence(child_fed_at_location),
                        expressions.FalseLiteral
                    ),
                    expressions.BinaryComposition(
                        u'=',
                        expressions.LocalField('name'),
                        expressions.ContextField(child_fed_at_location.navigate_to_field('name'))
                    )
                )
            ),
            blocks.MarkLocation(animal_fed_at_location),
            blocks.OutputSource(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
            child_fed_at_location: 'Event',
            child_revisited_location: 'Animal',
            animal_fed_at_location: 'Event',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_filter_on_optional_variable_name_or_alias(self):
        # The operand in the @filter directive originates from an optional block.
        graphql_input = '''{
            Animal {
                in_Animal_ParentOf @optional {
                    name @tag(tag_name: "parent_name")
                }
                out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["%parent_name"])
                                    @output_source {
                    name @output(out_name: "animal_name")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        parent_location = base_location.navigate_to_subpath('in_Animal_ParentOf')
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')
        base_revisited_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('in', 'Animal_ParentOf', optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(base_revisited_location),
            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(
                        u'=',
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral
                    ),
                    expressions.BinaryComposition(
                        u'||',
                        expressions.BinaryComposition(
                            u'=',
                            expressions.LocalField('name'),
                            expressions.ContextField(parent_location.navigate_to_field('name'))
                        ),
                        expressions.BinaryComposition(
                            u'contains',
                            expressions.LocalField('alias'),
                            expressions.ContextField(parent_location.navigate_to_field('name'))
                        )
                    )
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.OutputSource(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    child_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            parent_location: 'Animal',
            base_revisited_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_filter_in_optional_block(self):
        graphql_input = '''{
            Animal {
                out_Animal_FedAt @optional {
                    name @filter(op_name: "=", value: ["$name"])
                    uuid @output(out_name: "uuid")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        animal_fed_at_location = base_location.navigate_to_subpath('out_Animal_FedAt')
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_FedAt', optional=True),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'=',
                    expressions.LocalField('name'),
                    expressions.Variable('$name', GraphQLString)
                )
            ),
            blocks.MarkLocation(animal_fed_at_location),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.ConstructResult({
                'uuid': expressions.TernaryConditional(
                    expressions.ContextFieldExistence(animal_fed_at_location),
                    expressions.OutputContextField(
                        animal_fed_at_location.navigate_to_field('uuid'), GraphQLID),
                    expressions.NullLiteral
                )
            }),
        ]
        expected_output_metadata = {
            'uuid': OutputMetadata(type=GraphQLID, optional=True),
        }
        expected_input_metadata = {
            'name': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Animal',
            animal_fed_at_location: 'Event',
            revisited_base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_between_filter_on_simple_scalar(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a simple scalar (a String).
        graphql_input = '''{
            Animal {
                name @filter(op_name: "between", value: ["$lower", "$upper"])
                     @output(out_name: "name")
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'&&',
                    expressions.BinaryComposition(
                        u'>=',
                        expressions.LocalField('name'),
                        expressions.Variable('$lower', GraphQLString)
                    ),
                    expressions.BinaryComposition(
                        u'<=',
                        expressions.LocalField('name'),
                        expressions.Variable('$upper', GraphQLString)
                    )
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString)
            }),
        ]
        expected_output_metadata = {
            'name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'lower': GraphQLString,
            'upper': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_between_filter_on_date(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (Date).
        graphql_input = '''{
            Animal {
                birthday @filter(op_name: "between", value: ["$lower", "$upper"])
                         @output(out_name: "birthday")
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'&&',
                    expressions.BinaryComposition(
                        u'>=',
                        expressions.LocalField('birthday'),
                        expressions.Variable('$lower', GraphQLDate)
                    ),
                    expressions.BinaryComposition(
                        u'<=',
                        expressions.LocalField('birthday'),
                        expressions.Variable('$upper', GraphQLDate)
                    )
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'birthday': expressions.OutputContextField(
                    base_location.navigate_to_field('birthday'), GraphQLDate)
            }),
        ]
        expected_output_metadata = {
            'birthday': OutputMetadata(type=GraphQLDate, optional=False),
        }
        expected_input_metadata = {
            'lower': GraphQLDate,
            'upper': GraphQLDate,
        }
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_between_filter_on_datetime(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (DateTime).
        graphql_input = '''{
            Event {
                event_date @filter(op_name: "between", value: ["$lower", "$upper"])
                           @output(out_name: "event_date")
            }
        }'''

        base_location = helpers.Location(('Event',))

        expected_blocks = [
            blocks.QueryRoot({'Event'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'&&',
                    expressions.BinaryComposition(
                        u'>=',
                        expressions.LocalField('event_date'),
                        expressions.Variable('$lower', GraphQLDateTime)
                    ),
                    expressions.BinaryComposition(
                        u'<=',
                        expressions.LocalField('event_date'),
                        expressions.Variable('$upper', GraphQLDateTime)
                    )
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'event_date': expressions.OutputContextField(
                    base_location.navigate_to_field('event_date'), GraphQLDateTime)
            }),
        ]
        expected_output_metadata = {
            'event_date': OutputMetadata(type=GraphQLDateTime, optional=False),
        }
        expected_input_metadata = {
            'lower': GraphQLDateTime,
            'upper': GraphQLDateTime,
        }
        expected_location_types = {
            base_location: 'Event',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_complex_optional_variables(self):
        # The operands in the @filter directives originate from an optional block.
        graphql_input = '''{
            Animal {
                name @filter(op_name: "=", value: ["$animal_name"])
                out_Animal_ParentOf {
                    out_Animal_FedAt @optional {
                        name @tag(tag_name: "child_fed_at_event")
                        event_date @tag(tag_name: "child_fed_at")
                                   @output(out_name: "child_fed_at")
                    }
                    in_Animal_ParentOf {
                        out_Animal_FedAt @optional {
                            event_date @tag(tag_name: "other_parent_fed_at")
                                       @output(out_name: "other_parent_fed_at")
                        }
                    }
                }
                in_Animal_ParentOf {
                    out_Animal_FedAt {
                        name @filter(op_name: "=", value: ["%child_fed_at_event"])
                        event_date @output(out_name: "grandparent_fed_at")
                                   @filter(op_name: "between",
                                           value: ["%other_parent_fed_at", "%child_fed_at"])
                    }
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')
        child_fed_at_location = child_location.navigate_to_subpath('out_Animal_FedAt')

        child_fed_at_event_tag = child_fed_at_location.navigate_to_field('name')
        child_fed_at_tag = child_fed_at_location.navigate_to_field('event_date')

        revisited_child_location = child_location.revisit()

        other_parent_location = child_location.navigate_to_subpath('in_Animal_ParentOf')
        other_parent_fed_at_location = other_parent_location.navigate_to_subpath('out_Animal_FedAt')
        other_parent_fed_at_tag = other_parent_fed_at_location.navigate_to_field('event_date')
        other_parent_revisited_location = other_parent_location.revisit()

        grandparent_location = base_location.navigate_to_subpath('in_Animal_ParentOf')
        grandparent_fed_at_location = grandparent_location.navigate_to_subpath('out_Animal_FedAt')
        grandparent_fed_at_output = grandparent_fed_at_location.navigate_to_field('event_date')

        expected_blocks = [
            # Apply the filter to the root vertex and mark it.
            blocks.QueryRoot({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'=',
                    expressions.LocalField('name'),
                    expressions.Variable('$animal_name', GraphQLString)
                )
            ),
            blocks.MarkLocation(base_location),

            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.MarkLocation(child_location),

            blocks.Traverse('out', 'Animal_FedAt', optional=True),
            blocks.MarkLocation(child_fed_at_location),
            blocks.Backtrack(child_location, optional=True),
            blocks.MarkLocation(revisited_child_location),

            blocks.Traverse('in', 'Animal_ParentOf'),
            blocks.MarkLocation(other_parent_location),
            blocks.Traverse('out', 'Animal_FedAt', optional=True),
            blocks.MarkLocation(other_parent_fed_at_location),
            blocks.Backtrack(other_parent_location, optional=True),
            blocks.MarkLocation(other_parent_revisited_location),
            blocks.Backtrack(revisited_child_location),

            # Back to root vertex.
            blocks.Backtrack(base_location),

            blocks.Traverse('in', 'Animal_ParentOf'),
            blocks.MarkLocation(grandparent_location),
            blocks.Traverse('out', 'Animal_FedAt'),
            blocks.Filter(  # Filter "=" on the name field.
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(
                        u'=',
                        expressions.ContextFieldExistence(child_fed_at_location),
                        expressions.FalseLiteral
                    ),
                    expressions.BinaryComposition(
                        u'=',
                        expressions.LocalField('name'),
                        expressions.ContextField(child_fed_at_event_tag),
                    )
                )
            ),
            blocks.Filter(  # Filter "between" on the event_date field.
                expressions.BinaryComposition(
                    u'&&',
                    expressions.BinaryComposition(
                        u'||',
                        expressions.BinaryComposition(
                            u'=',
                            expressions.ContextFieldExistence(other_parent_fed_at_location),
                            expressions.FalseLiteral
                        ),
                        expressions.BinaryComposition(
                            u'>=',
                            expressions.LocalField('event_date'),
                            expressions.ContextField(other_parent_fed_at_tag)
                        )
                    ),
                    expressions.BinaryComposition(
                        u'||',
                        expressions.BinaryComposition(
                            u'=',
                            expressions.ContextFieldExistence(child_fed_at_location),
                            expressions.FalseLiteral
                        ),
                        expressions.BinaryComposition(
                            u'<=',
                            expressions.LocalField('event_date'),
                            expressions.ContextField(child_fed_at_tag)
                        )
                    )
                )
            ),
            blocks.MarkLocation(grandparent_fed_at_location),
            blocks.Backtrack(grandparent_location),
            blocks.Backtrack(base_location),

            blocks.ConstructResult({
                'child_fed_at': expressions.TernaryConditional(
                    expressions.ContextFieldExistence(child_fed_at_location),
                    expressions.OutputContextField(child_fed_at_tag, GraphQLDateTime),
                    expressions.NullLiteral
                ),
                'other_parent_fed_at': expressions.TernaryConditional(
                    expressions.ContextFieldExistence(other_parent_fed_at_location),
                    expressions.OutputContextField(other_parent_fed_at_tag, GraphQLDateTime),
                    expressions.NullLiteral
                ),
                'grandparent_fed_at': expressions.OutputContextField(
                    grandparent_fed_at_output, GraphQLDateTime),
            }),
        ]
        expected_output_metadata = {
            'child_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
            'other_parent_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
            'grandparent_fed_at': OutputMetadata(type=GraphQLDateTime, optional=False),
        }
        expected_input_metadata = {
            'animal_name': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
            child_fed_at_location: 'Event',
            revisited_child_location: 'Animal',
            other_parent_location: 'Animal',
            other_parent_fed_at_location: 'Event',
            other_parent_revisited_location: 'Animal',
            grandparent_location: 'Animal',
            grandparent_fed_at_location: 'Event',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_simple_fragment(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Entity_Related {
                    ... on Animal {
                        name @output(out_name: "related_animal_name")
                        out_Animal_OfSpecies {
                            name @output(out_name: "related_animal_species")
                        }
                    }
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        related_location = base_location.navigate_to_subpath('out_Entity_Related')
        related_species_location = related_location.navigate_to_subpath('out_Animal_OfSpecies')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Entity_Related'),
            blocks.CoerceType({'Animal'}),
            blocks.MarkLocation(related_location),
            blocks.Traverse('out', 'Animal_OfSpecies'),
            blocks.MarkLocation(related_species_location),
            blocks.Backtrack(related_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'related_animal_name': expressions.OutputContextField(
                    related_location.navigate_to_field('name'), GraphQLString),
                'related_animal_species': expressions.OutputContextField(
                    related_species_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'related_animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'related_animal_species': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            related_location: 'Animal',
            related_species_location: 'Species',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_simple_union(self):
        graphql_input = '''{
            Species {
                name @output(out_name: "species_name")
                out_Species_Eats {
                    ... on Food {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }'''

        base_location = helpers.Location(('Species',))
        food_location = base_location.navigate_to_subpath('out_Species_Eats')

        expected_blocks = [
            blocks.QueryRoot({'Species'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Species_Eats'),
            blocks.CoerceType({'Food'}),
            blocks.MarkLocation(food_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'species_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'food_name': expressions.OutputContextField(
                    food_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'species_name': OutputMetadata(type=GraphQLString, optional=False),
            'food_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Species',
            food_location: 'Food',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_filter_on_fragment_in_union(self):
        graphql_input = '''{
            Species {
                name @output(out_name: "species_name")
                out_Species_Eats {
                    ... on Food @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }'''

        base_location = helpers.Location(('Species',))
        food_location = base_location.navigate_to_subpath('out_Species_Eats')

        expected_blocks = [
            blocks.QueryRoot({'Species'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Species_Eats'),
            blocks.CoerceType({'Food'}),
            blocks.Filter(expressions.BinaryComposition(
                u'||',
                expressions.BinaryComposition(
                    u'=',
                    expressions.LocalField('name'),
                    expressions.Variable('$wanted', GraphQLString)
                ), expressions.BinaryComposition(
                    u'contains',
                    expressions.LocalField('alias'),
                    expressions.Variable('$wanted', GraphQLString)
                )
            )),
            blocks.MarkLocation(food_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'species_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'food_name': expressions.OutputContextField(
                    food_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'species_name': OutputMetadata(type=GraphQLString, optional=False),
            'food_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Species',
            food_location: 'Food',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_optional_on_union(self):
        graphql_input = '''{
            Species {
                name @output(out_name: "species_name")
                out_Species_Eats @optional {
                    ... on Food {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }'''

        base_location = helpers.Location(('Species',))
        food_location = base_location.navigate_to_subpath('out_Species_Eats')
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({'Species'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Species_Eats', optional=True),
            blocks.CoerceType({'Food'}),
            blocks.MarkLocation(food_location),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.ConstructResult({
                'species_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'food_name': expressions.TernaryConditional(
                    expressions.ContextFieldExistence(food_location),
                    expressions.OutputContextField(
                        food_location.navigate_to_field('name'), GraphQLString),
                    expressions.NullLiteral
                ),
            }),
        ]
        expected_output_metadata = {
            'species_name': OutputMetadata(type=GraphQLString, optional=False),
            'food_name': OutputMetadata(type=GraphQLString, optional=True),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Species',
            food_location: 'Food',
            revisited_base_location: 'Species',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_typename_output(self):
        graphql_input = '''{
            Animal {
                __typename @output(out_name: "base_cls")
                out_Animal_OfSpecies {
                    __typename @output(out_name: "child_cls")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        species_location = base_location.navigate_to_subpath('out_Animal_OfSpecies')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_OfSpecies'),
            blocks.MarkLocation(species_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'base_cls': expressions.OutputContextField(
                    base_location.navigate_to_field('@class'), GraphQLString),
                'child_cls': expressions.OutputContextField(
                    species_location.navigate_to_field('@class'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'base_cls': OutputMetadata(type=GraphQLString, optional=False),
            'child_cls': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            species_location: 'Species',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_typename_filter(self):
        graphql_input = '''{
            Entity {
                __typename @filter(op_name: "=", value: ["$base_cls"])
                name @output(out_name: "entity_name")
            }
        }'''

        base_location = helpers.Location(('Entity',))

        expected_blocks = [
            blocks.QueryRoot({'Entity'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'=',
                    expressions.LocalField('@class'),
                    expressions.Variable('$base_cls', GraphQLString)
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'entity_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'entity_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'base_cls': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Entity',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_simple_recurse(self):
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 1) {
                    name @output(out_name: "relation_name")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Recurse('out', 'Animal_ParentOf', 1),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'relation_name': expressions.OutputContextField(
                    child_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'relation_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_recurse_within_fragment(self):
        graphql_input = '''{
            Food {
                name @output(out_name: "food_name")
                in_Entity_Related {
                    ... on Animal {
                        name @output(out_name: "animal_name")
                        out_Animal_ParentOf @recurse(depth: 3) {
                            name @output(out_name: "relation_name")
                        }
                    }
                }
            }
        }'''

        base_location = helpers.Location(('Food',))
        related_location = base_location.navigate_to_subpath('in_Entity_Related')
        child_location = related_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Food'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('in', 'Entity_Related'),
            blocks.CoerceType({'Animal'}),
            blocks.MarkLocation(related_location),
            blocks.Recurse('out', 'Animal_ParentOf', 3),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(related_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'food_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'animal_name': expressions.OutputContextField(
                    related_location.navigate_to_field('name'), GraphQLString),
                'relation_name': expressions.OutputContextField(
                    child_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'food_name': OutputMetadata(type=GraphQLString, optional=False),
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'relation_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Food',
            related_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_filter_within_recurse(self):
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 3) {
                    name @output(out_name: "relation_name")
                    color @filter(op_name: "=", value: ["$wanted"])
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Recurse('out', 'Animal_ParentOf', 3),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'=',
                    expressions.LocalField('color'),
                    expressions.Variable('$wanted', GraphQLString)
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'relation_name': expressions.OutputContextField(
                    child_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'relation_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_recurse_with_immediate_type_coercion(self):
        graphql_input = '''{
            Animal {
                in_Entity_Related @recurse(depth: 4) {
                    ... on Animal {
                        name @output(out_name: "name")
                    }
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        related_location = base_location.navigate_to_subpath('in_Entity_Related')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Recurse('in', 'Entity_Related', 4),
            blocks.CoerceType({'Animal'}),
            blocks.MarkLocation(related_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'name': expressions.OutputContextField(
                    related_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            related_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_recurse_with_immediate_type_coercion_and_filter(self):
        graphql_input = '''{
            Animal {
                in_Entity_Related @recurse(depth: 4) {
                    ... on Animal {
                        name @output(out_name: "name")
                        color @filter(op_name: "=", value: ["$color"])
                    }
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        related_location = base_location.navigate_to_subpath('in_Entity_Related')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Recurse('in', 'Entity_Related', 4),
            blocks.CoerceType({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'=',
                    expressions.LocalField('color'),
                    expressions.Variable('$color', GraphQLString)
                )
            ),
            blocks.MarkLocation(related_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'name': expressions.OutputContextField(
                    related_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'color': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Animal',
            related_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_in_collection_op_filter_with_variable(self):
        graphql_input = '''{
            Animal {
                name @filter(op_name: "in_collection", value: ["$wanted"])
                     @output(out_name: "animal_name")
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'contains',
                    expressions.Variable('$wanted', GraphQLList(GraphQLString)),
                    expressions.LocalField('name')
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLList(GraphQLString)
        }
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_in_collection_op_filter_with_tag(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                alias @tag(tag_name: "aliases")
                out_Animal_ParentOf {
                    name @filter(op_name: "in_collection", value: ["%aliases"])
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'contains',
                    expressions.ContextField(base_location.navigate_to_field('alias')),
                    expressions.LocalField('name')
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_in_collection_op_filter_with_optional_tag(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf @optional {
                    alias @tag(tag_name: "parent_aliases")
                }
                out_Animal_ParentOf {
                    name @filter(op_name: "in_collection", value: ["%parent_aliases"])
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath('in_Animal_ParentOf')
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),

            blocks.Traverse('in', 'Animal_ParentOf', optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),

            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(
                        u'=',
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral
                    ),
                    expressions.BinaryComposition(
                        u'contains',
                        expressions.ContextField(parent_location.navigate_to_field('alias')),
                        expressions.LocalField('name')
                    )
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            revisited_base_location: 'Animal',
            parent_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_contains_op_filter_with_variable(self):
        graphql_input = '''{
            Animal {
                alias @filter(op_name: "contains", value: ["$wanted"])
                name @output(out_name: "animal_name")
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'contains',
                    expressions.LocalField('alias'),
                    expressions.Variable('$wanted', GraphQLString)
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_contains_op_filter_with_tag(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name") @tag(tag_name: "name")
                out_Animal_ParentOf {
                    alias @filter(op_name: "contains", value: ["%name"])
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'contains',
                    expressions.LocalField('alias'),
                    expressions.ContextField(base_location.navigate_to_field('name')),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_contains_op_filter_with_optional_tag(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf @optional {
                    name @tag(tag_name: "parent_name")
                }
                out_Animal_ParentOf {
                    alias @filter(op_name: "contains", value: ["%parent_name"])
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath('in_Animal_ParentOf')
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),

            blocks.Traverse('in', 'Animal_ParentOf', optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),

            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(
                        u'=',
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral
                    ),
                    expressions.BinaryComposition(
                        u'contains',
                        expressions.LocalField('alias'),
                        expressions.ContextField(parent_location.navigate_to_field('name'))
                    )
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            revisited_base_location: 'Animal',
            parent_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_has_substring_op_filter(self):
        graphql_input = '''{
            Animal {
                name @filter(op_name: "has_substring", value: ["$wanted"])
                     @output(out_name: "animal_name")
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'has_substring',
                    expressions.LocalField('name'),
                    expressions.Variable('$wanted', GraphQLString)
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_has_substring_op_filter_with_optional_tag(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf @optional {
                    name @tag(tag_name: "parent_name")
                }
                out_Animal_ParentOf {
                    name @filter(op_name: "has_substring", value: ["%parent_name"])
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath('in_Animal_ParentOf')
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),

            blocks.Traverse('in', 'Animal_ParentOf', optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),

            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(
                        u'=',
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral
                    ),
                    expressions.BinaryComposition(
                        u'has_substring',
                        expressions.LocalField('name'),
                        expressions.ContextField(parent_location.navigate_to_field('name'))
                    )
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            revisited_base_location: 'Animal',
            parent_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    # Disabled until OrientDB fixes the limitation against traversing from an optional vertex.
    # For details, see https://github.com/orientechnologies/orientdb/issues/6788
    @pytest.mark.skip(reason='traversing from an optional node is not currently supported in MATCH')
    def test_optional_traversal_edge_case(self):
        # Both Animal and out_Animal_ParentOf have an out_Animal_FedAt field,
        # ensure the correct such field is picked out.
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @optional {
                    out_Animal_FedAt {
                        name @output(out_name: "name")
                    }
                }
            }
        }'''

        # Disabled until OrientDB fixes the limitation against traversing from an optional vertex.
        # Rather than compiling correctly, this raises an exception until the OrientDB limitation
        # is lifted.
        # For details, see https://github.com/orientechnologies/orientdb/issues/6788
        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')
        child_fed_at_location = child_location.navigate_to_subpath('out_Animal_FedAt')
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),

            blocks.Traverse('out', 'Animal_ParentOf', optional=True),
            blocks.MarkLocation(child_location),

            blocks.Traverse('out', 'Animal_FedAt'),
            blocks.MarkLocation(child_fed_at_location),
            blocks.Backtrack(child_location),

            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),

            blocks.ConstructResult({
                'name': expressions.TernaryConditional(
                    expressions.ContextFieldExistence(child_fed_at_location),
                    expressions.OutputContextField(
                        child_fed_at_location.navigate_to_field('name'), GraphQLString),
                    expressions.NullLiteral
                ),
            })
        ]
        expected_output_metadata = {
            'name': OutputMetadata(type=GraphQLString, optional=True),
        }
        expected_input_metadata = {}
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
            child_fed_at_location: 'Event',
            revisited_base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_no_traversing_from_optional_scope(self):
        # Until OrientDB fixes the limitation against traversing from an optional vertex,
        # attempting to do so will raise GraphQLCompilationError.
        # For details, see https://github.com/orientechnologies/orientdb/issues/6788

        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @optional {
                    out_Animal_FedAt {
                        name @output(out_name: "name")
                    }
                }
            }
        }'''

        with self.assertRaises(helpers.GraphQLCompilationError):
            graphql_to_ir(self.schema, graphql_input)

    def test_fold_on_output_variable(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    name @output(out_name: "child_names_list")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_names_list': expressions.FoldedOutputContextField(
                    base_location, ('out', 'Animal_ParentOf'), 'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'child_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_fold_after_traverse(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf {
                    out_Animal_ParentOf @fold {
                        name @output(out_name: "sibling_and_self_names_list")
                    }
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))
        parent_location = base_location.navigate_to_subpath('in_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('in', 'Animal_ParentOf'),
            blocks.MarkLocation(parent_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'sibling_and_self_names_list': expressions.FoldedOutputContextField(
                    parent_location, ('out', 'Animal_ParentOf'),
                    'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'sibling_and_self_names_list': OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
            parent_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_multiple_outputs_in_same_fold(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    name @output(out_name: "child_names_list")
                    uuid @output(out_name: "child_uuids_list")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_names_list': expressions.FoldedOutputContextField(
                    base_location, ('out', 'Animal_ParentOf'), 'name', GraphQLList(GraphQLString)),
                'child_uuids_list': expressions.FoldedOutputContextField(
                    base_location, ('out', 'Animal_ParentOf'), 'uuid', GraphQLList(GraphQLID)),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'child_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
            'child_uuids_list': OutputMetadata(type=GraphQLList(GraphQLID), optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_multiple_folds(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    name @output(out_name: "child_names_list")
                    uuid @output(out_name: "child_uuids_list")
                }
                in_Animal_ParentOf @fold {
                    name @output(out_name: "parent_names_list")
                    uuid @output(out_name: "parent_uuids_list")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_names_list': expressions.FoldedOutputContextField(
                    base_location, ('out', 'Animal_ParentOf'), 'name', GraphQLList(GraphQLString)),
                'child_uuids_list': expressions.FoldedOutputContextField(
                    base_location, ('out', 'Animal_ParentOf'), 'uuid', GraphQLList(GraphQLID)),
                'parent_names_list': expressions.FoldedOutputContextField(
                    base_location, ('in', 'Animal_ParentOf'), 'name', GraphQLList(GraphQLString)),
                'parent_uuids_list': expressions.FoldedOutputContextField(
                    base_location, ('in', 'Animal_ParentOf'), 'uuid', GraphQLList(GraphQLID)),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'child_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
            'child_uuids_list': OutputMetadata(type=GraphQLList(GraphQLID), optional=False),
            'parent_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
            'parent_uuids_list': OutputMetadata(type=GraphQLList(GraphQLID), optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)

    def test_fold_date_and_datetime_fields(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    birthday @output(out_name: "child_birthdays_list")
                }
                out_Animal_FedAt @fold {
                    event_date @output(out_name: "fed_at_datetimes_list")
                }
            }
        }'''

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_birthdays_list': expressions.FoldedOutputContextField(
                    base_location, ('out', 'Animal_ParentOf'),
                    'birthday', GraphQLList(GraphQLDate)),
                'fed_at_datetimes_list': expressions.FoldedOutputContextField(
                    base_location, ('out', 'Animal_FedAt'),
                    'event_date', GraphQLList(GraphQLDateTime)),
            }),
        ]
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'child_birthdays_list': OutputMetadata(type=GraphQLList(GraphQLDate), optional=False),
            'fed_at_datetimes_list': OutputMetadata(
                type=GraphQLList(GraphQLDateTime), optional=False),
        }
        expected_input_metadata = {}
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, graphql_input, expected_blocks,
                        expected_output_metadata, expected_input_metadata, expected_location_types)
