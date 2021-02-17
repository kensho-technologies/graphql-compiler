# Copyright 2017-present Kensho Technologies, LLC.
import unittest

from graphql import GraphQLID, GraphQLInt, GraphQLList, GraphQLString
import six

from . import test_input_data
from ..compiler import blocks, expressions, helpers
from ..compiler.compiler_frontend import OutputMetadata, graphql_to_ir
from ..schema import (
    COUNT_META_FIELD_NAME,
    TYPENAME_META_FIELD_NAME,
    GraphQLDate,
    GraphQLDateTime,
    GraphQLDecimal,
)
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

    compilation_results = graphql_to_ir(
        test_case.schema,
        test_data.graphql_input,
        type_equivalence_hints=schema_based_type_equivalence_hints,
    )

    compare_ir_blocks(test_case, expected_blocks, compilation_results.ir_blocks)
    compare_input_metadata(
        test_case, test_data.expected_input_metadata, compilation_results.input_metadata
    )
    test_case.assertEqual(test_data.expected_output_metadata, compilation_results.output_metadata)
    test_case.assertEqual(
        expected_location_types,
        get_comparable_location_types(compilation_results.query_metadata_table),
    )

    all_child_locations, revisits = compute_child_and_revisit_locations(expected_blocks)
    for parent_location, child_locations in six.iteritems(all_child_locations):
        for child_location in child_locations:
            child_info = compilation_results.query_metadata_table.get_location_info(child_location)
            test_case.assertEqual(parent_location, child_info.parent_location)

    test_case.assertEqual(
        all_child_locations,
        get_comparable_child_locations(compilation_results.query_metadata_table),
    )
    test_case.assertEqual(
        revisits, get_comparable_revisits(compilation_results.query_metadata_table)
    )


def get_comparable_location_types(query_metadata_table):
    """Return the dict of location -> GraphQL type name for each location in the query."""
    return {
        location: location_info.type.name
        for location, location_info in query_metadata_table.registered_locations
    }


def get_comparable_child_locations(query_metadata_table):
    """Return the dict of location -> set of child locations for each location in the query."""
    all_locations_with_possible_children = {
        location: set(query_metadata_table.get_child_locations(location))
        for location, _ in query_metadata_table.registered_locations
    }
    return {
        location: child_locations
        for location, child_locations in six.iteritems(all_locations_with_possible_children)
        if child_locations
    }


def get_comparable_revisits(query_metadata_table):
    """Return a dict location -> set of revisit locations for that starting location."""
    revisit_origins = {
        query_metadata_table.get_revisit_origin(location)
        for location, _ in query_metadata_table.registered_locations
    }

    intermediate_result = {
        location: set(query_metadata_table.get_all_revisits(location))
        for location in revisit_origins
    }

    return {
        location: revisits for location, revisits in six.iteritems(intermediate_result) if revisits
    }


def compute_child_and_revisit_locations(ir_blocks):
    """Return dicts describing the parent-child and revisit relationships for all query locations.

    Args:
        ir_blocks: list of IR blocks describing the given query

    Returns:
        tuple of:
            dict mapping parent location -> set of child locations (guaranteed to be non-empty)
            dict mapping revisit origin -> set of revisits (possibly empty)
    """
    if not ir_blocks:
        raise AssertionError("Unexpectedly received empty ir_blocks: {}".format(ir_blocks))

    first_block = ir_blocks[0]
    if not isinstance(first_block, blocks.QueryRoot):
        raise AssertionError(
            "Unexpectedly, the first IR block was not a QueryRoot: {} {}".format(
                first_block, ir_blocks
            )
        )

    # These block types do not affect the computed location structure.
    no_op_block_types = (
        blocks.Filter,
        blocks.ConstructResult,
        blocks.EndOptional,
        blocks.OutputSource,
        blocks.CoerceType,
    )

    current_location = None
    traversed_or_recursed_or_folded = False
    fold_started_at = None

    top_level_locations = set()
    parent_location = dict()  # location -> parent location
    child_locations = dict()  # location -> set of child locations
    revisits = dict()  # location -> set of revisit locations
    query_path_to_revisit_origin = dict()  # location query path -> its revisit origin

    # Walk the IR blocks and reconstruct the query's location structure.
    for block in ir_blocks[1:]:
        if isinstance(block, (blocks.Traverse, blocks.Fold, blocks.Recurse)):
            traversed_or_recursed_or_folded = True
            if isinstance(block, blocks.Fold):
                fold_started_at = current_location
        elif isinstance(block, blocks.Unfold):
            current_location = fold_started_at
        elif isinstance(block, blocks.MarkLocation):
            # Handle optional traversals and backtracks, due to the fact that
            # they might drop MarkLocations before and after themselves.
            if traversed_or_recursed_or_folded:
                block_parent_location = current_location
            else:
                block_parent_location = parent_location.get(current_location, None)

            if block_parent_location is not None:
                parent_location[block.location] = block_parent_location
                child_locations.setdefault(block_parent_location, set()).add(block.location)
            else:
                top_level_locations.add(current_location)

            current_location = block.location

            if isinstance(current_location, helpers.FoldScopeLocation):
                revisit_origin = None
            elif isinstance(current_location, helpers.Location):
                if current_location.query_path not in query_path_to_revisit_origin:
                    query_path_to_revisit_origin[current_location.query_path] = current_location
                    revisit_origin = None
                else:
                    revisit_origin = query_path_to_revisit_origin[current_location.query_path]
            else:
                raise AssertionError(
                    "Unreachable state reached: {} {}".format(current_location, ir_blocks)
                )

            if revisit_origin is not None:
                revisits.setdefault(revisit_origin, set()).add(current_location)

            traversed_or_recursed_or_folded = False
        elif isinstance(block, blocks.Backtrack):
            current_location = block.location
        elif isinstance(block, blocks.GlobalOperationsStart):
            # In the global operations section, there is no "current" location.
            current_location = None
        elif isinstance(block, no_op_block_types):
            # These blocks do not affect the computed location structure.
            pass
        elif isinstance(block, blocks.QueryRoot):
            raise AssertionError(
                "Unexpectedly encountered a second QueryRoot after the first "
                "IR block: {} {}".format(block, ir_blocks)
            )
        else:
            raise AssertionError(
                "Unexpected block type encountered: {} {}".format(block, ir_blocks)
            )

    return child_locations, revisits


class IrGenerationTests(unittest.TestCase):
    """Ensure valid inputs produce correct IR."""

    def setUp(self):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        self.maxDiff = None
        self.schema = get_schema()

    def test_immediate_output(self):
        test_data = test_input_data.immediate_output()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_immediate_output_custom_scalars(self):
        test_data = test_input_data.immediate_output_custom_scalars()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "birthday": expressions.OutputContextField(
                        base_location.navigate_to_field("birthday"), GraphQLDate
                    ),
                    "net_worth": expressions.OutputContextField(
                        base_location.navigate_to_field("net_worth"), GraphQLDecimal
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_immediate_filter_and_output(self):
        # Ensure that all basic comparison operators output correct code in this simple case.
        comparison_operators = {"=", "!=", ">", "<", ">=", "<="}

        for operator in comparison_operators:
            graphql_input = """{
                Animal {
                    name @filter(op_name: "%s", value: ["$wanted"]) @output(out_name: "animal_name")
                }
            }""" % (
                operator,
            )

            base_location = helpers.Location(("Animal",))

            expected_blocks = [
                blocks.QueryRoot({"Animal"}),
                blocks.Filter(
                    expressions.BinaryComposition(
                        operator,
                        expressions.LocalField("name", GraphQLString),
                        expressions.Variable("$wanted", GraphQLString),
                    )
                ),
                blocks.MarkLocation(base_location),
                blocks.GlobalOperationsStart(),
                blocks.ConstructResult(
                    {
                        "animal_name": expressions.OutputContextField(
                            base_location.navigate_to_field("name"), GraphQLString
                        )
                    }
                ),
            ]
            expected_location_types = {
                base_location: "Animal",
            }
            expected_output_metadata = {
                "animal_name": OutputMetadata(type=GraphQLString, optional=False, folded=False),
            }
            expected_input_metadata = {
                "wanted": GraphQLString,
            }

            test_data = test_input_data.CommonTestData(
                graphql_input=graphql_input,
                expected_output_metadata=expected_output_metadata,
                expected_input_metadata=expected_input_metadata,
                type_equivalence_hints=None,
            )

            check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_immediate_output_with_custom_scalar_filter(self):
        test_data = test_input_data.immediate_output_with_custom_scalar_filter()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.LocalField("net_worth", GraphQLDecimal),
                    expressions.Variable("$min_worth", GraphQLDecimal),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_colocated_filter_and_tag(self):
        test_data = test_input_data.colocated_filter_and_tag()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Entity_Related"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "related_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_colocated_filter_with_differently_named_column_and_tag(self):
        test_data = test_input_data.colocated_filter_with_differently_named_column_and_tag()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Entity_Related"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "related_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_colocated_filter_and_tag_sharing_name_with_other_column(self):
        test_data = test_input_data.colocated_filter_and_tag_sharing_name_with_other_column()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Entity_Related"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "related_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_colocated_out_of_order_filter_and_tag(self):
        test_data = test_input_data.colocated_out_of_order_filter_and_tag()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Entity_Related"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "related_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_filters(self):
        test_data = test_input_data.multiple_filters()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$lower_bound", GraphQLString),
                )
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    "<",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$upper_bound", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_traverse_and_output(self):
        test_data = test_input_data.traverse_and_output()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "parent_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_traverse_after_mandatory_traverse(self):
        test_data = test_input_data.optional_traverse_after_mandatory_traverse()

        base_location = helpers.Location(("Animal",))
        revisited_base_location = base_location.revisit()
        twice_revisited_base_location = revisited_base_location.revisit()
        species_location = base_location.navigate_to_subpath("out_Animal_OfSpecies")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_OfSpecies"),
            blocks.MarkLocation(species_location),
            blocks.Backtrack(base_location),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(revisited_base_location, optional=True),
            blocks.MarkLocation(twice_revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        species_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            species_location: "Species",
            revisited_base_location: "Animal",
            child_location: "Animal",
            twice_revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_traverse_filter_and_output(self):
        test_data = test_input_data.traverse_filter_and_output()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.Variable("$wanted", GraphQLString),
                    ),
                    expressions.BinaryComposition(
                        "contains",
                        expressions.LocalField("alias", GraphQLList(GraphQLString)),
                        expressions.Variable("$wanted", GraphQLString),
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "parent_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_name_or_alias_filter_on_interface_type(self):
        test_data = test_input_data.name_or_alias_filter_on_interface_type()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Entity_Related"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.Variable("$wanted", GraphQLString),
                    ),
                    expressions.BinaryComposition(
                        "contains",
                        expressions.LocalField("alias", GraphQLList(GraphQLString)),
                        expressions.Variable("$wanted", GraphQLString),
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "related_entity": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_output_source_and_complex_output(self):
        test_data = test_input_data.output_source_and_complex_output()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(child_location),
            blocks.OutputSource(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "parent_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_optional_variable_equality(self):
        test_data = test_input_data.filter_on_optional_variable_equality()

        # The operand in the @filter directive originates from an optional block.
        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        child_fed_at_location = child_location.navigate_to_subpath("out_Animal_FedAt")
        child_revisited_location = child_location.revisit()
        animal_fed_at_location = base_location.navigate_to_subpath("out_Animal_FedAt")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(child_location),
            blocks.Traverse("out", "Animal_FedAt", optional=True),
            blocks.MarkLocation(child_fed_at_location),
            blocks.EndOptional(),
            blocks.Backtrack(child_location, optional=True),
            blocks.MarkLocation(child_revisited_location),
            blocks.Backtrack(base_location),
            blocks.Traverse("out", "Animal_FedAt"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(child_fed_at_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.ContextField(
                            child_fed_at_location.navigate_to_field("name"), GraphQLString
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(animal_fed_at_location),
            blocks.OutputSource(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            child_fed_at_location: "FeedingEvent",
            child_revisited_location: "Animal",
            animal_fed_at_location: "FeedingEvent",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_optional_variable_name_or_alias(self):
        test_data = test_input_data.filter_on_optional_variable_name_or_alias()

        # The operand in the @filter directive originates from an optional block.
        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        base_revisited_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(base_revisited_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "||",
                        expressions.BinaryComposition(
                            "=",
                            expressions.LocalField("name", GraphQLString),
                            expressions.ContextField(
                                parent_location.navigate_to_field("name"), GraphQLString
                            ),
                        ),
                        expressions.BinaryComposition(
                            "contains",
                            expressions.LocalField("alias", GraphQLList(GraphQLString)),
                            expressions.ContextField(
                                parent_location.navigate_to_field("name"), GraphQLString
                            ),
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.OutputSource(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            base_revisited_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_in_optional_block(self):
        test_data = test_input_data.filter_in_optional_block()

        base_location = helpers.Location(("Animal",))
        animal_parent_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$name", GraphQLString),
                )
            ),
            blocks.MarkLocation(animal_parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "parent_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(animal_parent_location),
                        expressions.OutputContextField(
                            animal_parent_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "uuid": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(animal_parent_location),
                        expressions.OutputContextField(
                            animal_parent_location.navigate_to_field("uuid"), GraphQLID
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            animal_parent_location: "Animal",
            revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_in_optional_and_count(self):
        test_data = test_input_data.filter_in_optional_and_count()

        base_location = helpers.Location(("Species",))
        animal_location = base_location.navigate_to_subpath("in_Animal_OfSpecies")
        base_revisit_1 = base_location.revisit()
        fold_location = base_revisit_1.navigate_to_fold("in_Species_Eats")

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_OfSpecies", optional=True),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$animal_name", GraphQLString),
                )
            ),
            blocks.MarkLocation(animal_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(base_revisit_1),
            blocks.Fold(fold_location),
            blocks.MarkLocation(fold_location),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.FoldedContextField(
                        fold_location.navigate_to_field(COUNT_META_FIELD_NAME), GraphQLInt
                    ),
                    expressions.Variable("$predators", GraphQLInt),
                )
            ),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            animal_location: "Animal",
            base_revisit_1: "Species",
            fold_location: "Species",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_between_filter_on_simple_scalar(self):
        test_data = test_input_data.between_filter_on_simple_scalar()

        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a simple scalar (a String).
        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "&&",
                    expressions.BinaryComposition(
                        ">=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.Variable("$lower", GraphQLString),
                    ),
                    expressions.BinaryComposition(
                        "<=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.Variable("$upper", GraphQLString),
                    ),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_between_filter_on_date(self):
        test_data = test_input_data.between_filter_on_date()

        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (Date).
        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "&&",
                    expressions.BinaryComposition(
                        ">=",
                        expressions.LocalField("birthday", GraphQLDate),
                        expressions.Variable("$lower", GraphQLDate),
                    ),
                    expressions.BinaryComposition(
                        "<=",
                        expressions.LocalField("birthday", GraphQLDate),
                        expressions.Variable("$upper", GraphQLDate),
                    ),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "birthday": expressions.OutputContextField(
                        base_location.navigate_to_field("birthday"), GraphQLDate
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_between_filter_on_datetime(self):
        test_data = test_input_data.between_filter_on_datetime()

        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (DateTime).
        base_location = helpers.Location(("Event",))

        expected_blocks = [
            blocks.QueryRoot({"Event"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "&&",
                    expressions.BinaryComposition(
                        ">=",
                        expressions.LocalField("event_date", GraphQLDateTime),
                        expressions.Variable("$lower", GraphQLDateTime),
                    ),
                    expressions.BinaryComposition(
                        "<=",
                        expressions.LocalField("event_date", GraphQLDateTime),
                        expressions.Variable("$upper", GraphQLDateTime),
                    ),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "event_date": expressions.OutputContextField(
                        base_location.navigate_to_field("event_date"), GraphQLDateTime
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Event",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_between_lowering_on_simple_scalar(self):
        test_data = test_input_data.between_lowering_on_simple_scalar()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "<=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$upper", GraphQLString),
                ),
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$lower", GraphQLString),
                ),
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_between_lowering_with_extra_filters(self):
        test_data = test_input_data.between_lowering_with_extra_filters()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "<=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$upper", GraphQLString),
                ),
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    "has_substring",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$substring", GraphQLString),
                ),
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.Variable("$fauna", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                ),
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$lower", GraphQLString),
                ),
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_no_between_lowering_on_simple_scalar(self):
        test_data = test_input_data.no_between_lowering_on_simple_scalar()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "<=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$upper", GraphQLString),
                ),
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$lower0", GraphQLString),
                ),
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$lower1", GraphQLString),
                ),
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_complex_optional_variables(self):
        test_data = test_input_data.complex_optional_variables()

        # The operands in the @filter directives originate from an optional block.
        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        child_fed_at_location = child_location.navigate_to_subpath("out_Animal_FedAt")

        child_fed_at_event_tag = child_fed_at_location.navigate_to_field("name")
        child_fed_at_tag = child_fed_at_location.navigate_to_field("event_date")

        revisited_child_location = child_location.revisit()

        other_parent_location = child_location.navigate_to_subpath("in_Animal_ParentOf")
        other_parent_fed_at_location = other_parent_location.navigate_to_subpath("out_Animal_FedAt")
        other_parent_fed_at_tag = other_parent_fed_at_location.navigate_to_field("event_date")
        other_parent_revisited_location = other_parent_location.revisit()

        grandparent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandparent_fed_at_location = grandparent_location.navigate_to_subpath("out_Animal_FedAt")
        grandparent_fed_at_output = grandparent_fed_at_location.navigate_to_field("event_date")

        expected_blocks = [
            # Apply the filter to the root vertex and mark it.
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(child_location),
            blocks.Traverse("out", "Animal_FedAt", optional=True),
            blocks.MarkLocation(child_fed_at_location),
            blocks.EndOptional(),
            blocks.Backtrack(child_location, optional=True),
            blocks.MarkLocation(revisited_child_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(other_parent_location),
            blocks.Traverse("out", "Animal_FedAt", optional=True),
            blocks.MarkLocation(other_parent_fed_at_location),
            blocks.EndOptional(),
            blocks.Backtrack(other_parent_location, optional=True),
            blocks.MarkLocation(other_parent_revisited_location),
            blocks.Backtrack(revisited_child_location),
            # Back to root vertex.
            blocks.Backtrack(base_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(grandparent_location),
            blocks.Traverse("out", "Animal_FedAt"),
            blocks.Filter(  # Filter "=" on the name field.
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(child_fed_at_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.ContextField(child_fed_at_event_tag, GraphQLString),
                    ),
                )
            ),
            blocks.Filter(  # Filter "between" on the event_date field.
                expressions.BinaryComposition(
                    "&&",
                    expressions.BinaryComposition(
                        "||",
                        expressions.BinaryComposition(
                            "=",
                            expressions.ContextFieldExistence(other_parent_fed_at_location),
                            expressions.FalseLiteral,
                        ),
                        expressions.BinaryComposition(
                            ">=",
                            expressions.LocalField("event_date", GraphQLDateTime),
                            expressions.ContextField(other_parent_fed_at_tag, GraphQLDateTime),
                        ),
                    ),
                    expressions.BinaryComposition(
                        "||",
                        expressions.BinaryComposition(
                            "=",
                            expressions.ContextFieldExistence(child_fed_at_location),
                            expressions.FalseLiteral,
                        ),
                        expressions.BinaryComposition(
                            "<=",
                            expressions.LocalField("event_date", GraphQLDateTime),
                            expressions.ContextField(child_fed_at_tag, GraphQLDateTime),
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(grandparent_fed_at_location),
            blocks.Backtrack(grandparent_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "child_fed_at": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_fed_at_location),
                        expressions.OutputContextField(child_fed_at_tag, GraphQLDateTime),
                        expressions.NullLiteral,
                    ),
                    "other_parent_fed_at": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(other_parent_fed_at_location),
                        expressions.OutputContextField(other_parent_fed_at_tag, GraphQLDateTime),
                        expressions.NullLiteral,
                    ),
                    "grandparent_fed_at": expressions.OutputContextField(
                        grandparent_fed_at_output, GraphQLDateTime
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            child_fed_at_location: "FeedingEvent",
            revisited_child_location: "Animal",
            other_parent_location: "Animal",
            other_parent_fed_at_location: "FeedingEvent",
            other_parent_revisited_location: "Animal",
            grandparent_location: "Animal",
            grandparent_fed_at_location: "FeedingEvent",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_complex_optional_variables_with_starting_filter(self):
        test_data = test_input_data.complex_optional_variables_with_starting_filter()

        # The operands in the @filter directives originate from an optional block.
        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        child_fed_at_location = child_location.navigate_to_subpath("out_Animal_FedAt")

        child_fed_at_event_tag = child_fed_at_location.navigate_to_field("name")
        child_fed_at_tag = child_fed_at_location.navigate_to_field("event_date")

        revisited_child_location = child_location.revisit()

        other_parent_location = child_location.navigate_to_subpath("in_Animal_ParentOf")
        other_parent_fed_at_location = other_parent_location.navigate_to_subpath("out_Animal_FedAt")
        other_parent_fed_at_tag = other_parent_fed_at_location.navigate_to_field("event_date")
        other_parent_revisited_location = other_parent_location.revisit()

        grandparent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandparent_fed_at_location = grandparent_location.navigate_to_subpath("out_Animal_FedAt")
        grandparent_fed_at_output = grandparent_fed_at_location.navigate_to_field("event_date")

        expected_blocks = [
            # Apply the filter to the root vertex and mark it.
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$animal_name", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(child_location),
            blocks.Traverse("out", "Animal_FedAt", optional=True),
            blocks.MarkLocation(child_fed_at_location),
            blocks.EndOptional(),
            blocks.Backtrack(child_location, optional=True),
            blocks.MarkLocation(revisited_child_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(other_parent_location),
            blocks.Traverse("out", "Animal_FedAt", optional=True),
            blocks.MarkLocation(other_parent_fed_at_location),
            blocks.EndOptional(),
            blocks.Backtrack(other_parent_location, optional=True),
            blocks.MarkLocation(other_parent_revisited_location),
            blocks.Backtrack(revisited_child_location),
            # Back to root vertex.
            blocks.Backtrack(base_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(grandparent_location),
            blocks.Traverse("out", "Animal_FedAt"),
            blocks.Filter(  # Filter "=" on the name field.
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(child_fed_at_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.ContextField(child_fed_at_event_tag, GraphQLString),
                    ),
                )
            ),
            blocks.Filter(  # Filter "between" on the event_date field.
                expressions.BinaryComposition(
                    "&&",
                    expressions.BinaryComposition(
                        "||",
                        expressions.BinaryComposition(
                            "=",
                            expressions.ContextFieldExistence(other_parent_fed_at_location),
                            expressions.FalseLiteral,
                        ),
                        expressions.BinaryComposition(
                            ">=",
                            expressions.LocalField("event_date", GraphQLDateTime),
                            expressions.ContextField(other_parent_fed_at_tag, GraphQLDateTime),
                        ),
                    ),
                    expressions.BinaryComposition(
                        "||",
                        expressions.BinaryComposition(
                            "=",
                            expressions.ContextFieldExistence(child_fed_at_location),
                            expressions.FalseLiteral,
                        ),
                        expressions.BinaryComposition(
                            "<=",
                            expressions.LocalField("event_date", GraphQLDateTime),
                            expressions.ContextField(child_fed_at_tag, GraphQLDateTime),
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(grandparent_fed_at_location),
            blocks.Backtrack(grandparent_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "child_fed_at": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_fed_at_location),
                        expressions.OutputContextField(child_fed_at_tag, GraphQLDateTime),
                        expressions.NullLiteral,
                    ),
                    "other_parent_fed_at": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(other_parent_fed_at_location),
                        expressions.OutputContextField(other_parent_fed_at_tag, GraphQLDateTime),
                        expressions.NullLiteral,
                    ),
                    "grandparent_fed_at": expressions.OutputContextField(
                        grandparent_fed_at_output, GraphQLDateTime
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            child_fed_at_location: "FeedingEvent",
            revisited_child_location: "Animal",
            other_parent_location: "Animal",
            other_parent_fed_at_location: "FeedingEvent",
            other_parent_revisited_location: "Animal",
            grandparent_location: "Animal",
            grandparent_fed_at_location: "FeedingEvent",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_simple_fragment(self):
        test_data = test_input_data.simple_fragment()

        base_location = helpers.Location(("Animal",))
        related_location = base_location.navigate_to_subpath("out_Entity_Related")
        related_species_location = related_location.navigate_to_subpath("out_Animal_OfSpecies")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Entity_Related"),
            blocks.CoerceType({"Animal"}),
            blocks.MarkLocation(related_location),
            blocks.Traverse("out", "Animal_OfSpecies"),
            blocks.MarkLocation(related_species_location),
            blocks.Backtrack(related_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_animal_name": expressions.OutputContextField(
                        related_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_animal_species": expressions.OutputContextField(
                        related_species_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            related_location: "Animal",
            related_species_location: "Species",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_simple_union(self):
        test_data = test_input_data.simple_union()

        base_location = helpers.Location(("Species",))
        food_location = base_location.navigate_to_subpath("out_Species_Eats")

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Species_Eats"),
            blocks.CoerceType({"Food"}),
            blocks.MarkLocation(food_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "food_name": expressions.OutputContextField(
                        food_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            food_location: "Food",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_then_apply_fragment(self):
        test_data = test_input_data.filter_then_apply_fragment()

        base_location = helpers.Location(("Species",))
        food_location = base_location.navigate_to_subpath("out_Species_Eats")

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.Variable("$species", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Species_Eats"),
            blocks.CoerceType({"Food"}),
            blocks.MarkLocation(food_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "food_name": expressions.OutputContextField(
                        food_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            food_location: "Food",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_then_apply_fragment_with_multiple_traverses(self):
        test_data = test_input_data.filter_then_apply_fragment_with_multiple_traverses()

        base_location = helpers.Location(("Species",))
        food_location = base_location.navigate_to_subpath("out_Species_Eats")
        entity_related_location = food_location.navigate_to_subpath("out_Entity_Related")
        food_related_location = food_location.navigate_to_subpath("in_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.Variable("$species", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Species_Eats"),
            blocks.CoerceType({"Food"}),
            blocks.MarkLocation(food_location),
            blocks.Traverse("out", "Entity_Related"),
            blocks.MarkLocation(entity_related_location),
            blocks.Backtrack(food_location),
            blocks.Traverse("in", "Entity_Related"),
            blocks.MarkLocation(food_related_location),
            blocks.Backtrack(food_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "food_name": expressions.OutputContextField(
                        food_location.navigate_to_field("name"), GraphQLString
                    ),
                    "entity_related_to_food": expressions.OutputContextField(
                        entity_related_location.navigate_to_field("name"), GraphQLString
                    ),
                    "food_related_to_entity": expressions.OutputContextField(
                        food_related_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            food_location: "Food",
            entity_related_location: "Entity",
            food_related_location: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_fragment_in_union(self):
        test_data = test_input_data.filter_on_fragment_in_union()

        base_location = helpers.Location(("Species",))
        food_location = base_location.navigate_to_subpath("out_Species_Eats")

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Species_Eats"),
            blocks.CoerceType({"Food"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.Variable("$wanted", GraphQLString),
                    ),
                    expressions.BinaryComposition(
                        "contains",
                        expressions.LocalField("alias", GraphQLList(GraphQLString)),
                        expressions.Variable("$wanted", GraphQLString),
                    ),
                )
            ),
            blocks.MarkLocation(food_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "food_name": expressions.OutputContextField(
                        food_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            food_location: "Food",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_on_union(self):
        test_data = test_input_data.optional_on_union()

        base_location = helpers.Location(("Species",))
        food_location = base_location.navigate_to_subpath("out_Species_Eats")
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Species_Eats", optional=True),
            blocks.CoerceType({"Food"}),
            blocks.MarkLocation(food_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "food_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(food_location),
                        expressions.OutputContextField(
                            food_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            food_location: "Food",
            revisited_base_location: "Species",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_typename_output(self):
        test_data = test_input_data.typename_output()

        base_location = helpers.Location(("Animal",))
        species_location = base_location.navigate_to_subpath("out_Animal_OfSpecies")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_OfSpecies"),
            blocks.MarkLocation(species_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "base_cls": expressions.OutputContextField(
                        base_location.navigate_to_field(TYPENAME_META_FIELD_NAME), GraphQLString
                    ),
                    "child_cls": expressions.OutputContextField(
                        species_location.navigate_to_field(TYPENAME_META_FIELD_NAME), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            species_location: "Species",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_typename_filter(self):
        test_data = test_input_data.typename_filter()

        base_location = helpers.Location(("Entity",))

        expected_blocks = [
            blocks.QueryRoot({"Entity"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField(TYPENAME_META_FIELD_NAME, GraphQLString),
                    expressions.Variable("$base_cls", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "entity_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_simple_recurse(self):
        test_data = test_input_data.simple_recurse()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Recurse("out", "Animal_ParentOf", 1),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "relation_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_inwards_recurse_after_traverse(self):
        test_data = test_input_data.inwards_recurse_after_traverse()

        base_location = helpers.Location(("Species",))
        child_location = base_location.navigate_to_subpath("in_Animal_OfSpecies")
        recurse_location = child_location.navigate_to_subpath("in_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_OfSpecies"),
            blocks.MarkLocation(child_location),
            blocks.Recurse("in", "Animal_ParentOf", 1),
            blocks.MarkLocation(recurse_location),
            blocks.Backtrack(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "animal_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                    "ancestor_name": expressions.OutputContextField(
                        recurse_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            child_location: "Animal",
            recurse_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_recurse_with_new_output_inside_recursion_and_filter_at_root(self):
        test_data = test_input_data.recurse_with_new_output_inside_recursion_and_filter_at_root()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u"=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$animal_name", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Recurse("out", "Animal_ParentOf", 1),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "relation_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                    "animal_color": expressions.OutputContextField(
                        child_location.navigate_to_field("color"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_then_recurse(self):
        test_data = test_input_data.filter_then_recurse()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    u"=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$animal_name", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Recurse("out", "Animal_ParentOf", 1),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "relation_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_traverse_then_recurse(self):
        test_data = test_input_data.traverse_then_recurse()

        base_location = helpers.Location(("Animal",))
        ancestor_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        event_location = base_location.navigate_to_subpath("out_Animal_ImportantEvent")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ImportantEvent"),
            blocks.CoerceType({"Event"}),
            blocks.MarkLocation(event_location),
            blocks.Backtrack(base_location),
            blocks.Recurse("out", "Animal_ParentOf", 2),
            blocks.MarkLocation(ancestor_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "important_event": expressions.OutputContextField(
                        event_location.navigate_to_field("name"), GraphQLString
                    ),
                    "ancestor_name": expressions.OutputContextField(
                        ancestor_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]

        expected_location_types = {
            base_location: "Animal",
            event_location: "Event",
            ancestor_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_then_traverse_and_recurse(self):
        test_data = test_input_data.filter_then_traverse_and_recurse()

        base_location = helpers.Location(("Animal",))
        ancestor_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        event_location = base_location.navigate_to_subpath("out_Animal_ImportantEvent")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.Variable("$animal_name_or_alias", GraphQLString),
                    ),
                    expressions.BinaryComposition(
                        "contains",
                        expressions.LocalField("alias", GraphQLList(GraphQLString)),
                        expressions.Variable("$animal_name_or_alias", GraphQLString),
                    ),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ImportantEvent"),
            blocks.CoerceType({"Event"}),
            blocks.MarkLocation(event_location),
            blocks.Backtrack(base_location),
            blocks.Recurse("out", "Animal_ParentOf", 2),
            blocks.MarkLocation(ancestor_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "important_event": expressions.OutputContextField(
                        event_location.navigate_to_field("name"), GraphQLString
                    ),
                    "ancestor_name": expressions.OutputContextField(
                        ancestor_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]

        expected_location_types = {
            base_location: "Animal",
            event_location: "Event",
            ancestor_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_two_consecutive_recurses(self):
        test_data = test_input_data.two_consecutive_recurses()

        base_location = helpers.Location(("Animal",))
        ancestor_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        descendent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        event_location = base_location.navigate_to_subpath("out_Animal_ImportantEvent")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.Variable("$animal_name_or_alias", GraphQLString),
                    ),
                    expressions.BinaryComposition(
                        "contains",
                        expressions.LocalField("alias", GraphQLList(GraphQLString)),
                        expressions.Variable("$animal_name_or_alias", GraphQLString),
                    ),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ImportantEvent"),
            blocks.CoerceType({"Event"}),
            blocks.MarkLocation(event_location),
            blocks.Backtrack(base_location),
            blocks.Recurse("out", "Animal_ParentOf", 2),
            blocks.MarkLocation(ancestor_location),
            blocks.Backtrack(base_location),
            blocks.Recurse("in", "Animal_ParentOf", 2),
            blocks.MarkLocation(descendent_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "important_event": expressions.OutputContextField(
                        event_location.navigate_to_field("name"), GraphQLString
                    ),
                    "ancestor_name": expressions.OutputContextField(
                        ancestor_location.navigate_to_field("name"), GraphQLString
                    ),
                    "descendent_name": expressions.OutputContextField(
                        descendent_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]

        expected_location_types = {
            base_location: "Animal",
            event_location: "Event",
            descendent_location: "Animal",
            ancestor_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_recurse_within_fragment(self):
        test_data = test_input_data.recurse_within_fragment()

        base_location = helpers.Location(("Food",))
        related_location = base_location.navigate_to_subpath("in_Entity_Related")
        child_location = related_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Food"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Entity_Related"),
            blocks.CoerceType({"Animal"}),
            blocks.MarkLocation(related_location),
            blocks.Recurse("out", "Animal_ParentOf", 3),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(related_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "food_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "animal_name": expressions.OutputContextField(
                        related_location.navigate_to_field("name"), GraphQLString
                    ),
                    "relation_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Food",
            related_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_within_recurse(self):
        test_data = test_input_data.filter_within_recurse()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Recurse("out", "Animal_ParentOf", 3),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("color", GraphQLString),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "relation_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_recurse_with_immediate_type_coercion(self):
        test_data = test_input_data.recurse_with_immediate_type_coercion()

        base_location = helpers.Location(("Animal",))
        related_location = base_location.navigate_to_subpath("in_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Recurse("in", "Entity_Related", 4),
            blocks.CoerceType({"Animal"}),
            blocks.MarkLocation(related_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        related_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            related_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_recurse_with_immediate_type_coercion_and_filter(self):
        test_data = test_input_data.recurse_with_immediate_type_coercion_and_filter()

        base_location = helpers.Location(("Animal",))
        related_location = base_location.navigate_to_subpath("in_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Recurse("in", "Entity_Related", 4),
            blocks.CoerceType({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("color", GraphQLString),
                    expressions.Variable("$color", GraphQLString),
                )
            ),
            blocks.MarkLocation(related_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        related_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            related_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_in_collection_op_filter_with_variable(self):
        test_data = test_input_data.in_collection_op_filter_with_variable()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.Variable("$wanted", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_in_collection_op_filter_with_tag(self):
        test_data = test_input_data.in_collection_op_filter_with_tag()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.ContextField(
                        base_location.navigate_to_field("alias"), GraphQLList(GraphQLString)
                    ),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_in_collection_op_filter_with_optional_tag(self):
        test_data = test_input_data.in_collection_op_filter_with_optional_tag()

        base_location = helpers.Location(("Animal",))
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "contains",
                        expressions.ContextField(
                            parent_location.navigate_to_field("alias"), GraphQLList(GraphQLString)
                        ),
                        expressions.LocalField("name", GraphQLString),
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            revisited_base_location: "Animal",
            parent_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_not_in_collection_op_filter_with_variable(self):
        test_data = test_input_data.not_in_collection_op_filter_with_variable()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "not_contains",
                    expressions.Variable("$wanted", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_not_in_collection_op_filter_with_tag(self):
        test_data = test_input_data.not_in_collection_op_filter_with_tag()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "not_contains",
                    expressions.ContextField(
                        base_location.navigate_to_field("alias"), GraphQLList(GraphQLString)
                    ),
                    expressions.LocalField("name", GraphQLString),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_not_in_collection_op_filter_with_optional_tag(self):
        test_data = test_input_data.not_in_collection_op_filter_with_optional_tag()

        base_location = helpers.Location(("Animal",))
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "not_contains",
                        expressions.ContextField(
                            parent_location.navigate_to_field("alias"), GraphQLList(GraphQLString)
                        ),
                        expressions.LocalField("name", GraphQLString),
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            revisited_base_location: "Animal",
            parent_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_intersects_op_filter_with_variable(self):
        test_data = test_input_data.intersects_op_filter_with_variable()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "intersects",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.Variable("$wanted", GraphQLList(GraphQLString)),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_intersects_op_filter_with_tag(self):
        test_data = test_input_data.intersects_op_filter_with_tag()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "intersects",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.ContextField(
                        base_location.navigate_to_field("alias"), GraphQLList(GraphQLString)
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_intersects_op_filter_with_optional_tag(self):
        test_data = test_input_data.intersects_op_filter_with_optional_tag()

        base_location = helpers.Location(("Animal",))
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "intersects",
                        expressions.LocalField("alias", GraphQLList(GraphQLString)),
                        expressions.ContextField(
                            parent_location.navigate_to_field("alias"), GraphQLList(GraphQLString)
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            revisited_base_location: "Animal",
            parent_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_contains_op_filter_with_variable(self):
        test_data = test_input_data.contains_op_filter_with_variable()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_contains_op_filter_with_tag(self):
        test_data = test_input_data.contains_op_filter_with_tag()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.ContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                )
            ),
            blocks.MarkLocation(parent_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_contains_op_filter_with_optional_tag(self):
        test_data = test_input_data.contains_op_filter_with_optional_tag()

        base_location = helpers.Location(("Animal",))
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "contains",
                        expressions.LocalField("alias", GraphQLList(GraphQLString)),
                        expressions.ContextField(
                            parent_location.navigate_to_field("name"), GraphQLString
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            revisited_base_location: "Animal",
            parent_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_not_contains_op_filter_with_variable(self):
        test_data = test_input_data.not_contains_op_filter_with_variable()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "not_contains",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_not_contains_op_filter_with_tag(self):
        test_data = test_input_data.not_contains_op_filter_with_tag()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "not_contains",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.ContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                )
            ),
            blocks.MarkLocation(parent_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_not_contains_op_filter_with_optional_tag(self):
        test_data = test_input_data.not_contains_op_filter_with_optional_tag()

        base_location = helpers.Location(("Animal",))
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "not_contains",
                        expressions.LocalField("alias", GraphQLList(GraphQLString)),
                        expressions.ContextField(
                            parent_location.navigate_to_field("name"), GraphQLString
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            revisited_base_location: "Animal",
            parent_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_starts_with_op_filter(self):
        test_data = test_input_data.starts_with_op_filter()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "starts_with",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_ends_with_op_filter(self):
        test_data = test_input_data.ends_with_op_filter()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "ends_with",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_substring_op_filter(self):
        test_data = test_input_data.has_substring_op_filter()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "has_substring",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_substring_op_filter_with_optional_tag(self):
        test_data = test_input_data.has_substring_op_filter_with_optional_tag()

        base_location = helpers.Location(("Animal",))
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(parent_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "has_substring",
                        expressions.LocalField("name", GraphQLString),
                        expressions.ContextField(
                            parent_location.navigate_to_field("name"), GraphQLString
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(child_location),
            blocks.Backtrack(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            revisited_base_location: "Animal",
            parent_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_edge_degree_op_filter(self):
        test_data = test_input_data.has_edge_degree_op_filter()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")

        list_of_animal_type = GraphQLList(self.schema.get_type("Animal"))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(  # the zero-edge check
                        "&&",
                        expressions.BinaryComposition(
                            "=",
                            expressions.Variable("$child_count", GraphQLInt),
                            expressions.ZeroLiteral,
                        ),
                        expressions.BinaryComposition(
                            "=",
                            expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            expressions.NullLiteral,
                        ),
                    ),
                    expressions.BinaryComposition(  # the non-zero-edge check
                        "&&",
                        expressions.BinaryComposition(
                            "!=",
                            expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            expressions.NullLiteral,
                        ),
                        expressions.BinaryComposition(
                            "=",
                            expressions.UnaryTransformation(
                                "size",
                                expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            ),
                            expressions.Variable("$child_count", GraphQLInt),
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(child_location),
            blocks.OutputSource(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_edge_degree_op_filter_with_optional(self):
        test_data = test_input_data.has_edge_degree_op_filter_with_optional()

        base_location = helpers.Location(("Species",))
        animal_location = base_location.navigate_to_subpath("in_Animal_OfSpecies")
        child_location = animal_location.navigate_to_subpath("in_Animal_ParentOf")
        revisited_animal_location = animal_location.revisit()

        list_of_animal_type = GraphQLList(self.schema.get_type("Animal"))

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_OfSpecies"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(  # the zero-edge check
                        "&&",
                        expressions.BinaryComposition(
                            "=",
                            expressions.Variable("$child_count", GraphQLInt),
                            expressions.ZeroLiteral,
                        ),
                        expressions.BinaryComposition(
                            "=",
                            expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            expressions.NullLiteral,
                        ),
                    ),
                    expressions.BinaryComposition(  # the non-zero-edge check
                        "&&",
                        expressions.BinaryComposition(
                            "!=",
                            expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            expressions.NullLiteral,
                        ),
                        expressions.BinaryComposition(
                            "=",
                            expressions.UnaryTransformation(
                                "size",
                                expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            ),
                            expressions.Variable("$child_count", GraphQLInt),
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(animal_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(animal_location, optional=True),
            blocks.MarkLocation(revisited_animal_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "parent_name": expressions.OutputContextField(
                        animal_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            animal_location: "Animal",
            child_location: "Animal",
            revisited_animal_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_edge_degree_op_filter_with_optional_and_between(self):
        test_data = test_input_data.has_edge_degree_op_filter_with_optional_and_between()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        related_location = parent_location.navigate_to_subpath("out_Entity_Related")
        revisited_base_location = base_location.revisit()

        list_of_animal_type = GraphQLList(self.schema.get_type("Animal"))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "&&",
                        expressions.BinaryComposition(
                            "=",
                            expressions.Variable("$number_of_edges", GraphQLInt),
                            expressions.ZeroLiteral,
                        ),
                        expressions.BinaryComposition(
                            "=",
                            expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            expressions.NullLiteral,
                        ),
                    ),
                    expressions.BinaryComposition(
                        "&&",
                        expressions.BinaryComposition(
                            "!=",
                            expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            expressions.NullLiteral,
                        ),
                        expressions.BinaryComposition(
                            "=",
                            expressions.UnaryTransformation(
                                "size",
                                expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            ),
                            expressions.Variable("$number_of_edges", GraphQLInt),
                        ),
                    ),
                )
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    "&&",
                    expressions.BinaryComposition(
                        ">=",
                        expressions.LocalField("uuid", GraphQLID),
                        expressions.Variable("$uuid_lower_bound", GraphQLID),
                    ),
                    expressions.BinaryComposition(
                        "<=",
                        expressions.LocalField("uuid", GraphQLID),
                        expressions.Variable("$uuid_upper_bound", GraphQLID),
                    ),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Traverse("out", "Entity_Related", within_optional_scope=True),
            blocks.CoerceType({"Event"}),
            blocks.MarkLocation(related_location),
            blocks.Backtrack(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_event": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(related_location),
                        expressions.OutputContextField(
                            related_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            related_location: "Event",
            revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_has_edge_degree_op_filter_with_fold(self):
        test_data = test_input_data.has_edge_degree_op_filter_with_fold()

        base_location = helpers.Location(("Species",))
        animal_location = base_location.navigate_to_subpath("in_Animal_OfSpecies")
        animal_fold = animal_location.navigate_to_fold("in_Animal_ParentOf")

        list_of_animal_type = GraphQLList(self.schema.get_type("Animal"))

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_OfSpecies"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(  # the zero-edge check
                        "&&",
                        expressions.BinaryComposition(
                            "=",
                            expressions.Variable("$child_count", GraphQLInt),
                            expressions.ZeroLiteral,
                        ),
                        expressions.BinaryComposition(
                            "=",
                            expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            expressions.NullLiteral,
                        ),
                    ),
                    expressions.BinaryComposition(  # the non-zero-edge check
                        "&&",
                        expressions.BinaryComposition(
                            "!=",
                            expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            expressions.NullLiteral,
                        ),
                        expressions.BinaryComposition(
                            "=",
                            expressions.UnaryTransformation(
                                "size",
                                expressions.LocalField("in_Animal_ParentOf", list_of_animal_type),
                            ),
                            expressions.Variable("$child_count", GraphQLInt),
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(animal_location),
            blocks.Fold(animal_fold),
            blocks.MarkLocation(animal_fold),
            blocks.Unfold(),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "species_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "parent_name": expressions.OutputContextField(
                        animal_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names": expressions.FoldedContextField(
                        animal_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            animal_location: "Animal",
            animal_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_is_null_op_filter(self):
        test_data = test_input_data.is_null_op_filter()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("net_worth", GraphQLDecimal),
                    expressions.NullLiteral,
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_is_null_op_filter_missing_value_argument(self):
        test_data = test_input_data.is_null_op_filter_missing_value_argument()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("net_worth", GraphQLDecimal),
                    expressions.NullLiteral,
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_is_not_null_op_filter(self):
        test_data = test_input_data.is_not_null_op_filter()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "!=",
                    expressions.LocalField("net_worth", GraphQLDecimal),
                    expressions.NullLiteral,
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_is_not_null_op_filter_missing_value_argument(self):
        test_data = test_input_data.is_not_null_op_filter_missing_value_argument()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "!=",
                    expressions.LocalField("net_worth", GraphQLDecimal),
                    expressions.NullLiteral,
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_same_edge_type_in_different_locations(self):
        test_data = test_input_data.fold_same_edge_type_in_different_locations()

        base_location = helpers.Location(("Animal",))
        base_fold = base_location.navigate_to_fold("out_Animal_ParentOf")
        traverse = base_location.navigate_to_subpath("in_Animal_ParentOf")
        second_fold = traverse.navigate_to_fold("out_Animal_ParentOf")
        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.MarkLocation(base_fold),
            blocks.Unfold(),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(traverse),
            blocks.Fold(second_fold),
            blocks.MarkLocation(second_fold),
            blocks.Unfold(),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names_list": expressions.FoldedContextField(
                        base_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "sibling_and_self_names_list": expressions.FoldedContextField(
                        second_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_fold: "Animal",
            traverse: "Animal",
            second_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_on_two_output_variables(self):
        test_data = test_input_data.fold_on_two_output_variables()

        base_location = helpers.Location(("Animal",))
        base_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.MarkLocation(base_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names_list": expressions.FoldedContextField(
                        base_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "child_color_list": expressions.FoldedContextField(
                        base_fold.navigate_to_field("color"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_on_output_variable(self):
        test_data = test_input_data.fold_on_output_variable()

        base_location = helpers.Location(("Animal",))
        base_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.MarkLocation(base_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names_list": expressions.FoldedContextField(
                        base_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_on_many_to_one_edge(self):
        test_data = test_input_data.fold_on_many_to_one_edge()

        base_location = helpers.Location(("Animal",))
        base_fold = base_location.navigate_to_fold("out_Animal_LivesIn")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.MarkLocation(base_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "homes_list": expressions.FoldedContextField(
                        base_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_fold: "Location",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_after_recurse(self):
        test_data = test_input_data.fold_after_recurse()

        base_location = helpers.Location(("Animal",))
        base_recurse = base_location.navigate_to_subpath("out_Animal_ParentOf")
        base_fold = base_recurse.navigate_to_fold("out_Animal_LivesIn")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Recurse("out", "Animal_ParentOf", 3, within_optional_scope=False),
            blocks.MarkLocation(base_recurse),
            blocks.Fold(base_fold),
            blocks.MarkLocation(base_fold),
            blocks.Unfold(),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "homes_list": expressions.FoldedContextField(
                        base_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_recurse: "Animal",
            base_fold: "Location",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_after_traverse(self):
        test_data = test_input_data.fold_after_traverse()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        parent_fold = parent_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(parent_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "sibling_and_self_names_list": expressions.FoldedContextField(
                        parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_and_traverse(self):
        test_data = test_input_data.fold_and_traverse()

        base_location = helpers.Location(("Animal",))
        parent_fold = base_location.navigate_to_fold("in_Animal_ParentOf")
        first_traversed_fold = parent_fold.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(first_traversed_fold),
            blocks.Backtrack(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "sibling_and_self_names_list": expressions.FoldedContextField(
                        first_traversed_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_fold: "Animal",
            first_traversed_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_and_deep_traverse(self):
        test_data = test_input_data.fold_and_deep_traverse()

        base_location = helpers.Location(("Animal",))
        parent_fold = base_location.navigate_to_fold("in_Animal_ParentOf")
        first_traversed_fold = parent_fold.navigate_to_subpath("out_Animal_ParentOf")
        second_traversed_fold = first_traversed_fold.navigate_to_subpath("out_Animal_OfSpecies")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(first_traversed_fold),
            blocks.Traverse("out", "Animal_OfSpecies"),
            blocks.MarkLocation(second_traversed_fold),
            blocks.Backtrack(first_traversed_fold),
            blocks.Backtrack(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "sibling_and_self_species_list": expressions.FoldedContextField(
                        second_traversed_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_fold: "Animal",
            first_traversed_fold: "Animal",
            second_traversed_fold: "Species",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_traverse_and_fold_and_traverse(self):
        test_data = test_input_data.traverse_and_fold_and_traverse()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        sibling_fold = parent_location.navigate_to_fold("out_Animal_ParentOf")
        sibling_species_fold = sibling_fold.navigate_to_subpath("out_Animal_OfSpecies")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(parent_location),
            blocks.Fold(sibling_fold),
            blocks.MarkLocation(sibling_fold),
            blocks.Traverse("out", "Animal_OfSpecies"),
            blocks.MarkLocation(sibling_species_fold),
            blocks.Backtrack(sibling_fold),
            blocks.Unfold(),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "sibling_and_self_species_list": expressions.FoldedContextField(
                        sibling_species_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            sibling_fold: "Animal",
            sibling_species_fold: "Species",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_and_filter_and_traverse_and_output(self):
        test_data = test_input_data.fold_and_filter_and_traverse_and_output()

        base_location = helpers.Location(("Animal",))
        parent_fold = base_location.navigate_to_fold("in_Animal_ParentOf")
        grand_parent_fold = parent_fold.navigate_to_subpath("in_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(parent_fold),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">",
                    expressions.LocalField("net_worth", GraphQLDecimal),
                    expressions.Variable("$parent_min_worth", GraphQLDecimal),
                )
            ),
            blocks.MarkLocation(parent_fold),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(grand_parent_fold),
            blocks.Backtrack(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "grand_parent_list": expressions.FoldedContextField(
                        grand_parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_fold: "Animal",
            grand_parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_outputs_in_same_fold(self):
        test_data = test_input_data.multiple_outputs_in_same_fold()

        base_location = helpers.Location(("Animal",))
        base_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.MarkLocation(base_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names_list": expressions.FoldedContextField(
                        base_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "child_uuids_list": expressions.FoldedContextField(
                        base_fold.navigate_to_field("uuid"), GraphQLList(GraphQLID)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_outputs_in_same_fold_and_traverse(self):
        test_data = test_input_data.multiple_outputs_in_same_fold_and_traverse()

        base_location = helpers.Location(("Animal",))
        base_fold = base_location.navigate_to_fold("in_Animal_ParentOf")
        first_traversed_fold = base_fold.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.MarkLocation(base_fold),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(first_traversed_fold),
            blocks.Backtrack(base_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "sibling_and_self_names_list": expressions.FoldedContextField(
                        first_traversed_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "sibling_and_self_uuids_list": expressions.FoldedContextField(
                        first_traversed_fold.navigate_to_field("uuid"), GraphQLList(GraphQLID)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_fold: "Animal",
            first_traversed_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_folds(self):
        test_data = test_input_data.multiple_folds()

        base_location = helpers.Location(("Animal",))
        base_out_fold = base_location.navigate_to_fold("out_Animal_ParentOf")
        base_in_fold = base_location.navigate_to_fold("in_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_out_fold),
            blocks.MarkLocation(base_out_fold),
            blocks.Unfold(),
            blocks.Fold(base_in_fold),
            blocks.MarkLocation(base_in_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names_list": expressions.FoldedContextField(
                        base_out_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "child_uuids_list": expressions.FoldedContextField(
                        base_out_fold.navigate_to_field("uuid"), GraphQLList(GraphQLID)
                    ),
                    "parent_names_list": expressions.FoldedContextField(
                        base_in_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "parent_uuids_list": expressions.FoldedContextField(
                        base_in_fold.navigate_to_field("uuid"), GraphQLList(GraphQLID)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_out_fold: "Animal",
            base_in_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_folds_and_traverse(self):
        test_data = test_input_data.multiple_folds_and_traverse()
        base_location = helpers.Location(("Animal",))
        base_out_fold = base_location.navigate_to_fold("out_Animal_ParentOf")
        base_out_traversed_fold = base_out_fold.navigate_to_subpath("in_Animal_ParentOf")
        base_in_fold = base_location.navigate_to_fold("in_Animal_ParentOf")
        base_in_traversed_fold = base_in_fold.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_out_fold),
            blocks.MarkLocation(base_out_fold),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(base_out_traversed_fold),
            blocks.Backtrack(base_out_fold),
            blocks.Unfold(),
            blocks.Fold(base_in_fold),
            blocks.MarkLocation(base_in_fold),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(base_in_traversed_fold),
            blocks.Backtrack(base_in_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "spouse_and_self_names_list": expressions.FoldedContextField(
                        base_out_traversed_fold.navigate_to_field("name"),
                        GraphQLList(GraphQLString),
                    ),
                    "spouse_and_self_uuids_list": expressions.FoldedContextField(
                        base_out_traversed_fold.navigate_to_field("uuid"), GraphQLList(GraphQLID)
                    ),
                    "sibling_and_self_names_list": expressions.FoldedContextField(
                        base_in_traversed_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "sibling_and_self_uuids_list": expressions.FoldedContextField(
                        base_in_traversed_fold.navigate_to_field("uuid"), GraphQLList(GraphQLID)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_out_fold: "Animal",
            base_out_traversed_fold: "Animal",
            base_in_fold: "Animal",
            base_in_traversed_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_after_traverse_different_types(self):
        test_data = test_input_data.fold_after_traverse_different_types()
        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("out_Animal_LivesIn")
        parent_fold = parent_location.navigate_to_fold("in_Animal_LivesIn")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_LivesIn"),
            blocks.MarkLocation(parent_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "neighbor_and_self_names_list": expressions.FoldedContextField(
                        parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Location",
            parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_after_traverse_no_output_on_root(self):
        test_data = test_input_data.fold_after_traverse_no_output_on_root()
        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("out_Animal_LivesIn")
        parent_fold = parent_location.navigate_to_fold("in_Animal_LivesIn")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_LivesIn"),
            blocks.MarkLocation(parent_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "location_name": expressions.OutputContextField(
                        parent_location.navigate_to_field("name"), GraphQLString
                    ),
                    "neighbor_and_self_names_list": expressions.FoldedContextField(
                        parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Location",
            parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_date_and_datetime_fields(self):
        test_data = test_input_data.fold_date_and_datetime_fields()

        base_location = helpers.Location(("Animal",))
        base_parent_fold = base_location.navigate_to_fold("out_Animal_ParentOf")
        base_fed_at_fold = base_location.navigate_to_fold("out_Animal_FedAt")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.MarkLocation(base_parent_fold),
            blocks.Unfold(),
            blocks.Fold(base_fed_at_fold),
            blocks.MarkLocation(base_fed_at_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_birthdays_list": expressions.FoldedContextField(
                        base_parent_fold.navigate_to_field("birthday"), GraphQLList(GraphQLDate)
                    ),
                    "fed_at_datetimes_list": expressions.FoldedContextField(
                        base_fed_at_fold.navigate_to_field("event_date"),
                        GraphQLList(GraphQLDateTime),
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_parent_fold: "Animal",
            base_fed_at_fold: "FeedingEvent",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_to_union_base_type_inside_fold(self):
        # Given type_equivalence_hints = { Event: Union__BirthEvent__Event__FeedingEvent },
        # the coercion should be optimized away as a no-op.
        test_data = test_input_data.coercion_to_union_base_type_inside_fold()

        base_location = helpers.Location(("Animal",))
        important_event_fold = base_location.navigate_to_fold("out_Animal_ImportantEvent")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(important_event_fold),
            blocks.MarkLocation(important_event_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "important_events": expressions.FoldedContextField(
                        important_event_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            important_event_fold: "Event",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_filters_and_multiple_outputs_within_fold_scope(self):
        test_data = test_input_data.coercion_filters_and_multiple_outputs_within_fold_scope()

        base_location = helpers.Location(("Animal",))
        related_entity_fold = base_location.navigate_to_fold("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(related_entity_fold),
            blocks.CoerceType({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "has_substring",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$substring", GraphQLString),
                )
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    "<=",
                    expressions.LocalField("birthday", GraphQLDate),
                    expressions.Variable("$latest", GraphQLDate),
                )
            ),
            blocks.MarkLocation(related_entity_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "related_animals": expressions.FoldedContextField(
                        related_entity_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_birthdays": expressions.FoldedContextField(
                        related_entity_fold.navigate_to_field("birthday"), GraphQLList(GraphQLDate)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            related_entity_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_filters_and_multiple_outputs_within_fold_traversal(self):
        test_data = test_input_data.coercion_filters_and_multiple_outputs_within_fold_traversal()

        base_location = helpers.Location(("Animal",))
        parent_fold = base_location.navigate_to_fold("in_Animal_ParentOf")
        inner_fold = parent_fold.navigate_to_subpath("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Traverse("out", "Entity_Related"),
            blocks.CoerceType({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "has_substring",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$substring", GraphQLString),
                )
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    "<=",
                    expressions.LocalField("birthday", GraphQLDate),
                    expressions.Variable("$latest", GraphQLDate),
                )
            ),
            blocks.MarkLocation(inner_fold),
            blocks.Backtrack(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_animals": expressions.FoldedContextField(
                        inner_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "related_birthdays": expressions.FoldedContextField(
                        inner_fold.navigate_to_field("birthday"), GraphQLList(GraphQLDate)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_fold: "Animal",
            inner_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_no_op_coercion_inside_fold(self):
        # The type where the coercion is applied is already Entity, so the coercion is a no-op.
        test_data = test_input_data.no_op_coercion_inside_fold()

        base_location = helpers.Location(("Animal",))
        related_entity_fold = base_location.navigate_to_fold("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(related_entity_fold),
            blocks.MarkLocation(related_entity_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_entities": expressions.FoldedContextField(
                        related_entity_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            related_entity_fold: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_no_op_coercion_with_eligible_subpath(self):
        # The type where the coercion is applied is already Entity, so the coercion is a no-op.
        test_data = test_input_data.no_op_coercion_with_eligible_subpath()

        base_location = helpers.Location(("Animal",))
        kid_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        grandkid_location = kid_location.navigate_to_subpath("out_Animal_ParentOf")
        related_location = kid_location.navigate_to_subpath("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(kid_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(grandkid_location),
            blocks.Backtrack(kid_location),
            blocks.Traverse("out", "Entity_Related"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.Variable("$entity_names", GraphQLList(GraphQLString)),
                    expressions.LocalField("name", GraphQLString),
                ),
            ),
            blocks.MarkLocation(related_location),
            blocks.Backtrack(kid_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        grandkid_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            kid_location: "Animal",
            grandkid_location: "Animal",
            related_location: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_within_fold_scope(self):
        test_data = test_input_data.filter_within_fold_scope()

        base_location = helpers.Location(("Animal",))
        base_parent_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.Filter(
                expressions.BinaryComposition(
                    "has_substring",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$desired", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_list": expressions.FoldedContextField(
                        base_parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_and_multiple_outputs_within_fold_scope(self):
        test_data = test_input_data.filter_and_multiple_outputs_within_fold_scope()

        base_location = helpers.Location(("Animal",))
        base_parent_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$desired", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_list": expressions.FoldedContextField(
                        base_parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "child_descriptions": expressions.FoldedContextField(
                        base_parent_fold.navigate_to_field("description"),
                        GraphQLList(GraphQLString),
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_fold_scope(self):
        test_data = test_input_data.filter_on_fold_scope()

        base_location = helpers.Location(("Animal",))
        base_parent_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.Variable("$desired", GraphQLString),
                    ),
                    expressions.BinaryComposition(
                        "contains",
                        expressions.LocalField("alias", GraphQLList(GraphQLString)),
                        expressions.Variable("$desired", GraphQLString),
                    ),
                )
            ),
            blocks.MarkLocation(base_parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_list": expressions.FoldedContextField(
                        base_parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_on_interface_within_fold_scope(self):
        test_data = test_input_data.coercion_on_interface_within_fold_scope()

        base_location = helpers.Location(("Animal",))
        related_entity_fold = base_location.navigate_to_fold("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(related_entity_fold),
            blocks.CoerceType({"Animal"}),
            blocks.MarkLocation(related_entity_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_animals": expressions.FoldedContextField(
                        related_entity_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            related_entity_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_on_interface_within_fold_traversal(self):
        test_data = test_input_data.coercion_on_interface_within_fold_traversal()

        base_location = helpers.Location(("Animal",))
        base_parent_fold = base_location.navigate_to_fold("in_Animal_ParentOf")
        first_traversed_fold = base_parent_fold.navigate_to_subpath("out_Entity_Related")
        second_traversed_fold = first_traversed_fold.navigate_to_subpath("out_Animal_OfSpecies")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_parent_fold),
            blocks.MarkLocation(base_parent_fold),
            blocks.Traverse("out", "Entity_Related"),
            blocks.CoerceType({"Animal"}),
            blocks.MarkLocation(first_traversed_fold),
            blocks.Traverse("out", "Animal_OfSpecies"),
            blocks.MarkLocation(second_traversed_fold),
            blocks.Backtrack(first_traversed_fold),
            blocks.Backtrack(base_parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_animal_species": expressions.FoldedContextField(
                        second_traversed_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            base_parent_fold: "Animal",
            first_traversed_fold: "Animal",
            second_traversed_fold: "Species",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_on_union_within_fold_scope(self):
        test_data = test_input_data.coercion_on_union_within_fold_scope()

        base_location = helpers.Location(("Animal",))
        important_event_fold = base_location.navigate_to_fold("out_Animal_ImportantEvent")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(important_event_fold),
            blocks.CoerceType({"BirthEvent"}),
            blocks.MarkLocation(important_event_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "birth_events": expressions.FoldedContextField(
                        important_event_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            important_event_fold: "BirthEvent",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_output_count_in_fold_scope(self):
        test_data = test_input_data.output_count_in_fold_scope()

        base_location = helpers.Location(("Animal",))
        parent_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names": expressions.FoldedContextField(
                        parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                    "number_of_children": expressions.FoldCountContextField(
                        parent_fold.navigate_to_field(COUNT_META_FIELD_NAME)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_count_with_runtime_parameter_in_fold_scope(self):
        test_data = test_input_data.filter_count_with_runtime_parameter_in_fold_scope()

        base_location = helpers.Location(("Animal",))
        parent_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.FoldedContextField(
                        parent_fold.navigate_to_field(COUNT_META_FIELD_NAME), GraphQLInt
                    ),
                    expressions.Variable("$min_children", GraphQLInt),
                )
            ),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names": expressions.FoldedContextField(
                        parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_field_with_tagged_optional_parameter_in_fold_scope(self):
        test_data = test_input_data.filter_field_with_tagged_optional_parameter_in_fold_scope()

        base_location = helpers.Location(("Animal",))
        optional_parent_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        revisited_base_location = base_location.revisit()
        parent_fold = revisited_base_location.navigate_to_fold("in_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True, within_optional_scope=False),
            blocks.MarkLocation(optional_parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Fold(parent_fold),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(optional_parent_location),
                        expressions.Literal(
                            False,
                        ),
                    ),
                    expressions.BinaryComposition(
                        ">=",
                        expressions.LocalField("net_worth", GraphQLDecimal),
                        expressions.ContextField(
                            optional_parent_location.navigate_to_field("net_worth"), GraphQLDecimal
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "children_with_higher_net_worth": expressions.FoldedContextField(
                        parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]

        expected_location_types = {
            base_location: "Animal",
            optional_parent_location: "Animal",
            revisited_base_location: "Animal",
            parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_count_with_tagged_optional_parameter_in_fold_scope(self):
        test_data = test_input_data.filter_count_with_tagged_optional_parameter_in_fold_scope()

        base_location = helpers.Location(("Animal",))
        species_location = base_location.navigate_to_subpath("out_Animal_OfSpecies")
        revisited_base_location = base_location.revisit()
        parent_fold = revisited_base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_OfSpecies", optional=True, within_optional_scope=False),
            blocks.MarkLocation(species_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(species_location),
                        expressions.Literal(
                            False,
                        ),
                    ),
                    expressions.BinaryComposition(
                        ">=",
                        expressions.FoldedContextField(
                            parent_fold.navigate_to_field(COUNT_META_FIELD_NAME), GraphQLInt
                        ),
                        expressions.GlobalContextField(
                            species_location.navigate_to_field("limbs"), GraphQLInt
                        ),
                    ),
                )
            ),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names": expressions.FoldedContextField(
                        parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]

        expected_location_types = {
            base_location: "Animal",
            species_location: "Species",
            revisited_base_location: "Animal",
            parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_count_with_tagged_parameter_in_fold_scope(self):
        test_data = test_input_data.filter_count_with_tagged_parameter_in_fold_scope()

        base_location = helpers.Location(("Animal",))
        species_location = base_location.navigate_to_subpath("out_Animal_OfSpecies")
        parent_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_OfSpecies"),
            blocks.MarkLocation(species_location),
            blocks.Backtrack(base_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.FoldedContextField(
                        parent_fold.navigate_to_field(COUNT_META_FIELD_NAME), GraphQLInt
                    ),
                    expressions.GlobalContextField(
                        species_location.navigate_to_field("limbs"), GraphQLInt
                    ),
                )
            ),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_names": expressions.FoldedContextField(
                        parent_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            species_location: "Species",
            parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_count_and_other_filters_in_fold_scope(self):
        test_data = test_input_data.filter_count_and_other_filters_in_fold_scope()

        base_location = helpers.Location(("Animal",))
        parent_fold = base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(parent_fold),
            blocks.Filter(
                expressions.BinaryComposition(
                    "contains",
                    expressions.LocalField("alias", GraphQLList(GraphQLString)),
                    expressions.Variable("$expected_alias", GraphQLString),
                )
            ),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.FoldedContextField(
                        parent_fold.navigate_to_field(COUNT_META_FIELD_NAME), GraphQLInt
                    ),
                    expressions.Variable("$min_children", GraphQLInt),
                )
            ),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "number_of_children": expressions.FoldCountContextField(
                        parent_fold.navigate_to_field(COUNT_META_FIELD_NAME)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_filters_on_count(self):
        test_data = test_input_data.multiple_filters_on_count()

        base_location = helpers.Location(("Animal",))
        parent_fold = base_location.navigate_to_fold("out_Animal_ParentOf")
        related_fold = base_location.navigate_to_fold("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(parent_fold),
            blocks.MarkLocation(parent_fold),
            blocks.Unfold(),
            blocks.Fold(related_fold),
            blocks.MarkLocation(related_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.FoldedContextField(
                        parent_fold.navigate_to_field(COUNT_META_FIELD_NAME), GraphQLInt
                    ),
                    expressions.Variable("$min_children", GraphQLInt),
                )
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.FoldedContextField(
                        related_fold.navigate_to_field(COUNT_META_FIELD_NAME), GraphQLInt
                    ),
                    expressions.Variable("$min_related", GraphQLInt),
                )
            ),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_fold: "Animal",
            related_fold: "Entity",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_count_with_nested_filter(self):
        test_data = test_input_data.filter_on_count_with_nested_filter()

        base_location = helpers.Location(("Species",))
        animal_fold = base_location.navigate_to_fold("in_Animal_OfSpecies")
        location_fold = animal_fold.navigate_to_subpath("out_Animal_LivesIn")

        expected_blocks = [
            blocks.QueryRoot({"Species"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(animal_fold),
            blocks.MarkLocation(animal_fold),
            blocks.Traverse("out", "Animal_LivesIn"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$location", GraphQLString),
                )
            ),
            blocks.MarkLocation(location_fold),
            blocks.Backtrack(animal_fold),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.FoldedContextField(
                        location_fold.navigate_to_field(COUNT_META_FIELD_NAME), GraphQLInt
                    ),
                    expressions.Variable("$num_animals", GraphQLInt),
                )
            ),
            blocks.ConstructResult(
                {
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Species",
            animal_fold: "Animal",
            location_fold: "Location",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_and_traverse(self):
        test_data = test_input_data.optional_and_traverse()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandchild_location = child_location.navigate_to_subpath("in_Animal_ParentOf")
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.Traverse("in", "Animal_ParentOf", within_optional_scope=True),
            blocks.MarkLocation(grandchild_location),
            blocks.Backtrack(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "grandchild_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(grandchild_location),
                        expressions.OutputContextField(
                            grandchild_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            grandchild_location: "Animal",
            revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_and_traverse_after_filter(self):
        test_data = test_input_data.optional_and_traverse_after_filter()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandchild_location = child_location.navigate_to_subpath("in_Animal_ParentOf")
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "has_substring",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.Traverse("in", "Animal_ParentOf", within_optional_scope=True),
            blocks.MarkLocation(grandchild_location),
            blocks.Backtrack(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "grandchild_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(grandchild_location),
                        expressions.OutputContextField(
                            grandchild_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            grandchild_location: "Animal",
            revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_and_deep_traverse(self):
        test_data = test_input_data.optional_and_deep_traverse()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        spouse_location = child_location.navigate_to_subpath("out_Animal_ParentOf")
        spouse_species = spouse_location.navigate_to_subpath("out_Animal_OfSpecies")
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.Traverse("out", "Animal_ParentOf", within_optional_scope=True),
            blocks.MarkLocation(spouse_location),
            blocks.Traverse("out", "Animal_OfSpecies", within_optional_scope=True),
            blocks.MarkLocation(spouse_species),
            blocks.Backtrack(spouse_location),
            blocks.Backtrack(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "spouse_and_self_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(spouse_location),
                        expressions.OutputContextField(
                            spouse_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "spouse_species": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(spouse_species),
                        expressions.OutputContextField(
                            spouse_species.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            spouse_location: "Animal",
            spouse_species: "Species",
            revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_traverse_and_optional_and_traverse(self):
        test_data = test_input_data.traverse_and_optional_and_traverse()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        spouse_location = child_location.navigate_to_subpath("out_Animal_ParentOf")
        spouse_species = spouse_location.navigate_to_subpath("out_Animal_OfSpecies")
        revisited_child_location = child_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(child_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(spouse_location),
            blocks.Traverse("out", "Animal_OfSpecies", within_optional_scope=True),
            blocks.MarkLocation(spouse_species),
            blocks.Backtrack(spouse_location),
            blocks.EndOptional(),
            blocks.Backtrack(child_location, optional=True),
            blocks.MarkLocation(revisited_child_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "spouse_and_self_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(spouse_location),
                        expressions.OutputContextField(
                            spouse_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "spouse_and_self_species": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(spouse_species),
                        expressions.OutputContextField(
                            spouse_species.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_name": expressions.OutputContextField(
                        child_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            spouse_location: "Animal",
            spouse_species: "Species",
            revisited_child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_optional_traversals_with_starting_filter(self):
        test_data = test_input_data.multiple_optional_traversals_with_starting_filter()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        spouse_location = child_location.navigate_to_subpath("out_Animal_ParentOf")
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        parent_species_location = parent_location.navigate_to_subpath("out_Animal_OfSpecies")
        re_revisited_base_location = revisited_base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "has_substring",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.Traverse("out", "Animal_ParentOf", within_optional_scope=True),
            blocks.MarkLocation(spouse_location),
            blocks.Backtrack(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Traverse("out", "Animal_OfSpecies", within_optional_scope=True),
            blocks.MarkLocation(parent_species_location),
            blocks.Backtrack(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(revisited_base_location, optional=True),
            blocks.MarkLocation(re_revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "spouse_and_self_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(spouse_location),
                        expressions.OutputContextField(
                            spouse_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "parent_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(parent_location),
                        expressions.OutputContextField(
                            parent_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "parent_species": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(parent_species_location),
                        expressions.OutputContextField(
                            parent_species_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            spouse_location: "Animal",
            revisited_base_location: "Animal",
            parent_location: "Animal",
            parent_species_location: "Species",
            re_revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_traversal_and_optional_without_traversal(self):
        test_data = test_input_data.optional_traversal_and_optional_without_traversal()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        parent_species_location = parent_location.navigate_to_subpath("out_Animal_OfSpecies")
        re_revisited_base_location = revisited_base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "has_substring",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$wanted", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Traverse("out", "Animal_OfSpecies", within_optional_scope=True),
            blocks.MarkLocation(parent_species_location),
            blocks.Backtrack(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(revisited_base_location, optional=True),
            blocks.MarkLocation(re_revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "parent_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(parent_location),
                        expressions.OutputContextField(
                            parent_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "parent_species": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(parent_species_location),
                        expressions.OutputContextField(
                            parent_species_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            revisited_base_location: "Animal",
            parent_location: "Animal",
            parent_species_location: "Species",
            re_revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_on_interface_within_optional_traversal(self):
        test_data = test_input_data.coercion_on_interface_within_optional_traversal()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        entity_location = parent_location.navigate_to_subpath("out_Entity_Related")
        species_location = entity_location.navigate_to_subpath("out_Animal_OfSpecies")
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Traverse("out", "Entity_Related", within_optional_scope=True),
            blocks.CoerceType({"Animal"}),
            blocks.MarkLocation(entity_location),
            blocks.Traverse("out", "Animal_OfSpecies", within_optional_scope=True),
            blocks.MarkLocation(species_location),
            blocks.Backtrack(entity_location),
            blocks.Backtrack(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_animal_species": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(species_location),
                        expressions.OutputContextField(
                            species_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            entity_location: "Animal",
            species_location: "Species",
            revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_optional_traversal_equality(self):
        test_data = test_input_data.filter_on_optional_traversal_equality()

        # The operand in the @filter directive originates from an optional block.
        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        grandparent_location = parent_location.navigate_to_subpath("out_Animal_ParentOf")
        fed_at_location = grandparent_location.navigate_to_subpath("out_Animal_FedAt")
        parent_revisited_location = parent_location.revisit()
        animal_fed_at_location = base_location.navigate_to_subpath("out_Animal_FedAt")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(parent_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(grandparent_location),
            blocks.Traverse("out", "Animal_FedAt", within_optional_scope=True),
            blocks.MarkLocation(fed_at_location),
            blocks.Backtrack(grandparent_location),
            blocks.EndOptional(),
            blocks.Backtrack(parent_location, optional=True),
            blocks.MarkLocation(parent_revisited_location),
            blocks.Backtrack(base_location),
            blocks.Traverse("out", "Animal_FedAt"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(fed_at_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.ContextField(
                            fed_at_location.navigate_to_field("name"), GraphQLString
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(animal_fed_at_location),
            blocks.OutputSource(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            grandparent_location: "Animal",
            fed_at_location: "FeedingEvent",
            parent_revisited_location: "Animal",
            animal_fed_at_location: "FeedingEvent",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_filter_on_optional_traversal_name_or_alias(self):
        test_data = test_input_data.filter_on_optional_traversal_name_or_alias()

        # The operand in the @filter directive originates from an optional block.
        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandchild_location = child_location.navigate_to_subpath("in_Animal_ParentOf")
        revisited_base_location = base_location.revisit()
        parent_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.Traverse("in", "Animal_ParentOf", within_optional_scope=True),
            blocks.MarkLocation(grandchild_location),
            blocks.Backtrack(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.Filter(
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(grandchild_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "||",
                        expressions.BinaryComposition(
                            "=",
                            expressions.LocalField("name", GraphQLString),
                            expressions.ContextField(
                                grandchild_location.navigate_to_field("name"), GraphQLString
                            ),
                        ),
                        expressions.BinaryComposition(
                            "contains",
                            expressions.LocalField("alias", GraphQLList(GraphQLString)),
                            expressions.ContextField(
                                grandchild_location.navigate_to_field("name"), GraphQLString
                            ),
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(parent_location),
            blocks.OutputSource(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "parent_name": expressions.OutputContextField(
                        parent_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            grandchild_location: "Animal",
            revisited_base_location: "Animal",
            child_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_complex_optional_traversal_variables(self):
        test_data = test_input_data.complex_optional_traversal_variables()

        # The operands in the @filter directives originate from an optional block.
        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        parent_fed_at_location = parent_location.navigate_to_subpath("out_Animal_FedAt")

        parent_fed_at_event_tag = parent_fed_at_location.navigate_to_field("name")
        parent_fed_at_tag = parent_fed_at_location.navigate_to_field("event_date")

        revisited_child_location = parent_location.revisit()
        re_revisited_child_location = revisited_child_location.revisit()

        other_child_location = parent_location.navigate_to_subpath("in_Animal_ParentOf")
        other_child_fed_at_location = other_child_location.navigate_to_subpath("out_Animal_FedAt")
        other_child_fed_at_tag = other_child_fed_at_location.navigate_to_field("event_date")

        grandchild_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandchild_fed_at_location = grandchild_location.navigate_to_subpath("out_Animal_FedAt")
        grandchild_fed_at_output = grandchild_fed_at_location.navigate_to_field("event_date")

        expected_blocks = [
            # Apply the filter to the root vertex and mark it.
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "=",
                    expressions.LocalField("name", GraphQLString),
                    expressions.Variable("$animal_name", GraphQLString),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(parent_location),
            blocks.Traverse("out", "Animal_FedAt", optional=True),
            blocks.MarkLocation(parent_fed_at_location),
            blocks.EndOptional(),
            blocks.Backtrack(parent_location, optional=True),
            blocks.MarkLocation(revisited_child_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(other_child_location),
            blocks.Traverse("out", "Animal_FedAt", within_optional_scope=True),
            blocks.MarkLocation(other_child_fed_at_location),
            blocks.Backtrack(other_child_location),
            blocks.EndOptional(),
            blocks.Backtrack(revisited_child_location, optional=True),
            blocks.MarkLocation(re_revisited_child_location),
            # Back to root vertex.
            blocks.Backtrack(base_location),
            blocks.Traverse("in", "Animal_ParentOf"),
            blocks.MarkLocation(grandchild_location),
            blocks.Traverse("out", "Animal_FedAt"),
            blocks.Filter(  # Filter "=" on the name field.
                expressions.BinaryComposition(
                    "||",
                    expressions.BinaryComposition(
                        "=",
                        expressions.ContextFieldExistence(parent_fed_at_location),
                        expressions.FalseLiteral,
                    ),
                    expressions.BinaryComposition(
                        "=",
                        expressions.LocalField("name", GraphQLString),
                        expressions.ContextField(parent_fed_at_event_tag, GraphQLString),
                    ),
                )
            ),
            blocks.Filter(  # Filter "between" on the event_date field.
                expressions.BinaryComposition(
                    "&&",
                    expressions.BinaryComposition(
                        "||",
                        expressions.BinaryComposition(
                            "=",
                            expressions.ContextFieldExistence(other_child_fed_at_location),
                            expressions.FalseLiteral,
                        ),
                        expressions.BinaryComposition(
                            ">=",
                            expressions.LocalField("event_date", GraphQLDateTime),
                            expressions.ContextField(other_child_fed_at_tag, GraphQLDateTime),
                        ),
                    ),
                    expressions.BinaryComposition(
                        "||",
                        expressions.BinaryComposition(
                            "=",
                            expressions.ContextFieldExistence(parent_fed_at_location),
                            expressions.FalseLiteral,
                        ),
                        expressions.BinaryComposition(
                            "<=",
                            expressions.LocalField("event_date", GraphQLDateTime),
                            expressions.ContextField(parent_fed_at_tag, GraphQLDateTime),
                        ),
                    ),
                )
            ),
            blocks.MarkLocation(grandchild_fed_at_location),
            blocks.Backtrack(grandchild_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "parent_fed_at": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(parent_fed_at_location),
                        expressions.OutputContextField(parent_fed_at_tag, GraphQLDateTime),
                        expressions.NullLiteral,
                    ),
                    "other_child_fed_at": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(other_child_fed_at_location),
                        expressions.OutputContextField(other_child_fed_at_tag, GraphQLDateTime),
                        expressions.NullLiteral,
                    ),
                    "grandchild_fed_at": expressions.OutputContextField(
                        grandchild_fed_at_output, GraphQLDateTime
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            parent_fed_at_location: "FeedingEvent",
            revisited_child_location: "Animal",
            other_child_location: "Animal",
            other_child_fed_at_location: "FeedingEvent",
            re_revisited_child_location: "Animal",
            grandchild_location: "Animal",
            grandchild_fed_at_location: "FeedingEvent",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_simple_optional_recurse(self):
        test_data = test_input_data.simple_optional_recurse()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        self_and_ancestor_location = child_location.navigate_to_subpath("out_Animal_ParentOf")
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.Recurse("out", "Animal_ParentOf", 3, within_optional_scope=True),
            blocks.MarkLocation(self_and_ancestor_location),
            blocks.Backtrack(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "self_and_ancestor_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(self_and_ancestor_location),
                        expressions.OutputContextField(
                            self_and_ancestor_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            self_and_ancestor_location: "Animal",
            revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_multiple_traverse_within_optional(self):
        test_data = test_input_data.multiple_traverse_within_optional()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandchild_location = child_location.navigate_to_subpath("in_Animal_ParentOf")
        revisited_base_location = base_location.revisit()
        child_fed_at_location = child_location.navigate_to_subpath("out_Animal_FedAt")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.Traverse("in", "Animal_ParentOf", within_optional_scope=True),
            blocks.MarkLocation(grandchild_location),
            blocks.Backtrack(child_location),
            blocks.Traverse("out", "Animal_FedAt", within_optional_scope=True),
            blocks.MarkLocation(child_fed_at_location),
            blocks.Backtrack(child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "grandchild_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(grandchild_location),
                        expressions.OutputContextField(
                            grandchild_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_feeding_time": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_fed_at_location),
                        expressions.OutputContextField(
                            child_fed_at_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            grandchild_location: "Animal",
            revisited_base_location: "Animal",
            child_fed_at_location: "FeedingEvent",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_and_fold(self):
        test_data = test_input_data.optional_and_fold()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        revisited_base_location = base_location.revisit()
        fold_scope = revisited_base_location.navigate_to_fold("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Fold(fold_scope),
            blocks.MarkLocation(fold_scope),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "parent_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(parent_location),
                        expressions.OutputContextField(
                            parent_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_names_list": expressions.FoldedContextField(
                        fold_scope.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            revisited_base_location: "Animal",
            fold_scope: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_and_optional(self):
        test_data = test_input_data.fold_and_optional()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        base_fold = base_location.navigate_to_fold("out_Animal_ParentOf")
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.MarkLocation(base_fold),
            blocks.Unfold(),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "parent_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(parent_location),
                        expressions.OutputContextField(
                            parent_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_names_list": expressions.FoldedContextField(
                        base_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            revisited_base_location: "Animal",
            base_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_optional_traversal_and_fold_traversal(self):
        test_data = test_input_data.optional_traversal_and_fold_traversal()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandparent_location = parent_location.navigate_to_subpath("in_Animal_ParentOf")
        revisited_base_location = base_location.revisit()
        fold_scope = revisited_base_location.navigate_to_fold("out_Animal_ParentOf")
        first_traversed_fold = fold_scope.navigate_to_subpath("out_Animal_ParentOf")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Traverse("in", "Animal_ParentOf", within_optional_scope=True),
            blocks.MarkLocation(grandparent_location),
            blocks.Backtrack(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Fold(fold_scope),
            blocks.MarkLocation(fold_scope),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(first_traversed_fold),
            blocks.Backtrack(fold_scope),
            blocks.Unfold(),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "grandparent_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(grandparent_location),
                        expressions.OutputContextField(
                            grandparent_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "grandchild_names_list": expressions.FoldedContextField(
                        first_traversed_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            grandparent_location: "Animal",
            revisited_base_location: "Animal",
            fold_scope: "Animal",
            first_traversed_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_fold_traversal_and_optional_traversal(self):
        test_data = test_input_data.fold_traversal_and_optional_traversal()

        base_location = helpers.Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandparent_location = parent_location.navigate_to_subpath("in_Animal_ParentOf")
        base_fold = base_location.navigate_to_fold("out_Animal_ParentOf")
        first_traversed_fold = base_fold.navigate_to_subpath("out_Animal_ParentOf")
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Fold(base_fold),
            blocks.MarkLocation(base_fold),
            blocks.Traverse("out", "Animal_ParentOf"),
            blocks.MarkLocation(first_traversed_fold),
            blocks.Backtrack(base_fold),
            blocks.Unfold(),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Traverse("in", "Animal_ParentOf", within_optional_scope=True),
            blocks.MarkLocation(grandparent_location),
            blocks.Backtrack(parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "grandparent_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(grandparent_location),
                        expressions.OutputContextField(
                            grandparent_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "grandchild_names_list": expressions.FoldedContextField(
                        first_traversed_fold.navigate_to_field("name"), GraphQLList(GraphQLString)
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            parent_location: "Animal",
            grandparent_location: "Animal",
            revisited_base_location: "Animal",
            base_fold: "Animal",
            first_traversed_fold: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_between_lowering(self):
        test_data = test_input_data.between_lowering()

        base_location = helpers.Location(("Animal",))

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "&&",
                    expressions.BinaryComposition(
                        ">=",
                        expressions.LocalField("uuid", GraphQLID),
                        expressions.Variable("$uuid_lower", GraphQLID),
                    ),
                    expressions.BinaryComposition(
                        "<=",
                        expressions.LocalField("uuid", GraphQLID),
                        expressions.Variable("$uuid_upper", GraphQLID),
                    ),
                )
            ),
            blocks.Filter(
                expressions.BinaryComposition(
                    ">=",
                    expressions.LocalField("birthday", GraphQLDate),
                    expressions.Variable("$earliest_modified_date", GraphQLDate),
                )
            ),
            blocks.MarkLocation(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_coercion_and_filter_with_tag(self):
        test_data = test_input_data.coercion_and_filter_with_tag()

        base_location = helpers.Location(("Animal",))
        related_location = base_location.navigate_to_subpath("out_Entity_Related")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Entity_Related"),
            blocks.CoerceType({"Animal"}),
            blocks.Filter(
                expressions.BinaryComposition(
                    "has_substring",
                    expressions.LocalField("name", GraphQLString),
                    expressions.ContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                ),
            ),
            blocks.MarkLocation(related_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "origin": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "related_name": expressions.OutputContextField(
                        related_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            related_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_nested_optional_and_traverse(self):
        test_data = test_input_data.nested_optional_and_traverse()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        spouse_location = child_location.navigate_to_subpath("out_Animal_ParentOf")
        spouse_species_location = spouse_location.navigate_to_subpath("out_Animal_OfSpecies")
        revisited_child_location = child_location.revisit()
        revisited_base_location = base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True, within_optional_scope=True),
            blocks.MarkLocation(spouse_location),
            blocks.Traverse("out", "Animal_OfSpecies", within_optional_scope=True),
            blocks.MarkLocation(spouse_species_location),
            blocks.Backtrack(spouse_location),
            blocks.EndOptional(),
            blocks.Backtrack(child_location, optional=True),
            blocks.MarkLocation(revisited_child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "spouse_and_self_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(spouse_location),
                        expressions.OutputContextField(
                            spouse_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "spouse_species": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(spouse_species_location),
                        expressions.OutputContextField(
                            spouse_species_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            spouse_location: "Animal",
            spouse_species_location: "Species",
            revisited_child_location: "Animal",
            revisited_base_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_complex_nested_optionals(self):
        test_data = test_input_data.complex_nested_optionals()

        base_location = helpers.Location(("Animal",))
        child_location = base_location.navigate_to_subpath("in_Animal_ParentOf")
        grandchild_location = child_location.navigate_to_subpath("in_Animal_ParentOf")
        grandchild_species_location = grandchild_location.navigate_to_subpath(
            "out_Animal_OfSpecies"
        )
        child_related_location = child_location.navigate_to_subpath("in_Entity_Related")
        child_related_species_location = child_related_location.navigate_to_subpath(
            "out_Animal_OfSpecies"
        )
        parent_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        grandparent_location = parent_location.navigate_to_subpath("out_Animal_ParentOf")
        grandparent_species_location = grandparent_location.navigate_to_subpath(
            "out_Animal_OfSpecies"
        )
        revisited_child_location = child_location.revisit()
        re_revisited_child_location = revisited_child_location.revisit()
        revisited_base_location = base_location.revisit()
        revisited_parent_location = parent_location.revisit()
        re_revisited_base_location = revisited_base_location.revisit()

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(child_location),
            blocks.Traverse("in", "Animal_ParentOf", optional=True, within_optional_scope=True),
            blocks.MarkLocation(grandchild_location),
            blocks.Traverse("out", "Animal_OfSpecies", within_optional_scope=True),
            blocks.MarkLocation(grandchild_species_location),
            blocks.Backtrack(grandchild_location),
            blocks.EndOptional(),
            blocks.Backtrack(child_location, optional=True),
            blocks.MarkLocation(revisited_child_location),
            blocks.Traverse("in", "Entity_Related", optional=True, within_optional_scope=True),
            blocks.CoerceType({"Animal"}),
            blocks.MarkLocation(child_related_location),
            blocks.Traverse("out", "Animal_OfSpecies", within_optional_scope=True),
            blocks.MarkLocation(child_related_species_location),
            blocks.Backtrack(child_related_location),
            blocks.EndOptional(),
            blocks.Backtrack(revisited_child_location, optional=True),
            blocks.MarkLocation(re_revisited_child_location),
            blocks.EndOptional(),
            blocks.Backtrack(base_location, optional=True),
            blocks.MarkLocation(revisited_base_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True),
            blocks.MarkLocation(parent_location),
            blocks.Traverse("out", "Animal_ParentOf", optional=True, within_optional_scope=True),
            blocks.MarkLocation(grandparent_location),
            blocks.Traverse("out", "Animal_OfSpecies", within_optional_scope=True),
            blocks.MarkLocation(grandparent_species_location),
            blocks.Backtrack(grandparent_location),
            blocks.EndOptional(),
            blocks.Backtrack(parent_location, optional=True),
            blocks.MarkLocation(revisited_parent_location),
            blocks.EndOptional(),
            blocks.Backtrack(revisited_base_location, optional=True),
            blocks.MarkLocation(re_revisited_base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "child_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_location),
                        expressions.OutputContextField(
                            child_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "grandchild_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(grandchild_location),
                        expressions.OutputContextField(
                            grandchild_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "grandchild_species": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(grandchild_species_location),
                        expressions.OutputContextField(
                            grandchild_species_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "grandchild_relation_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_related_location),
                        expressions.OutputContextField(
                            child_related_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "grandchild_relation_species": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(child_related_species_location),
                        expressions.OutputContextField(
                            child_related_species_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "parent_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(parent_location),
                        expressions.OutputContextField(
                            parent_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "grandparent_name": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(grandparent_location),
                        expressions.OutputContextField(
                            grandparent_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                    "grandparent_species": expressions.TernaryConditional(
                        expressions.ContextFieldExistence(grandparent_species_location),
                        expressions.OutputContextField(
                            grandparent_species_location.navigate_to_field("name"), GraphQLString
                        ),
                        expressions.NullLiteral,
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            child_location: "Animal",
            grandchild_location: "Animal",
            grandchild_species_location: "Species",
            child_related_location: "Animal",
            child_related_species_location: "Species",
            parent_location: "Animal",
            grandparent_location: "Animal",
            grandparent_species_location: "Species",
            revisited_base_location: "Animal",
            re_revisited_base_location: "Animal",
            revisited_child_location: "Animal",
            re_revisited_child_location: "Animal",
            revisited_parent_location: "Animal",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_recursive_field_type_is_subtype_of_parent_field(self):
        """Ensure the query can recurse on an edge that links supertype of the parent's field."""
        test_data = test_input_data.recursive_field_type_is_subtype_of_parent_field()

        base_location = helpers.Location(("BirthEvent",))
        related_event_location = base_location.navigate_to_subpath("out_Event_RelatedEvent")

        expected_blocks = [
            blocks.QueryRoot({"BirthEvent"}),
            blocks.MarkLocation(base_location),
            blocks.Recurse("out", "Event_RelatedEvent", 2),
            blocks.MarkLocation(related_event_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "related_event_name": expressions.OutputContextField(
                        related_event_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "BirthEvent",
            related_event_location: "Event",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)

    def test_animal_born_at_traversal(self):
        """Ensure that sql composite key traversals work."""
        test_data = test_input_data.animal_born_at_traversal()

        base_location = helpers.Location(("Animal",))
        birth_location = base_location.navigate_to_subpath("out_Animal_BornAt")

        expected_blocks = [
            blocks.QueryRoot({"Animal"}),
            blocks.MarkLocation(base_location),
            blocks.Traverse("out", "Animal_BornAt", optional=False),
            blocks.MarkLocation(birth_location),
            blocks.Backtrack(base_location),
            blocks.GlobalOperationsStart(),
            blocks.ConstructResult(
                {
                    "animal_name": expressions.OutputContextField(
                        base_location.navigate_to_field("name"), GraphQLString
                    ),
                    "birth_event_name": expressions.OutputContextField(
                        birth_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_location_types = {
            base_location: "Animal",
            birth_location: "BirthEvent",
        }

        check_test_data(self, test_data, expected_blocks, expected_location_types)
