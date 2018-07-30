# Copyright 2017-present Kensho Technologies, LLC.
import string
import unittest

import six

from ..compiler.compiler_frontend import graphql_to_ir
from ..exceptions import GraphQLCompilationError, GraphQLParsingError, GraphQLValidationError
from .test_helpers import get_schema


class IrGenerationErrorTests(unittest.TestCase):
    """Ensure illegal inputs raise proper exceptions."""

    def setUp(self):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        self.maxDiff = None
        self.schema = get_schema()

    def test_repeated_field_name(self):
        repeated_property_field = '''{
            Animal {
                name @output(out_name: "name")
                name
            }
        }'''

        repeated_property_field_with_directives = '''{
            Animal {
                name @output(out_name: "name")
                name @filter(op_name: "=", value: ["$wanted"])
            }
        }'''

        repeated_vertex_field = '''{
            Animal {
                out_Animal_ParentOf {
                    name @output(out_name: "child_name")
                }
                out_Animal_ParentOf {
                    uuid @output(out_name: "child_uuid")
                }
            }
        }'''

        for graphql in (repeated_property_field,
                        repeated_property_field_with_directives,
                        repeated_vertex_field):
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, graphql)

    def test_output_source_directive_constraints(self):
        output_source_not_on_last_vertex_element = '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                out_Animal_ParentOf @output_source {
                    name @output(out_name: "parent_name")
                }
                out_Animal_FedAt {
                    name @output(out_name: "event_name")
                    event_date @output(out_name: "event_date")
                }
            }
        }'''

        output_source_on_non_vertex_element = '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                out_Animal_FedAt {
                    name @output(out_name: "event_name") @output_source
                    event_date @output(out_name: "event_date")
                }
            }
        }'''

        multiple_output_sources = '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                out_Animal_FedAt @output_source {
                    name @output(out_name: "event_name") @output_source
                    event_date @output(out_name: "event_date")
                }
            }
        }'''

        output_source_on_optional_vertex = '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                out_Animal_FedAt @output_source @optional {
                    name @output(out_name: "event_name")
                    event_date @output(out_name: "event_date")
                }
            }
        }'''

        output_source_on_fold_vertex = '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                out_Animal_FedAt @output_source @fold {
                    name @output(out_name: "event_name")
                    event_date @output(out_name: "event_date")
                }
            }
        }'''

        for graphql in (output_source_not_on_last_vertex_element,
                        output_source_on_non_vertex_element,
                        multiple_output_sources,
                        output_source_on_optional_vertex,
                        output_source_on_fold_vertex):
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, graphql)

    def test_optional_directive_constraints(self):
        optional_on_property_field = '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                out_Animal_ParentOf {
                    name @output(out_name: "parent_name") @optional
                }
            }
        }'''

        optional_on_root_vertex = '''{
            Animal @optional {
                name @output(out_name: "uuid")
            }
        }'''

        output_source_inside_optional_block = '''{
            Animal {
                out_Animal_ParentOf @optional {
                    out_Animal_FedAt @output_source {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''

        recurse_traversal_inside_optional_block = '''{
            Animal {
                out_Animal_ParentOf @optional {
                out_Animal_FedAt @recurse(depth: 3) {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''

        fold_traversal_inside_optional_block = '''{
            Animal {
                out_Animal_ParentOf @optional {
                    out_Animal_FedAt @fold {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''

        optional_traversal_inside_optional_block = '''{
            Animal {
                out_Animal_ParentOf @optional {
                    out_Animal_FedAt @optional {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''

        optional_on_output_source_vertex_field = '''{
            Animal {
                out_Animal_ParentOf @optional @output_source {
                    uuid @output(out_name: "uuid")
                }
            }
        }'''

        optional_on_recurse_vertex_field = '''{
            Animal {
                out_Animal_ParentOf @optional @recurse(depth: 3) {
                    uuid @output(out_name: "uuid")
                }
            }
        }'''

        optional_on_fold_vertex_field = '''{
            Animal {
                out_Animal_ParentOf @optional @fold {
                    uuid @output(out_name: "uuid")
                }
            }
        }'''

        for graphql in (optional_on_property_field,
                        optional_on_root_vertex,
                        output_source_inside_optional_block,
                        recurse_traversal_inside_optional_block,
                        fold_traversal_inside_optional_block,
                        optional_traversal_inside_optional_block,
                        optional_on_output_source_vertex_field,
                        optional_on_recurse_vertex_field,
                        optional_on_fold_vertex_field):
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, graphql)

    def test_fold_directive_constraints(self):
        fold_on_property_field = '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                out_Animal_ParentOf {
                    name @output(out_name: "parent_name") @fold
                }
            }
        }'''

        fold_on_root_vertex = '''{
            Animal @fold {
                name @output(out_name: "uuid")
            }
        }'''

        multi_level_outputs_inside_fold_block = '''{
            Animal {
                out_Animal_ParentOf @fold {
                    uuid @output(out_name: "uuid")
                    out_Animal_FedAt {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''

        traversal_inside_fold_block_after_output = '''{
            Animal {
                out_Animal_ParentOf @fold {
                    in_Animal_ParentOf {
                        uuid @output(out_name: "uuid")
                        out_Animal_FedAt {
                            uuid
                        }
                    }
                }
            }
        }'''

        no_outputs_inside_fold_block = '''{
            Animal {
                uuid @output(out_name: "uuid")
                out_Animal_ParentOf @fold {
                    name
                }
            }
        }'''

        fold_within_fold = '''{
            Animal {
                out_Animal_ParentOf @fold {
                    out_Animal_FedAt @fold {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''

        optional_within_fold = '''{
            Animal {
                out_Animal_ParentOf @fold {
                    out_Animal_FedAt @optional {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''

        recurse_within_fold = '''{
            Animal {
                out_Animal_ParentOf @fold {
                    in_Animal_ParentOf @recurse(depth: 2) {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''

        output_source_within_fold = '''{
            Animal {
                out_Animal_ParentOf @fold {
                    out_Animal_FedAt @output_source {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }'''

        multiple_vertex_fields_within_fold = '''{
            Animal {
                out_Animal_ParentOf @fold {
                    out_Animal_FedAt {
                        uuid @output(out_name: "uuid")
                    }
                    in_Animal_ParentOf {
                        name
                    }
                }
            }
        }'''

        multiple_vertex_fields_within_fold_after_traverse = '''{
            Animal {
                out_Animal_ParentOf @fold {
                    in_Animal_ParentOf {
                        out_Animal_FedAt {
                            uuid @output(out_name: "uuid")
                        }
                        out_Animal_OfSpecies {
                            name
                        }
                    }
                }
            }
        }'''

        for graphql in (fold_on_property_field,
                        fold_on_root_vertex,
                        multi_level_outputs_inside_fold_block,
                        traversal_inside_fold_block_after_output,
                        no_outputs_inside_fold_block,
                        fold_within_fold,
                        optional_within_fold,
                        recurse_within_fold,
                        output_source_within_fold,
                        multiple_vertex_fields_within_fold,
                        multiple_vertex_fields_within_fold_after_traverse):
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, graphql)

    def test_output_directive_constraints(self):
        output_on_vertex_field = (GraphQLCompilationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                out_Animal_ParentOf @output(out_name: "parent") {
                    uuid
                }
            }
        }''')

        output_without_name = (GraphQLValidationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                name @output
            }
        }''')

        output_with_empty_name = (GraphQLCompilationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                name @output(out_name: "")
            }
        }''')

        output_with_name_starting_with_digit = (GraphQLCompilationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                name @output(out_name: "1uuid")
            }
        }''')

        output_with_duplicated_name = (GraphQLCompilationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                uuid @output(out_name: "uuid")
                out_Animal_ParentOf {
                    uuid @output(out_name: "uuid")
                }
            }
        }''')

        output_with_illegal_name = (GraphQLCompilationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                name @output(out_name: "name'\\\\\\"")
            }
        }''')

        for expected_error, graphql in (output_on_vertex_field,
                                        output_without_name,
                                        output_with_duplicated_name,
                                        output_with_illegal_name,
                                        output_with_empty_name,
                                        output_with_name_starting_with_digit):
            with self.assertRaises(expected_error):
                graphql_to_ir(self.schema, graphql)

    def test_tag_directive_constraints(self):
        tag_on_vertex_field = (GraphQLCompilationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                out_Animal_ParentOf @tag(tag_name: "role") {
                    uuid @output(out_name: "uuid")
                }
            }
        }''')

        tag_without_name = (GraphQLValidationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                name @tag
                uuid @output(out_name: "uuid")
            }
        }''')

        tag_with_duplicated_name = (GraphQLCompilationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                name @output(out_name: "name")
                uuid @tag(tag_name: "uuid")
                out_Animal_ParentOf {
                    uuid @tag(tag_name: "uuid")
                }
            }
        }''')

        tag_with_illegal_name = (GraphQLCompilationError, '''{
            Animal @filter(op_name: "name_or_alias", value: ["$animal_name"]) {
                name @tag(tag_name: "name'\\\\\\"")
                uuid @output(out_name: "uuid")
            }
        }''')

        tag_within_fold_scope = (GraphQLCompilationError, '''{
            Animal {
                out_Animal_ParentOf @fold {
                    name @tag(tag_name: "name")
                    uuid @output(out_name: "uuid")
                }
            }
        }''')

        for expected_error, graphql in (tag_on_vertex_field,
                                        tag_without_name,
                                        tag_with_duplicated_name,
                                        tag_with_illegal_name,
                                        tag_within_fold_scope):
            with self.assertRaises(expected_error):
                graphql_to_ir(self.schema, graphql)

    def test_recurse_directive_constraints(self):
        recurse_on_property_field = (GraphQLCompilationError, '''{
            Animal {
                name @recurse(depth: 3)
                uuid @output(out_name: "uuid")
            }
        }''')

        recurse_on_root_vertex = (GraphQLCompilationError, '''{
            Animal @recurse(depth: 3) {
                name @output(out_name: "name")
            }
        }''')

        recurse_with_illegal_depth = (GraphQLCompilationError, '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 0) {
                    name @output(out_name: "name")
                }
            }
        }''')

        recurse_at_fold_scope = (GraphQLCompilationError, '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 3) @fold {
                    name @output(out_name: "name")
                }
            }
        }''')

        recurse_within_fold_scope = (GraphQLCompilationError, '''{
            Animal {
                out_Animal_ParentOf @fold {
                    out_Animal_ParentOf @recurse(depth: 3) {
                        name @output(out_name: "name")
                    }
                }
            }
        }''')

        # Note that "color" is a property on Animal, but not on Species.
        # However, @recurse emits both the starting vertex (0-depth) as well as deeper vertices,
        # so this query is invalid. The "in_Animal_OfSpecies" vertex field is not of union type,
        # so this fails the type safety check for the @recurse directive.
        recurse_with_type_mismatch = (GraphQLCompilationError, '''{
            Species {
                in_Animal_OfSpecies @recurse(depth: 3) {
                    color @output(out_name: "color")
                }
            }
        }''')

        for expected_error, graphql in (recurse_on_property_field,
                                        recurse_on_root_vertex,
                                        recurse_with_illegal_depth,
                                        recurse_at_fold_scope,
                                        recurse_within_fold_scope,
                                        recurse_with_type_mismatch):
            with self.assertRaises(expected_error):
                graphql_to_ir(self.schema, graphql)

    def test_filter_directive_bad_op_name(self):
        with self.assertRaises(GraphQLCompilationError):
            graphql_to_ir(self.schema, '''{
                Event @filter(op_name: "non_existent", value: ["$a"]) {
                    name @output(out_name: "name")
                }
            }''')

    def test_filter_directive_undeclared_argument(self):
        with self.assertRaises(GraphQLCompilationError):
            graphql_to_ir(self.schema, '''{
                Event @filter(op_name: "name_or_alias", value: ["%not_there"]) {
                    name @output(out_name: "name")
                }
            }''')

    def test_filter_directive_literal_argument(self):
        # Literal arguments are currently not supported, and instead raise errors.
        with self.assertRaises(GraphQLCompilationError):
            graphql_to_ir(self.schema, '''{
                Event @filter(op_name: "name_or_alias", value: ["literal"]) {
                    name @output(out_name: "name")
                }
            }''')

    def test_filter_directive_non_list_value_argument(self):
        with self.assertRaises(GraphQLValidationError):
            graphql_to_ir(self.schema, '''{
                Event @filter(op_name: "name_or_alias", value: "$not_a_list") {
                    name @output(out_name: "name")
                }
            }''')

    def test_filter_directive_wrong_location(self):
        invalid_graphql_inputs = [
            # 'name_or_alias' must be on a vertex field that has 'name' and 'alias' properties,
            # Event vertex fields and property fields (like 'name') do not satisfy this.
            '''{
                Animal {
                    name @filter(op_name: "name_or_alias", value: ["$foo"])
                    description @output(out_name: "description_text")
                }
            }''',
            '''{
                Location @filter(op_name: "name_or_alias", value: ["$foo"]) {
                    name @output(out_name: "name")
                }
            }''',

            # '=' must be on a property field, not a vertex field
            '''{
                Event @filter(op_name: "=", value: ["$foo"]) {
                    name @output(out_name: "name")
                }
            }''',

            # 'between' must be on a property field
            '''{
                Event @filter(op_name: "between", value: ["$foo"]) {
                    name @output(out_name: "name")
                }
            }''',
        ]

        for graphql in invalid_graphql_inputs:
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, graphql)

    def test_filter_directive_bad_arg_counts(self):
        def generate_args_string(num_args):
            """Generates a GraphQL array with the given args, as a string."""
            if num_args == 0:
                return u'[]'

            variable_names = string.ascii_lowercase
            if num_args >= len(variable_names):
                raise AssertionError('Invalid test data, too many variables to represent.')

            args = (variable_names[i] for i in six.moves.xrange(num_args))
            array_contents = u','.join(u'"${}"'.format(x) for x in args)
            return u'[{}]'.format(array_contents)

        expected_arg_counts = [
            # Using % rather than .format() because GraphQL uses lots of curly braces,
            # which are annoying to escape the way .format() likes them.
            (1, '''{
                Animal @filter(op_name: "name_or_alias", value: %s) {
                    name @output(out_name: "name")
                }
            }'''),
            (1, '''{
                Event {
                    name @filter(op_name: "=", value: %s) @output(out_name: "name")
                }
            }'''),
            (2, '''{
                Event {
                    name @output(out_name: "name")
                    event_date @filter(op_name: "between", value: %s)
                }
            }''')
        ]

        for expected_arg_count, base_query in expected_arg_counts:
            # Try using just the right number of arguments, expect no error.
            args = generate_args_string(expected_arg_count)
            graphql_to_ir(self.schema, base_query % (args))

            # Try using one argument fewer or too many, expect an error.
            for num_args in (expected_arg_count - 1, expected_arg_count + 1):
                args = generate_args_string(num_args)
                with self.assertRaises(GraphQLCompilationError):
                    graphql_to_ir(self.schema, base_query % (args))

    def test_simple_bad_graphql(self):
        bad_graphqls = (
            (GraphQLParsingError, 'not really graphql'),

            # graphql that doesn't match the graph schema
            (GraphQLValidationError, '''{
                NonExistentVertex {
                    name @output(out_name: "name")
                }
            }'''),

            # more than one graphql definition block
            (GraphQLValidationError, '''{
                Animal {
                    name @output(out_name: "animal_name")
                }
            }

            {
                Species {
                    name @output(out_name: "species_name")
                }
            }'''),

            # more than one root selection
            (GraphQLCompilationError, '''{
                Animal {
                    name @output(out_name: "animal_name")
                }
                Species {
                    name @output(out_name: "species_name")
                }
            }'''),
        )

        for expected_error, graphql in bad_graphqls:
            with self.assertRaises(expected_error):
                graphql_to_ir(self.schema, graphql)

    def test_duplicate_directive_on_same_field(self):
        # sanity check: the non-duplicate version of the query compiles fine
        graphql_to_ir(self.schema, '''{
            Event {
                name @tag(tag_name: "name")
                event_date @output(out_name: "date")
            }
        }''')

        with self.assertRaises(GraphQLCompilationError):
            graphql_to_ir(self.schema, '''{
                Event {
                    name @tag(tag_name: "name") @tag(tag_name: "name2")
                    event_date @output(out_name: "date")
                }
            }''')

    def test_property_field_after_vertex_field(self):
        # sanity check: the correctly-ordered version of the query compiles fine
        graphql_to_ir(self.schema, '''{
            Event {
                name @output(out_name: "name")
                event_date @tag(tag_name: "date")
                in_Animal_FedAt {
                    name @output(out_name: "animal")
                }
            }
        }''')

        invalid_queries = (
            '''{
                Event {
                    name @output(out_name: "name")
                    in_Animal_FedAt {
                        name @output(out_name: "animal")
                    }
                    event_date @tag(tag_name: "date")
                }
            }''', '''{
                Event {
                    in_Animal_FedAt {
                        name @output(out_name: "animal")
                    }
                    name @output(out_name: "name")
                    event_date @tag(tag_name: "date")
                }
            }'''
        )

        for invalid_graphql in invalid_queries:
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, invalid_graphql)

    def test_fragment_and_fields_in_same_selection(self):
        invalid_graphql_queries = (
            # Property field and fragment in the same selection set.
            '''{
                Animal {
                    name @output(out_name: "animal_name")
                    out_Entity_Related {
                        name @output(out_name: "related_name")
                        ... on Animal {
                            out_Animal_OfSpecies {
                                name @output(out_name: "related_animal_species")
                            }
                        }
                    }
                }
            }''',

            # Vertex field and fragment in the same selection set.
            '''{
                Animal {
                    name @output(out_name: "animal_name")
                    out_Entity_Related {
                        out_Entity_Related {
                            name @output(out_name: "second_order_related_name")
                        }
                        ... on Animal {
                            name @output(out_name: "related_animal_name")
                        }
                    }
                }
            }''',

            # Both types of fields, and a fragment in the same selection set.
            '''{
                Animal {
                    name @output(out_name: "animal_name")
                    out_Entity_Related {
                        name @output(out_name: "related_name")
                        out_Entity_Related {
                            name @output(out_name: "second_order_related_name")
                        }
                        ... on Animal {
                            out_Animal_OfSpecies {
                                name @output(out_name: "related_animal_species")
                            }
                        }
                    }
                }
            }''')

        for invalid_graphql in invalid_graphql_queries:
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, invalid_graphql)

    def test_directive_on_fragment(self):
        invalid_graphql = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Entity_Related {
                    ... on Animal @optional {
                        name @output(out_name: "related_name")
                        out_Animal_OfSpecies {
                            name @output(out_name: "related_animal_species")
                        }
                    }
                }
            }
        }'''

        with self.assertRaises(GraphQLValidationError):
            graphql_to_ir(self.schema, invalid_graphql)

    def test_more_than_one_fragment_in_scope(self):
        invalid_graphql = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Entity_Related {
                    ... on Animal {
                        name @output(out_name: "related_animal_name")
                        out_Animal_OfSpecies {
                            name @output(out_name: "related_animal_species")
                        }
                    }
                    ... on Species {
                        name @output(out_name: "related_species")
                    }
                }
            }
        }'''

        with self.assertRaises(GraphQLCompilationError):
            graphql_to_ir(self.schema, invalid_graphql)

    def test_fragment_on_nonexistent_type(self):
        invalid_graphql = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Entity_Related {
                    ... on NonExistentType {
                        name @output(out_name: "related_animal_name")
                        out_Animal_OfSpecies {
                            name @output(out_name: "related_animal_species")
                        }
                    }
                }
            }
        }'''

        with self.assertRaises(GraphQLValidationError):
            graphql_to_ir(self.schema, invalid_graphql)

    def test_filter_on_union_type_field(self):
        # Filtering cannot be applied on a union type, because we don't yet know
        # what fields are available at the location.
        invalid_graphql = '''{
            Species {
                name @output(out_name: "species_name")
                out_Species_Eats @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                    ... on Food {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }'''

        with self.assertRaises(GraphQLCompilationError):
            graphql_to_ir(self.schema, invalid_graphql)

    def test_no_output_fields(self):
        # The GraphQL query must have at least one field marked @output, otherwise
        # why query at all if you don't want any results?
        invalid_graphql = '''{
            Species {
                out_Species_Eats {
                    ... on Food {
                        name @filter(op_name: "=", value: ["$food_name"])
                    }
                }
            }
        }'''

        with self.assertRaises(GraphQLCompilationError):
            graphql_to_ir(self.schema, invalid_graphql)

    def test_type_coercion_immediately_after_query_root(self):
        # The below pattern of applying a type coercion immediately after specifying a wider
        # type in the query root is nonsensical. Make sure we raise an appropriate error.
        invalid_graphql = '''{
            Entity {
                ... on Animal {
                    name @output(out_name: "animal")
                }
            }
        }'''

        with self.assertRaises(GraphQLCompilationError):
            graphql_to_ir(self.schema, invalid_graphql)

    def test_filter_graphql_type_validation(self):
        invalid_queries = [
            # The "=" filter requires a GraphQL leaf type on its left side,
            # but the "alias" field is a List of String. This should cause an error.
            '''{
                Animal {
                    name @output(out_name: "animal")
                    alias @filter(op_name: "=", value: ["$wanted"])
                }
            }''',

            # The "in_collection" filter requires a GraphQL leaf type on its left side,
            # but the "alias" field is a List of String. This should cause an error.
            '''{
                Animal {
                    name @output(out_name: "animal")
                    alias @filter(op_name: "in_collection", value: ["$wanted"])
                }
            }''',

            # The "has_substring" filter requires a GraphQLString type on its left side,
            # but the "alias" field is a List of String. This should cause an error.
            '''{
                Animal {
                    name @output(out_name: "animal")
                    alias @filter(op_name: "has_substring", value: ["$wanted"])
                }
            }''',

            # The "between" filter requires a GraphQL leaf type on its left side,
            # but the "alias" field is a List of String. This should cause an error.
            '''{
                Animal {
                    name @output(out_name: "animal")
                    alias @filter(op_name: "between", value: ["$left", "$right"])
                }
            }''',

            # The "contains" filter requires a GraphQLList on its left side,
            # but the "name" field is a List of String. This should cause an error.
            '''{
                Animal {
                    name @output(out_name: "animal")
                         @filter(op_name: "contains", value: ["$wanted"])
                }
            }''',
        ]

        for invalid_graphql in invalid_queries:
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, invalid_graphql)

    def test_input_type_validation(self):
        invalid_queries = [
            # The inferred types for "wanted" conflict between String and ID.
            '''{
                Animal {
                    name @filter(op_name: "=", value: ["$wanted"]) @output(out_name: "name")
                    uuid @filter(op_name: "=", value: ["$wanted"])
                }
            }''',

            # The inferred types for "wanted" conflict between String and ID.
            '''{
                Animal {
                    name @output(out_name: "name")
                    uuid @filter(op_name: "=", value: ["$wanted"])
                    alias @filter(op_name: "contains", value: ["$wanted"])
                }
            }''',
        ]

        for invalid_graphql in invalid_queries:
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, invalid_graphql)

    def test_tag_type_validation(self):
        invalid_queries = [
            # The inferred types for "tagged" conflict between String and ID.
            '''{
                Animal {
                    name @tag(tag_name: "tagged") @output(out_name: "name")
                    out_Animal_ParentOf {
                        uuid @filter(op_name: "=", value: ["%tagged"])
                    }
                }
            }''',

            # The inferred types for "tagged" conflict between String and ID.
            '''{
                Animal {
                    uuid @tag(tag_name: "tagged")
                    out_Animal_ParentOf {
                        name @filter(op_name: "=", value: ["%tagged"]) @output(out_name: "name")
                    }
                }
            }''',

            # The inferred types for "tagged" conflict between String and ID.
            '''{
                Animal {
                    uuid @tag(tag_name: "tagged") @output(out_name: "uuid")
                    out_Animal_ParentOf {
                        alias @filter(op_name: "contains", value: ["%tagged"])
                    }
                }
            }''',
        ]

        for invalid_graphql in invalid_queries:
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, invalid_graphql)

    def test_invalid_variable_types(self):
        # Variables currently cannot represent lists of Dates or lists of DateTimes.
        # Ensure such use of Variables causes compilation errors.
        invalid_queries = [
            # $list_of_dates is, unsurprisingly, a Variable of type List of Date
            '''{
                Animal {
                    name @output(out_name: "name")
                    birthday @filter(op_name: "in_collection", value: ["$list_of_dates"])
                }
            }''',

            # $list_of_datetimes is, unsurprisingly, a Variable of type List of DateTime
            '''{
                Event {
                    name @output(out_name: "name")
                    event_date @filter(op_name: "in_collection", value: ["$list_of_datetimes"])
                }
            }'''
        ]

        for invalid_graphql in invalid_queries:
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, invalid_graphql)

    def test_invalid_edge_degree_queries(self):
        invalid_queries = [
            # Can't filter with "has_edge_degree" on the root vertex field -- there's no edge.
            '''{
                Animal @filter(op_name: "has_edge_degree", value: ["$degree"]) {
                    name @output(out_name: "name")
                }
            }''',

            # Can't filter with "has_edge_degree" on a property field -- there's no edge.
            '''{
                Animal {
                    name @output(out_name: "name")
                         @filter(op_name: "has_edge_degree", value: ["$degree"])
                }
            }''',

            # Can't filter with "has_edge_degree" on a type coercion -- it has to be on the field.
            '''{
                Animal {
                    out_Entity_Related {
                        ... on Animal @filter(op_name: "has_edge_degree", value: ["$degree"]) {
                            name @output(out_name: "related")
                        }
                    }
                }
            }''',

            # Can't filter with "has_edge_degree" with a tagged value that isn't of Int type.
            '''{
                Animal {
                    out_Animal_ParentOf {
                        name @output(out_name: "name") @tag(tag_name: "parent")
                    }

                    out_Animal_OfSpecies @filter(op_name: "has_edge_degree", value: ["%parent"]) {
                        name @output(out_name: "species")
                    }
                }
            }''',

            # We currently do not support tagged values as "has_edge_degree" arguments.
            '''{
                Animal {
                    name @output(out_name: "animal_name")
                    out_Animal_OfSpecies @optional {
                        limbs @tag(tag_name: "limb_count")
                    }
                    out_Animal_ParentOf
                            @filter(op_name: "has_edge_degree", value: ["%limb_count"]) {
                        name @output(out_name: "child_name")
                    }
                }
            }'''
        ]

        for invalid_graphql in invalid_queries:
            with self.assertRaises(GraphQLCompilationError):
                graphql_to_ir(self.schema, invalid_graphql)
