# Copyright 2017 Kensho Technologies, Inc.
import unittest

from graphql import GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import six

from . import test_input_data
from ..compiler import blocks, expressions, helpers
from ..compiler.compiler_frontend import OutputMetadata, graphql_to_ir
from ..schema import GraphQLDate, GraphQLDateTime
from .test_helpers import compare_input_metadata, compare_ir_blocks, get_schema


def check_test_data(test_case, test_data, expected_blocks, expected_location_types):
    """Assert that the GraphQL input generates all expected IR data."""
    if test_data.type_equivalence_hints:
        # For test convenience, we accept the type equivalence hints in string form.
        # Here, we convert them to the required GraphQL types.
        schema_based_type_equivalence_hints = {
            test_case.schema.get_type(key): test_case.schema.get_type(value)
            for key, value in six.iteritems(test_data.type_equivalence_hints)
        }
    else:
        schema_based_type_equivalence_hints = None

    compilation_results = graphql_to_ir(test_case.schema, test_data.graphql_input,
                                        type_equivalence_hints=schema_based_type_equivalence_hints)

    compare_ir_blocks(test_case, expected_blocks, compilation_results.ir_blocks)
    compare_input_metadata(
        test_case, test_data.expected_input_metadata, compilation_results.input_metadata)
    test_case.assertEqual(
        test_data.expected_output_metadata, compilation_results.output_metadata)
    test_case.assertEqual(
        expected_location_types, comparable_location_types(compilation_results.location_types))


def comparable_location_types(location_types):
    """Convert the dict of Location -> GraphQL object type into a dict of Location -> string."""
    return {
        location: graphql_type.name
        for location, graphql_type in six.iteritems(location_types)
    }


class IrGenerationTests(unittest.TestCase):
    """Ensure valid inputs produce correct IR."""

    def setUp(self):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        self.maxDiff = None
        self.schema = get_schema()

    def test_immediate_output(self):
        test_data = test_input_data.immediate_output()

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString)
            }),
        ]
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

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
            expected_location_types = {
                base_location: 'Animal',
            }
            expected_output_metadata = {
                'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            }
            expected_input_metadata = {
                'wanted': GraphQLString,
            }

            test_data = test_input_data.CommonTestData(
                graphql_input=graphql_input,
                expected_output_metadata=expected_output_metadata,
                expected_input_metadata=expected_input_metadata,
                type_equivalence_hints=None)

            check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_filters(self):
        test_data = test_input_data.multiple_filters()

        base_location = helpers.Location(('Animal',))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.Filter(expressions.BinaryComposition(
                u'>=', expressions.LocalField('name'),
                expressions.Variable('$lower_bound', GraphQLString))),
            blocks.Filter(expressions.BinaryComposition(
                u'<', expressions.LocalField('name'),
                expressions.Variable('$upper_bound', GraphQLString))),
            blocks.MarkLocation(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString)
            }),
        ]
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_traverse_and_output(self):
        test_data = test_input_data.traverse_and_output()

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
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_traverse_after_mandatory_traverse(self):
        test_data = test_input_data.optional_traverse_after_mandatory_traverse()

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
        expected_location_types = {
            base_location: 'Animal',
            species_location: 'Species',
            revisited_base_location: 'Animal',
            child_location: 'Animal',
            twice_revisited_base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_traverse_filter_and_output(self):
        test_data = test_input_data.traverse_filter_and_output()

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
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_name_or_alias_filter_on_interface_type(self):
        test_data = test_input_data.name_or_alias_filter_on_interface_type()

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Entity_Related')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Entity_Related'),
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
                'related_entity': expressions.OutputContextField(
                    child_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Entity',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_output_source_and_complex_output(self):
        test_data = test_input_data.output_source_and_complex_output()

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
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_optional_variable_equality(self):
        test_data = test_input_data.filter_on_optional_variable_equality()

        # The operand in the @filter directive originates from an optional block.
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
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
            child_fed_at_location: 'Event',
            child_revisited_location: 'Animal',
            animal_fed_at_location: 'Event',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_optional_variable_name_or_alias(self):
        test_data = test_input_data.filter_on_optional_variable_name_or_alias()

        # The operand in the @filter directive originates from an optional block.
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
        expected_location_types = {
            base_location: 'Animal',
            parent_location: 'Animal',
            base_revisited_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_in_optional_block(self):
        test_data = test_input_data.filter_in_optional_block()

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
        expected_location_types = {
            base_location: 'Animal',
            animal_fed_at_location: 'Event',
            revisited_base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_between_filter_on_simple_scalar(self):
        test_data = test_input_data.between_filter_on_simple_scalar()

        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a simple scalar (a String).
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
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_between_filter_on_date(self):
        test_data = test_input_data.between_filter_on_date()

        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (Date).
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
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_between_filter_on_datetime(self):
        test_data = test_input_data.between_filter_on_datetime()

        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (DateTime).
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
        expected_location_types = {
            base_location: 'Event',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_complex_optional_variables(self):
        test_data = test_input_data.complex_optional_variables()

        # The operands in the @filter directives originate from an optional block.
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

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_simple_fragment(self):
        test_data = test_input_data.simple_fragment()

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
        expected_location_types = {
            base_location: 'Animal',
            related_location: 'Animal',
            related_species_location: 'Species',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_simple_union(self):
        test_data = test_input_data.simple_union()

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
        expected_location_types = {
            base_location: 'Species',
            food_location: 'Food',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_fragment_in_union(self):
        test_data = test_input_data.filter_on_fragment_in_union()

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
        expected_location_types = {
            base_location: 'Species',
            food_location: 'Food',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_on_union(self):
        test_data = test_input_data.optional_on_union()

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
        expected_location_types = {
            base_location: 'Species',
            food_location: 'Food',
            revisited_base_location: 'Species',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_typename_output(self):
        test_data = test_input_data.typename_output()

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
        expected_location_types = {
            base_location: 'Animal',
            species_location: 'Species',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_typename_filter(self):
        test_data = test_input_data.typename_filter()

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
        expected_location_types = {
            base_location: 'Entity',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_simple_recurse(self):
        test_data = test_input_data.simple_recurse()

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
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_recurse_within_fragment(self):
        test_data = test_input_data.recurse_within_fragment()

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
        expected_location_types = {
            base_location: 'Food',
            related_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_within_recurse(self):
        test_data = test_input_data.filter_within_recurse()

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
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_recurse_with_immediate_type_coercion(self):
        test_data = test_input_data.recurse_with_immediate_type_coercion()

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
        expected_location_types = {
            base_location: 'Animal',
            related_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_recurse_with_immediate_type_coercion_and_filter(self):
        test_data = test_input_data.recurse_with_immediate_type_coercion_and_filter()

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
        expected_location_types = {
            base_location: 'Animal',
            related_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_in_collection_op_filter_with_variable(self):
        test_data = test_input_data.in_collection_op_filter_with_variable()

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
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_in_collection_op_filter_with_tag(self):
        test_data = test_input_data.in_collection_op_filter_with_tag()

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
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_in_collection_op_filter_with_optional_tag(self):
        test_data = test_input_data.in_collection_op_filter_with_optional_tag()

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
        expected_location_types = {
            base_location: 'Animal',
            revisited_base_location: 'Animal',
            parent_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_contains_op_filter_with_variable(self):
        test_data = test_input_data.contains_op_filter_with_variable()

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
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_contains_op_filter_with_tag(self):
        test_data = test_input_data.contains_op_filter_with_tag()

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
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_contains_op_filter_with_optional_tag(self):
        test_data = test_input_data.contains_op_filter_with_optional_tag()

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
        expected_location_types = {
            base_location: 'Animal',
            revisited_base_location: 'Animal',
            parent_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_substring_op_filter(self):
        test_data = test_input_data.has_substring_op_filter()

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
        expected_location_types = {
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_substring_op_filter_with_optional_tag(self):
        test_data = test_input_data.has_substring_op_filter_with_optional_tag()

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
        expected_location_types = {
            base_location: 'Animal',
            revisited_base_location: 'Animal',
            parent_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_edge_degree_op_filter(self):
        test_data = test_input_data.has_edge_degree_op_filter()

        base_location = helpers.Location(('Animal',))
        child_location = base_location.navigate_to_subpath('out_Animal_ParentOf')

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(  # the zero-edge check
                        u'&&',
                        expressions.BinaryComposition(
                            u'=',
                            expressions.Variable('$child_count', GraphQLInt),
                            expressions.ZeroLiteral
                        ),
                        expressions.BinaryComposition(
                            u'=',
                            expressions.LocalField('out_Animal_ParentOf'),
                            expressions.NullLiteral
                        )
                    ),
                    expressions.BinaryComposition(  # the non-zero-edge check
                        u'&&',
                        expressions.BinaryComposition(
                            u'!=',
                            expressions.LocalField('out_Animal_ParentOf'),
                            expressions.NullLiteral
                        ),
                        expressions.BinaryComposition(
                            u'=',
                            expressions.UnaryTransformation(
                                u'size',
                                expressions.LocalField('out_Animal_ParentOf')
                            ),
                            expressions.Variable('$child_count', GraphQLInt),
                        )
                    )
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse('out', 'Animal_ParentOf'),
            blocks.MarkLocation(child_location),
            blocks.OutputSource(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_name': expressions.OutputContextField(
                    child_location.navigate_to_field('name'), GraphQLString),
            }),
        ]
        expected_location_types = {
            base_location: 'Animal',
            child_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_edge_degree_op_filter_with_optional(self):
        test_data = test_input_data.has_edge_degree_op_filter_with_optional()

        base_location = helpers.Location(('Species',))
        animal_location = base_location.navigate_to_subpath('in_Animal_OfSpecies')
        child_location = animal_location.navigate_to_subpath('out_Animal_ParentOf')
        revisited_animal_location = animal_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({'Species'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('in', 'Animal_OfSpecies'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(  # the zero-edge check
                        u'&&',
                        expressions.BinaryComposition(
                            u'=',
                            expressions.Variable('$child_count', GraphQLInt),
                            expressions.ZeroLiteral
                        ),
                        expressions.BinaryComposition(
                            u'=',
                            expressions.LocalField('out_Animal_ParentOf'),
                            expressions.NullLiteral
                        )
                    ),
                    expressions.BinaryComposition(  # the non-zero-edge check
                        u'&&',
                        expressions.BinaryComposition(
                            u'!=',
                            expressions.LocalField('out_Animal_ParentOf'),
                            expressions.NullLiteral
                        ),
                        expressions.BinaryComposition(
                            u'=',
                            expressions.UnaryTransformation(
                                u'size',
                                expressions.LocalField('out_Animal_ParentOf')
                            ),
                            expressions.Variable('$child_count', GraphQLInt),
                        )
                    )
                )
            ),
            blocks.MarkLocation(animal_location),
            blocks.Traverse('out', 'Animal_ParentOf', optional=True),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(animal_location, optional=True),
            blocks.MarkLocation(revisited_animal_location),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'species_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'parent_name': expressions.OutputContextField(
                    animal_location.navigate_to_field('name'), GraphQLString),
                'child_name': expressions.TernaryConditional(
                    expressions.ContextFieldExistence(child_location),
                    expressions.OutputContextField(
                        child_location.navigate_to_field('name'), GraphQLString),
                    expressions.NullLiteral),
            }),
        ]
        expected_location_types = {
            base_location: 'Species',
            animal_location: 'Animal',
            child_location: 'Animal',
            revisited_animal_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_edge_degree_op_filter_with_fold(self):
        test_data = test_input_data.has_edge_degree_op_filter_with_fold()

        base_location = helpers.Location(('Species',))
        animal_location = base_location.navigate_to_subpath('in_Animal_OfSpecies')
        animal_fold = helpers.FoldScopeLocation(animal_location, ('out', 'Animal_ParentOf'))

        expected_blocks = [
            blocks.QueryRoot({'Species'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('in', 'Animal_OfSpecies'),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(  # the zero-edge check
                        u'&&',
                        expressions.BinaryComposition(
                            u'=',
                            expressions.Variable('$child_count', GraphQLInt),
                            expressions.ZeroLiteral
                        ),
                        expressions.BinaryComposition(
                            u'=',
                            expressions.LocalField('out_Animal_ParentOf'),
                            expressions.NullLiteral
                        )
                    ),
                    expressions.BinaryComposition(  # the non-zero-edge check
                        u'&&',
                        expressions.BinaryComposition(
                            u'!=',
                            expressions.LocalField('out_Animal_ParentOf'),
                            expressions.NullLiteral
                        ),
                        expressions.BinaryComposition(
                            u'=',
                            expressions.UnaryTransformation(
                                u'size',
                                expressions.LocalField('out_Animal_ParentOf')
                            ),
                            expressions.Variable('$child_count', GraphQLInt),
                        )
                    )
                )
            ),
            blocks.MarkLocation(animal_location),
            blocks.Fold(animal_fold),
            blocks.Unfold(),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'species_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'parent_name': expressions.OutputContextField(
                    animal_location.navigate_to_field('name'), GraphQLString),
                'child_names': expressions.FoldedOutputContextField(
                    animal_fold, 'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_location_types = {
            base_location: 'Species',
            animal_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_on_output_variable(self):
        test_data = test_input_data.fold_on_output_variable()

        base_location = helpers.Location(('Animal',))
        base_fold = helpers.FoldScopeLocation(base_location, ('out', 'Animal_ParentOf'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.Unfold(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_names_list': expressions.FoldedOutputContextField(
                    base_fold, 'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_after_traverse(self):
        test_data = test_input_data.fold_after_traverse()

        base_location = helpers.Location(('Animal',))
        parent_location = base_location.navigate_to_subpath('in_Animal_ParentOf')
        parent_fold = helpers.FoldScopeLocation(parent_location, ('out', 'Animal_ParentOf'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Traverse('in', 'Animal_ParentOf'),
            blocks.MarkLocation(parent_location),
            blocks.Fold(parent_fold),
            blocks.Unfold(),
            blocks.Backtrack(base_location),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'sibling_and_self_names_list': expressions.FoldedOutputContextField(
                    parent_fold, 'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
            parent_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_outputs_in_same_fold(self):
        test_data = test_input_data.multiple_outputs_in_same_fold()

        base_location = helpers.Location(('Animal',))
        base_fold = helpers.FoldScopeLocation(base_location, ('out', 'Animal_ParentOf'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.Unfold(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_names_list': expressions.FoldedOutputContextField(
                    base_fold, 'name', GraphQLList(GraphQLString)),
                'child_uuids_list': expressions.FoldedOutputContextField(
                    base_fold, 'uuid', GraphQLList(GraphQLID)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_folds(self):
        test_data = test_input_data.multiple_folds()

        base_location = helpers.Location(('Animal',))
        base_out_fold = helpers.FoldScopeLocation(base_location, ('out', 'Animal_ParentOf'))
        base_in_fold = helpers.FoldScopeLocation(base_location, ('in', 'Animal_ParentOf'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_out_fold),
            blocks.Unfold(),
            blocks.Fold(base_in_fold),
            blocks.Unfold(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_names_list': expressions.FoldedOutputContextField(
                    base_out_fold, 'name', GraphQLList(GraphQLString)),
                'child_uuids_list': expressions.FoldedOutputContextField(
                    base_out_fold, 'uuid', GraphQLList(GraphQLID)),
                'parent_names_list': expressions.FoldedOutputContextField(
                    base_in_fold, 'name', GraphQLList(GraphQLString)),
                'parent_uuids_list': expressions.FoldedOutputContextField(
                    base_in_fold, 'uuid', GraphQLList(GraphQLID)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_date_and_datetime_fields(self):
        test_data = test_input_data.fold_date_and_datetime_fields()

        base_location = helpers.Location(('Animal',))
        base_parent_fold = helpers.FoldScopeLocation(base_location, ('out', 'Animal_ParentOf'))
        base_fed_at_fold = helpers.FoldScopeLocation(base_location, ('out', 'Animal_FedAt'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.Unfold(),
            blocks.Fold(base_fed_at_fold),
            blocks.Unfold(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_birthdays_list': expressions.FoldedOutputContextField(
                    base_parent_fold, 'birthday', GraphQLList(GraphQLDate)),
                'fed_at_datetimes_list': expressions.FoldedOutputContextField(
                    base_fed_at_fold, 'event_date', GraphQLList(GraphQLDateTime)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_to_union_base_type_inside_fold(self):
        # Given type_equivalence_hints = { Event: EventOrBirthEvent },
        # the coercion should be optimized away as a no-op.
        test_data = test_input_data.coercion_to_union_base_type_inside_fold()

        base_location = helpers.Location(('Animal',))
        base_parent_fold = helpers.FoldScopeLocation(
            base_location, ('out', 'Animal_ImportantEvent'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.Unfold(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'important_events': expressions.FoldedOutputContextField(
                    base_parent_fold, 'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_no_op_coercion_inside_fold(self):
        # The type where the coercion is applied is already Entity, so the coercion is a no-op.
        test_data = test_input_data.no_op_coercion_inside_fold()

        base_location = helpers.Location(('Animal',))
        base_parent_fold = helpers.FoldScopeLocation(
            base_location, ('out', 'Entity_Related'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.Unfold(),
            blocks.ConstructResult({
                'animal_name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'related_entities': expressions.FoldedOutputContextField(
                    base_parent_fold, 'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_within_fold_scope(self):
        test_data = test_input_data.filter_within_fold_scope()

        base_location = helpers.Location(('Animal',))
        base_parent_fold = helpers.FoldScopeLocation(base_location, ('out', 'Animal_ParentOf'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'=',
                    expressions.LocalField('name'),
                    expressions.Variable('$desired', GraphQLString)
                )
            ),
            blocks.Unfold(),
            blocks.ConstructResult({
                'name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_list': expressions.FoldedOutputContextField(
                    base_parent_fold, 'name', GraphQLList(GraphQLString)),
                'child_descriptions': expressions.FoldedOutputContextField(
                    base_parent_fold, 'description', GraphQLList(GraphQLString)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_fold_scope(self):
        test_data = test_input_data.filter_on_fold_scope()

        base_location = helpers.Location(('Animal',))
        base_parent_fold = helpers.FoldScopeLocation(base_location, ('out', 'Animal_ParentOf'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'||',
                    expressions.BinaryComposition(
                        u'=',
                        expressions.LocalField('name'),
                        expressions.Variable('$desired', GraphQLString)
                    ),
                    expressions.BinaryComposition(
                        u'contains',
                        expressions.LocalField('alias'),
                        expressions.Variable('$desired', GraphQLString)
                    )
                )
            ),
            blocks.Unfold(),
            blocks.ConstructResult({
                'name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'child_list': expressions.FoldedOutputContextField(
                    base_parent_fold, 'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_on_interface_within_fold_scope(self):
        test_data = test_input_data.coercion_on_interface_within_fold_scope()

        base_location = helpers.Location(('Animal',))
        base_parent_fold = helpers.FoldScopeLocation(base_location, ('out', 'Entity_Related'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.CoerceType({'Animal'}),
            blocks.Unfold(),
            blocks.ConstructResult({
                'name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'related_animals': expressions.FoldedOutputContextField(
                    base_parent_fold, 'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_on_union_within_fold_scope(self):
        test_data = test_input_data.coercion_on_union_within_fold_scope()

        base_location = helpers.Location(('Animal',))
        base_parent_fold = helpers.FoldScopeLocation(
            base_location, ('out', 'Animal_ImportantEvent'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.CoerceType({'BirthEvent'}),
            blocks.Unfold(),
            blocks.ConstructResult({
                'name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'birth_events': expressions.FoldedOutputContextField(
                    base_parent_fold, 'name', GraphQLList(GraphQLString)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_filters_and_multiple_outputs_within_fold_scope(self):
        test_data = test_input_data.coercion_filters_and_multiple_outputs_within_fold_scope()

        base_location = helpers.Location(('Animal',))
        base_parent_fold = helpers.FoldScopeLocation(base_location, ('out', 'Entity_Related'))

        expected_blocks = [
            blocks.QueryRoot({'Animal'}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.CoerceType({'Animal'}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'has_substring',
                    expressions.LocalField('name'),
                    expressions.Variable('$substring', GraphQLString)
                )
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    u'<=',
                    expressions.LocalField('birthday'),
                    expressions.Variable('$latest', GraphQLDate)
                )
            ),
            blocks.Unfold(),
            blocks.ConstructResult({
                'name': expressions.OutputContextField(
                    base_location.navigate_to_field('name'), GraphQLString),
                'related_animals': expressions.FoldedOutputContextField(
                    base_parent_fold, 'name', GraphQLList(GraphQLString)),
                'related_birthdays': expressions.FoldedOutputContextField(
                    base_parent_fold, 'birthday', GraphQLList(GraphQLDate)),
            }),
        ]
        expected_location_types = {
            # The folded location was never traversed to, so it does not appear here.
            base_location: 'Animal',
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)
