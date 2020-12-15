# Copyright 2017-present Kensho Technologies, LLC.
from pprint import pformat
import unittest

from graphql import GraphQLID, GraphQLString

from ..compiler import ir_lowering_gremlin, ir_lowering_match, ir_self_consistency_checks
from ..compiler.blocks import (
    Backtrack,
    CoerceType,
    ConstructResult,
    EndOptional,
    Filter,
    MarkLocation,
    QueryRoot,
    Traverse,
)
from ..compiler.compiler_frontend import IrAndMetadata, OutputMetadata
from ..compiler.expressions import (
    BinaryComposition,
    ContextField,
    ContextFieldExistence,
    FalseLiteral,
    Literal,
    LocalField,
    NullLiteral,
    OutputContextField,
    TernaryConditional,
    TrueLiteral,
    UnaryTransformation,
    Variable,
    ZeroLiteral,
)
from ..compiler.helpers import Location
from ..compiler.ir_lowering_common.common import (
    OutputContextVertex,
    merge_consecutive_filter_clauses,
    optimize_boolean_expression_comparisons,
)
from ..compiler.ir_lowering_match.utils import BetweenClause, CompoundMatchQuery
from ..compiler.match_query import MatchQuery, convert_to_match_query
from ..compiler.metadata import LocationInfo, QueryMetadataTable
from ..schema import GraphQLDate, GraphQLDateTime
from .test_helpers import compare_ir_blocks, get_common_schema_info, get_schema


def check_test_data(test_case, expected_object, received_object):
    """Assert that the expected and received IR blocks or MATCH queries are the same."""
    if type(expected_object) != type(received_object):
        raise AssertionError(
            "The types of the expected and received objects do not match: "
            "{} vs {}, {} and {}".format(
                type(expected_object), type(received_object), expected_object, received_object
            )
        )

    if isinstance(expected_object, MatchQuery):
        test_case.assertEqual(
            expected_object,
            received_object,
            msg="\n{}\n\n!=\n\n{}".format(pformat(expected_object), pformat(received_object)),
        )
    else:
        compare_ir_blocks(test_case, expected_object, received_object)


class CommonIrLoweringTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema = get_schema()

    def test_optimize_boolean_expression_comparisons(self):
        base_location = Location(("Animal",))
        equality_check = BinaryComposition(
            "=", ContextField(base_location, self.schema.get_type("Animal")), NullLiteral
        )
        inequality_check = BinaryComposition(
            "!=", ContextField(base_location, self.schema.get_type("Animal")), NullLiteral
        )

        test_data = [
            # unaffected
            (equality_check, equality_check),
            (inequality_check, inequality_check),
            # outer check elided
            (BinaryComposition("=", inequality_check, TrueLiteral), inequality_check),
            (BinaryComposition("=", equality_check, TrueLiteral), equality_check),
            (BinaryComposition("!=", inequality_check, FalseLiteral), inequality_check),
            (BinaryComposition("!=", equality_check, FalseLiteral), equality_check),
            # outer check elided + inner comparison inverted
            (BinaryComposition("!=", inequality_check, TrueLiteral), equality_check),
            (BinaryComposition("!=", equality_check, TrueLiteral), inequality_check),
            (BinaryComposition("=", inequality_check, FalseLiteral), equality_check),
            (BinaryComposition("=", equality_check, FalseLiteral), inequality_check),
        ]

        for test_expression, expected_output in test_data:
            ir_blocks = [
                Filter(test_expression),
            ]
            expected_ir_blocks = [
                Filter(expected_output),
            ]
            actual_ir_blocks = optimize_boolean_expression_comparisons(ir_blocks)
            check_test_data(self, expected_ir_blocks, actual_ir_blocks)


class MatchIrLoweringTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None

    def test_context_field_existence_lowering_in_output(self):
        schema = get_schema()

        base_location = Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        child_name_location = child_location.navigate_to_field("name")

        animal_graphql_type = schema.get_type("Animal")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        query_metadata_table.register_location(
            child_location, LocationInfo(base_location, animal_graphql_type, None, 1, 0, False)
        )
        revisited_base_location = query_metadata_table.revisit_location(base_location)

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            MarkLocation(revisited_base_location),
            ConstructResult(
                {
                    "child_name": TernaryConditional(
                        ContextFieldExistence(child_location),
                        OutputContextField(child_name_location, GraphQLString),
                        NullLiteral,
                    )
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        # The expected final blocks just have a rewritten ConstructResult block,
        # where the ContextFieldExistence expression is replaced with a null check.
        expected_final_blocks = ir_blocks[:]
        expected_final_blocks[-1] = ConstructResult(
            {
                "child_name": TernaryConditional(
                    BinaryComposition(
                        "!=", OutputContextVertex(child_location, animal_graphql_type), NullLiteral
                    ),
                    OutputContextField(child_name_location, GraphQLString),
                    NullLiteral,
                )
            }
        )

        final_blocks = ir_lowering_match.lower_context_field_existence(
            ir_blocks, query_metadata_table
        )
        check_test_data(self, expected_final_blocks, final_blocks)

    def test_context_field_existence_lowering_in_filter(self):
        schema = get_schema()

        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        child_name_location = child_location.navigate_to_field("name")

        animal_graphql_type = schema.get_type("Animal")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        query_metadata_table.register_location(
            child_location, LocationInfo(base_location, animal_graphql_type, None, 1, 0, False)
        )
        revisited_base_location = query_metadata_table.revisit_location(base_location)

        second_child_location = revisited_base_location.navigate_to_subpath("in_Animal_ParentOf")
        query_metadata_table.register_location(
            second_child_location,
            LocationInfo(base_location, animal_graphql_type, None, 0, 0, False),
        )

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            MarkLocation(revisited_base_location),
            Traverse("in", "Animal_ParentOf"),
            Filter(
                BinaryComposition(
                    "=",
                    LocalField("name", GraphQLString),
                    TernaryConditional(
                        ContextFieldExistence(child_location),
                        ContextField(child_name_location, GraphQLString),
                        NullLiteral,
                    ),
                )
            ),
            MarkLocation(second_child_location),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        # The expected final blocks have a rewritten ContextFieldExistence expression
        # inside the TernaryConditional expression of the Filter block.
        expected_final_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            MarkLocation(revisited_base_location),
            Traverse("in", "Animal_ParentOf"),
            Filter(
                BinaryComposition(
                    "=",
                    LocalField("name", GraphQLString),
                    TernaryConditional(
                        BinaryComposition(
                            "!=", ContextField(child_location, animal_graphql_type), NullLiteral
                        ),
                        ContextField(child_name_location, GraphQLString),
                        NullLiteral,
                    ),
                )
            ),
            MarkLocation(second_child_location),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]

        final_blocks = ir_lowering_match.lower_context_field_existence(
            ir_blocks, query_metadata_table
        )
        check_test_data(self, expected_final_blocks, final_blocks)

    def test_backtrack_block_lowering_simple(self):
        schema = get_schema()

        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        animal_graphql_type = schema.get_type("Animal")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        query_metadata_table.register_location(
            child_location, LocationInfo(base_location, animal_graphql_type, None, 0, 0, False)
        )

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf"),
            MarkLocation(child_location),
            Backtrack(base_location),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        match_query = convert_to_match_query(ir_blocks)

        # The expected final query consists of two traversals:
        # - one that ends right before the Backtrack block,
        # - one that starts at the location being backtracked to, with the appropriate QueryRoot.
        expected_final_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf"),
            MarkLocation(child_location),
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]
        expected_final_query = convert_to_match_query(expected_final_blocks)

        final_query = ir_lowering_match.lower_backtrack_blocks(match_query, query_metadata_table)
        check_test_data(self, expected_final_query, final_query)

    def test_backtrack_block_lowering_revisiting_root(self):
        schema = get_schema()

        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")
        child_location_1 = base_location.navigate_to_subpath("out_Animal_ParentOf")
        child_location_2 = base_location.navigate_to_subpath("in_Animal_ParentOf")

        animal_graphql_type = schema.get_type("Animal")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        query_metadata_table.register_location(
            child_location_1, LocationInfo(base_location, animal_graphql_type, None, 0, 0, False)
        )
        query_metadata_table.register_location(
            child_location_2, LocationInfo(base_location, animal_graphql_type, None, 0, 0, False)
        )

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf"),
            MarkLocation(child_location_1),
            Backtrack(base_location),
            Traverse("in", "Animal_ParentOf"),
            MarkLocation(child_location_2),
            Backtrack(base_location),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        match_query = convert_to_match_query(ir_blocks)

        # The expected final query consists of three traversals:
        # - one that ends right before the Backtrack block,
        # - two that start at the locations being backtracked to, with the appropriate QueryRoots.
        expected_final_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf"),
            MarkLocation(child_location_1),
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("in", "Animal_ParentOf"),
            MarkLocation(child_location_2),
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]
        expected_final_query = convert_to_match_query(expected_final_blocks)

        final_query = ir_lowering_match.lower_backtrack_blocks(match_query, query_metadata_table)
        check_test_data(self, expected_final_query, final_query)

    def test_optional_backtrack_block_lowering(self):
        schema = get_schema()

        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        animal_graphql_type = schema.get_type("Animal")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        query_metadata_table.register_location(
            child_location, LocationInfo(base_location, animal_graphql_type, None, 1, 0, False)
        )
        base_location_revisited = query_metadata_table.revisit_location(base_location)

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            MarkLocation(base_location_revisited),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        match_query = convert_to_match_query(ir_blocks)

        # The expected final query consists of two traversals:
        # - one that ends right before the Backtrack block,
        # - one that starts at the location being backtracked to, with the appropriate QueryRoot.
        # Notably, the "base_location_revisited" is rewritten and replaced with "base_location".
        expected_final_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]
        expected_final_query = convert_to_match_query(expected_final_blocks)

        final_query = ir_lowering_match.lower_backtrack_blocks(match_query, query_metadata_table)
        check_test_data(self, expected_final_query, final_query)

    def test_backtrack_lowering_with_optional_traverse_after_mandatory_traverse(self):
        # This testcase caught a bug in the lowering of Backtrack blocks
        # using locations added after Backtrack with optional=False but before a
        # Traverse with optional=True.
        schema = get_schema()

        base_location = Location(("Animal",))
        species_location = base_location.navigate_to_subpath("out_Animal_OfSpecies")
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")

        animal_graphql_type = schema.get_type("Animal")
        species_graphql_type = schema.get_type("Species")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        revisited_base_location = query_metadata_table.revisit_location(base_location)
        twice_revisited_base_location = query_metadata_table.revisit_location(
            revisited_base_location
        )
        query_metadata_table.register_location(
            species_location, LocationInfo(base_location, species_graphql_type, None, 0, 0, False)
        )
        query_metadata_table.register_location(
            child_location,
            LocationInfo(revisited_base_location, animal_graphql_type, None, 1, 0, False),
        )

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_OfSpecies"),
            MarkLocation(species_location),
            Backtrack(base_location),
            MarkLocation(revisited_base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            Backtrack(revisited_base_location, optional=True),
            MarkLocation(twice_revisited_base_location),
            ConstructResult(
                {
                    "species_name": OutputContextField(
                        species_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        match_query = convert_to_match_query(ir_blocks)

        # The expected final query consists of three traversals:
        # - one that ends right before the Backtrack block,
        # - two that start at the locations being backtracked to, with the appropriate QueryRoots.
        # Notably, the "revisited_base_location" and the "twice_revisited_base_location"
        # are rewritten and replaced with "base_location".
        expected_final_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_OfSpecies"),
            MarkLocation(species_location),
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            ConstructResult(
                {
                    "species_name": OutputContextField(
                        species_location.navigate_to_field("name"), GraphQLString
                    ),
                }
            ),
        ]
        expected_final_query = convert_to_match_query(expected_final_blocks)

        final_query = ir_lowering_match.lower_backtrack_blocks(match_query, query_metadata_table)
        check_test_data(self, expected_final_query, final_query)

    def test_unnecessary_traversal_elimination(self):
        # This test case caught a bug in the optimization pass that eliminates unnecessary
        # traversals, where it would fail to remove part of the dead code
        # if there were more than two @optional traversals from the same location.
        #
        # The problem in the optimization pass was the following:
        # - N @optional traversals from a given location X, would generate N QueryRoot
        #   blocks at that location N;
        # - exactly 2 of those QueryRoots would be eliminated away, leaving (N - 2) behind
        # - each such QueryRoot would multiplicatively increase the complexity of the query
        #   by a linear term -- the number of entries at that QueryRoot.
        #
        # This test ensures that all N=3 of the QueryRoots are eliminated away, rather than just 2.
        # See the complementary end-to-end version of the test in test_compiler.py for more details.
        schema = get_schema()

        base_location = Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        species_location = base_location.navigate_to_subpath("out_Animal_OfSpecies")
        event_location = base_location.navigate_to_subpath("out_Animal_FedAt")

        animal_graphql_type = schema.get_type("Animal")
        species_graphql_type = schema.get_type("Species")
        event_graphql_type = schema.get_type("Event")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        revisited_base_location = query_metadata_table.revisit_location(base_location)
        twice_revisited_base_location = query_metadata_table.revisit_location(
            revisited_base_location
        )
        thrice_revisited_base_location = query_metadata_table.revisit_location(
            twice_revisited_base_location
        )
        query_metadata_table.register_location(
            child_location, LocationInfo(base_location, animal_graphql_type, None, 1, 0, False)
        )
        query_metadata_table.register_location(
            species_location,
            LocationInfo(revisited_base_location, species_graphql_type, None, 1, 0, False),
        )
        query_metadata_table.register_location(
            event_location,
            LocationInfo(twice_revisited_base_location, event_graphql_type, None, 1, 0, False),
        )

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            MarkLocation(revisited_base_location),
            Traverse("out", "Animal_OfSpecies", optional=True),
            MarkLocation(species_location),
            Backtrack(revisited_base_location, optional=True),
            MarkLocation(twice_revisited_base_location),
            Traverse("out", "Animal_FedAt", optional=True),
            MarkLocation(event_location),
            Backtrack(twice_revisited_base_location, optional=True),
            MarkLocation(thrice_revisited_base_location),
            ConstructResult(
                {
                    "event_uuid": OutputContextField(
                        event_location.navigate_to_field("uuid"), GraphQLID
                    ),
                    "child_uuid": OutputContextField(
                        child_location.navigate_to_field("uuid"), GraphQLID
                    ),
                    "species_uuid": OutputContextField(
                        species_location.navigate_to_field("uuid"), GraphQLID
                    ),
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        match_query = convert_to_match_query(ir_blocks)

        # The expected final query consists of the three optional traversals.
        # There is no traversal that only captures the starting 'Animal' location
        # (with a "revisited" name) and nothing else -- it has been optimized away.
        expected_final_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_OfSpecies", optional=True),
            MarkLocation(species_location),
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_FedAt", optional=True),
            MarkLocation(event_location),
            ConstructResult(
                {
                    "event_uuid": OutputContextField(
                        event_location.navigate_to_field("uuid"), GraphQLID
                    ),
                    "child_uuid": OutputContextField(
                        child_location.navigate_to_field("uuid"), GraphQLID
                    ),
                    "species_uuid": OutputContextField(
                        species_location.navigate_to_field("uuid"), GraphQLID
                    ),
                }
            ),
        ]
        expected_final_query = convert_to_match_query(expected_final_blocks)

        temp_query = ir_lowering_match.lower_backtrack_blocks(match_query, query_metadata_table)
        final_query = ir_lowering_match.truncate_repeated_single_step_traversals(temp_query)

        check_test_data(self, expected_final_query, final_query)

    def test_merge_consecutive_filter_clauses(self):
        schema = get_schema()

        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")

        animal_graphql_type = schema.get_type("Animal")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        ir_blocks = [
            QueryRoot({"Animal"}),
            Filter(
                BinaryComposition(
                    "<=",
                    LocalField("birthday", GraphQLDate),
                    Variable("$foo_birthday", GraphQLDate),
                )
            ),
            Filter(
                BinaryComposition(
                    "=", LocalField("name", GraphQLString), Variable("$foo_name", GraphQLString)
                )
            ),
            Filter(
                BinaryComposition(
                    "=", LocalField("color", GraphQLString), Variable("$foo_color", GraphQLString)
                )
            ),
            MarkLocation(base_location),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        # The expected final blocks have one Filter block with the predicates joined by an AND.
        expected_final_blocks = [
            QueryRoot({"Animal"}),
            Filter(
                BinaryComposition(
                    "&&",
                    BinaryComposition(
                        "&&",
                        BinaryComposition(
                            "<=",
                            LocalField("birthday", GraphQLDate),
                            Variable("$foo_birthday", GraphQLDate),
                        ),
                        BinaryComposition(
                            "=",
                            LocalField("name", GraphQLString),
                            Variable("$foo_name", GraphQLString),
                        ),
                    ),
                    BinaryComposition(
                        "=",
                        LocalField("color", GraphQLString),
                        Variable("$foo_color", GraphQLString),
                    ),
                )
            ),
            MarkLocation(base_location),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]

        final_blocks = merge_consecutive_filter_clauses(ir_blocks)
        check_test_data(self, expected_final_blocks, final_blocks)

    def test_binary_composition_inside_ternary_conditional(self):
        # Modified excerpt from "test_complex_optional_variables" in test_ir_generation.py
        base_location = Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        other_parent_location = child_location.navigate_to_subpath("in_Animal_ParentOf")
        other_parent_fed_at_location = other_parent_location.navigate_to_subpath("out_Animal_FedAt")
        other_parent_fed_at_tag = other_parent_fed_at_location.navigate_to_field("event_date")

        special_ir_block = [
            Filter(
                TernaryConditional(
                    BinaryComposition(
                        "!=",
                        ContextField(other_parent_location.navigate_to_field("uuid"), GraphQLID),
                        ContextField(
                            other_parent_fed_at_location.navigate_to_field("uuid"), GraphQLID
                        ),
                    ),
                    BinaryComposition(
                        ">=",
                        LocalField("event_date", GraphQLDateTime),
                        ContextField(other_parent_fed_at_tag, GraphQLDateTime),
                    ),
                    TrueLiteral,
                )
            )
        ]

        # The expected final blocks rewrite the BinaryComposition expression
        # into another TernaryConditional that explicitly returns TrueLiteral or FalseLiteral.
        expected_final_blocks = [
            Filter(
                BinaryComposition(
                    "=",
                    TernaryConditional(
                        BinaryComposition(
                            "!=",
                            ContextField(
                                other_parent_location.navigate_to_field("uuid"), GraphQLID
                            ),
                            ContextField(
                                other_parent_fed_at_location.navigate_to_field("uuid"), GraphQLID
                            ),
                        ),
                        TernaryConditional(
                            BinaryComposition(
                                ">=",
                                LocalField("event_date", GraphQLDateTime),
                                ContextField(other_parent_fed_at_tag, GraphQLDateTime),
                            ),
                            TrueLiteral,
                            FalseLiteral,
                        ),
                        TrueLiteral,
                    ),
                    TrueLiteral,
                )
            )
        ]

        final_blocks = ir_lowering_match.rewrite_binary_composition_inside_ternary_conditional(
            special_ir_block
        )
        check_test_data(self, expected_final_blocks, final_blocks)

    def test_lower_has_substring_binary_compositions(self):
        # Modified excerpt from "test_has_substring_op_filter_with_optional_tag"
        # in test_ir_generation.py
        base_location = Location(("Animal",))
        parent_location = base_location.navigate_to_subpath("in_Animal_ParentOf")

        special_ir_block = [
            Filter(
                BinaryComposition(
                    "&&",
                    ContextFieldExistence(parent_location),
                    BinaryComposition(
                        "has_substring",
                        ContextField(parent_location.navigate_to_field("name"), GraphQLString),
                        LocalField("name", GraphQLString),
                    ),
                )
            )
        ]

        # The expected final blocks rewrite the BinaryComposition expression
        # into another TernaryConditional that explicitly returns TrueLiteral or FalseLiteral.
        expected_final_blocks = [
            Filter(
                BinaryComposition(
                    "&&",
                    ContextFieldExistence(parent_location),
                    BinaryComposition(
                        "LIKE",
                        ContextField(parent_location.navigate_to_field("name"), GraphQLString),
                        BinaryComposition(
                            "+",
                            Literal("%"),
                            BinaryComposition("+", LocalField("name", GraphQLString), Literal("%")),
                        ),
                    ),
                )
            )
        ]

        final_block = ir_lowering_match.lower_string_operators(special_ir_block)
        check_test_data(self, expected_final_blocks, final_block)

    def test_between_lowering_inverted_inequalities(self):
        # Lowering two `>=` inequalities to a BETWEEN clause
        base_location = Location(("Animal",))

        filter_block = Filter(
            BinaryComposition(
                "&&",
                BinaryComposition(
                    ">=",
                    Variable("$upper", GraphQLString),
                    LocalField("name", GraphQLString),
                ),
                BinaryComposition(
                    ">=", LocalField("name", GraphQLString), Variable("$lower", GraphQLString)
                ),
            )
        )
        ir_blocks = [
            QueryRoot({"Animal"}),
            filter_block,
            MarkLocation(base_location),
            ConstructResult(
                {"name": OutputContextField(base_location.navigate_to_field("name"), GraphQLString)}
            ),
        ]
        match_query = convert_to_match_query(ir_blocks)

        expected_final_filter_block = Filter(
            BetweenClause(
                LocalField("name", GraphQLString),
                Variable("$lower", GraphQLString),
                Variable("$upper", GraphQLString),
            )
        )
        expected_final_ir_blocks = [
            QueryRoot({"Animal"}),
            expected_final_filter_block,
            MarkLocation(base_location),
            ConstructResult(
                {"name": OutputContextField(base_location.navigate_to_field("name"), GraphQLString)}
            ),
        ]
        expected_final_query = convert_to_match_query(expected_final_ir_blocks)

        final_query = ir_lowering_match.lower_comparisons_to_between(match_query)
        check_test_data(self, expected_final_query, final_query)

    def test_optional_traversal_edge_case(self):
        # Both Animal and out_Animal_ParentOf have an out_Animal_FedAt field,
        # ensure the correct such field is picked out after full lowering.
        #
        # Equivalent GraphQL:
        #
        # graphql_input = '''{
        #     Animal {
        #         out_Animal_ParentOf @optional {
        #             out_Animal_FedAt {
        #                 name @output(out_name: "name")
        #             }
        #         }
        #     }
        # }'''
        schema = get_schema()

        base_location = Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        child_fed_at_location = child_location.navigate_to_subpath("out_Animal_FedAt")

        animal_graphql_type = schema.get_type("Animal")
        event_graphql_type = schema.get_type("Event")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        query_metadata_table.register_location(
            child_location, LocationInfo(base_location, animal_graphql_type, None, 1, 0, False)
        )
        query_metadata_table.register_location(
            child_fed_at_location,
            LocationInfo(child_location, event_graphql_type, None, 1, 0, False),
        )
        revisited_base_location = query_metadata_table.revisit_location(base_location)

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            Traverse("out", "Animal_FedAt"),
            MarkLocation(child_fed_at_location),
            Backtrack(child_location),
            EndOptional(),
            Backtrack(base_location, optional=True),
            MarkLocation(revisited_base_location),
            ConstructResult(
                {
                    "name": TernaryConditional(
                        ContextFieldExistence(child_fed_at_location),
                        OutputContextField(
                            child_fed_at_location.navigate_to_field("name"), GraphQLString
                        ),
                        NullLiteral,
                    ),
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        expected_final_blocks_without_optional_traverse = [
            QueryRoot({"Animal"}),
            Filter(
                BinaryComposition(
                    "||",
                    BinaryComposition("=", LocalField("out_Animal_ParentOf", None), NullLiteral),
                    BinaryComposition(
                        "=",
                        UnaryTransformation("size", LocalField("out_Animal_ParentOf", None)),
                        ZeroLiteral,
                    ),
                )
            ),
            MarkLocation(base_location),
            ConstructResult({}),
        ]
        expected_final_blocks_with_optional_traverse = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf"),
            CoerceType({"Animal"}),
            MarkLocation(child_location),
            Traverse("out", "Animal_FedAt"),
            CoerceType({"Event"}),
            MarkLocation(child_fed_at_location),
            ConstructResult(
                {
                    "name": OutputContextField(
                        child_fed_at_location.navigate_to_field("name"), GraphQLString
                    )
                }
            ),
        ]
        expected_match_query_without_optional_traverse = convert_to_match_query(
            expected_final_blocks_without_optional_traverse
        )
        expected_match_query_with_optional_traverse = convert_to_match_query(
            expected_final_blocks_with_optional_traverse
        )

        expected_compound_match_query = CompoundMatchQuery(
            match_queries=[
                expected_match_query_without_optional_traverse,
                expected_match_query_with_optional_traverse,
            ]
        )

        schema_info = get_common_schema_info()
        input_metadata = {}
        output_metadata = {"name": OutputMetadata(type=GraphQLString, optional=False, folded=False)}
        ir = IrAndMetadata(ir_blocks, input_metadata, output_metadata, query_metadata_table)
        final_query = ir_lowering_match.lower_ir(schema_info, ir)

        self.assertEqual(
            expected_compound_match_query,
            final_query,
            msg="\n{}\n\n!=\n\n{}".format(
                pformat(expected_compound_match_query), pformat(final_query)
            ),
        )


class GremlinIrLoweringTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None

    def test_context_field_existence_lowering(self):
        schema = get_schema()

        base_location = Location(("Animal",))
        child_location = base_location.navigate_to_subpath("out_Animal_ParentOf")
        child_name_location = child_location.navigate_to_field("name")

        animal_graphql_type = schema.get_type("Animal")
        base_location_info = LocationInfo(None, animal_graphql_type, None, 0, 0, False)
        query_metadata_table = QueryMetadataTable(base_location, base_location_info)

        query_metadata_table.register_location(
            child_location, LocationInfo(base_location, animal_graphql_type, None, 1, 0, False)
        )
        revisited_base_location = query_metadata_table.revisit_location(base_location)

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_ParentOf", optional=True),
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            MarkLocation(revisited_base_location),
            ConstructResult(
                {
                    "child_name": TernaryConditional(
                        ContextFieldExistence(child_location),
                        OutputContextField(child_name_location, GraphQLString),
                        NullLiteral,
                    )
                }
            ),
        ]
        ir_self_consistency_checks.self_consistency_check_ir_blocks_from_frontend(
            ir_blocks, query_metadata_table
        )

        # The expected final blocks just have a rewritten ConstructResult block,
        # where the ContextFieldExistence expression is replaced with a marked vertex null check.
        expected_final_blocks = ir_blocks[:-1]
        expected_final_blocks.append(
            ConstructResult(
                {
                    "child_name": TernaryConditional(
                        BinaryComposition(
                            "!=",
                            OutputContextVertex(child_location, animal_graphql_type),
                            NullLiteral,
                        ),
                        OutputContextField(child_name_location, GraphQLString),
                        NullLiteral,
                    )
                }
            )
        )

        final_blocks = ir_lowering_gremlin.lower_context_field_existence(
            ir_blocks, query_metadata_table
        )
        check_test_data(self, expected_final_blocks, final_blocks)
