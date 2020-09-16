# Copyright 2017-present Kensho Technologies, LLC.
import unittest

from graphql import GraphQLString
from sqlalchemy.dialects.mssql.base import MSDialect

from ..compiler import emit_cypher, emit_gremlin, emit_match, emit_sql
from ..compiler.blocks import (
    Backtrack,
    CoerceType,
    ConstructResult,
    Filter,
    GlobalOperationsStart,
    MarkLocation,
    QueryRoot,
    Traverse,
)
from ..compiler.cypher_query import convert_to_cypher_query
from ..compiler.expressions import (
    BinaryComposition,
    ContextField,
    LocalField,
    NullLiteral,
    OutputContextField,
    TernaryConditional,
    Variable,
)
from ..compiler.helpers import Location
from ..compiler.ir_lowering_common.common import OutputContextVertex
from ..compiler.ir_lowering_match.utils import CompoundMatchQuery
from ..compiler.match_query import convert_to_match_query
from ..compiler.metadata import LocationInfo, QueryMetadataTable
from ..compiler.sqlalchemy_extensions import print_sqlalchemy_query_string
from ..schema import GraphQLDateTime
from .test_helpers import (
    compare_cypher,
    compare_gremlin,
    compare_match,
    compare_sql,
    get_common_schema_info,
    get_schema,
    get_sqlalchemy_schema_info,
)


class EmitMatchTests(unittest.TestCase):
    def setUp(self) -> None:
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema_info = get_common_schema_info()

    def test_simple_immediate_output(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         name @output(out_name: "animal_name")
        #     }
        # }'''
        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            ConstructResult({"animal_name": OutputContextField(base_name_location, GraphQLString)}),
        ]
        match_query = convert_to_match_query(ir_blocks)
        compound_match_query = CompoundMatchQuery(match_queries=[match_query])

        expected_match = """
            SELECT Animal___1.name AS `animal_name` FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
        """

        received_match = emit_match.emit_code_from_ir(self.schema_info, compound_match_query)
        compare_match(self, expected_match, received_match)

    def test_simple_traverse_filter_output(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         name @tag(tag_name: "name")
        #              @output(out_name: "animal_name")
        #         out_Animal_BornAt {
        #             name @filter(op_name: "=", value: ["%name"])
        #         }
        #     }
        # }'''
        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")
        child_location = base_location.navigate_to_subpath("out_Animal_BornAt")

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_BornAt"),
            Filter(
                BinaryComposition(
                    "=",
                    LocalField("name", GraphQLString),
                    ContextField(base_name_location, GraphQLString),
                )
            ),
            MarkLocation(child_location),
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]
        match_query = convert_to_match_query(ir_blocks)
        compound_match_query = CompoundMatchQuery(match_queries=[match_query])

        expected_match = """
            SELECT Animal___1.name AS `animal_name` FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_BornAt') {{
                    where: ((name = $matched.Animal___1.name)),
                    as: Animal__out_Animal_BornAt___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
        """

        received_match = emit_match.emit_code_from_ir(self.schema_info, compound_match_query)
        compare_match(self, expected_match, received_match)

    def test_datetime_variable_representation(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     BirthEvent {
        #         name @output(out_name: "name")
        #         event_date @filter(op_name: "between", value: ["$start", "$end"])
        #     }
        # }'''
        base_location = Location(("BirthEvent",))
        base_name_location = base_location.navigate_to_field("name")

        ir_blocks = [
            QueryRoot({"BirthEvent"}),
            Filter(
                BinaryComposition(
                    "&&",
                    BinaryComposition(
                        ">=",
                        LocalField("event_date", GraphQLDateTime),
                        Variable("$start", GraphQLDateTime),
                    ),
                    BinaryComposition(
                        "<=",
                        LocalField("event_date", GraphQLDateTime),
                        Variable("$end", GraphQLDateTime),
                    ),
                )
            ),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            ConstructResult({"name": OutputContextField(base_name_location, GraphQLString)}),
        ]
        match_query = convert_to_match_query(ir_blocks)
        compound_match_query = CompoundMatchQuery(match_queries=[match_query])

        expected_match = """
            SELECT BirthEvent___1.name AS `name` FROM (
                MATCH {{
                    class: BirthEvent,
                    where: ((
                        (event_date >= date({start}, "yyyy-MM-dd'T'HH:mm:ss")) AND
                        (event_date <= date({end}, "yyyy-MM-dd'T'HH:mm:ss"))
                    )),
                    as: BirthEvent___1
                }}
                RETURN $matches
            )
        """

        received_match = emit_match.emit_code_from_ir(self.schema_info, compound_match_query)
        compare_match(self, expected_match, received_match)

    def test_datetime_output_representation(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     BirthEvent {
        #         event_date @output(out_name: "event_date")
        #     }
        # }'''
        base_location = Location(("BirthEvent",))
        base_event_date_location = base_location.navigate_to_field("event_date")

        ir_blocks = [
            QueryRoot({"BirthEvent"}),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            ConstructResult(
                {"event_date": OutputContextField(base_event_date_location, GraphQLDateTime)}
            ),
        ]
        match_query = convert_to_match_query(ir_blocks)
        compound_match_query = CompoundMatchQuery(match_queries=[match_query])

        expected_match = """
            SELECT BirthEvent___1.event_date.format("yyyy-MM-dd'T'HH:mm:ss") AS `event_date` FROM (
                MATCH {{
                    class: BirthEvent,
                    as: BirthEvent___1
                }}
                RETURN $matches
            )
        """

        received_match = emit_match.emit_code_from_ir(self.schema_info, compound_match_query)
        compare_match(self, expected_match, received_match)


class EmitGremlinTests(unittest.TestCase):
    def setUp(self) -> None:
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema_info = get_common_schema_info()

    def test_simple_immediate_output(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         name @output(out_name: "animal_name")
        #     }
        # }'''
        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]

        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """

        received_gremlin = emit_gremlin.emit_code_from_ir(self.schema_info, ir_blocks)
        compare_gremlin(self, expected_gremlin, received_gremlin)

    def test_simple_traverse_filter_output(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         name @tag(tag_name: "name")
        #              @output(out_name: "animal_name")
        #         out_Animal_BornAt {
        #             name @filter(op_name: "=", value: ["%name"])
        #         }
        #     }
        # }'''
        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")
        child_location = base_location.navigate_to_subpath("out_Animal_BornAt")

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_BornAt"),
            Filter(
                BinaryComposition(
                    "=",
                    LocalField("name", GraphQLString),
                    ContextField(base_location.navigate_to_field("name"), GraphQLString),
                )
            ),
            MarkLocation(child_location),
            Backtrack(base_location),
            GlobalOperationsStart(),
            ConstructResult(
                {
                    "animal_name": OutputContextField(base_name_location, GraphQLString),
                }
            ),
        ]

        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_BornAt')
            .filter{it, m -> (it.name == m.Animal___1.name)}
            .as('Animal__out_Animal_BornAt___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """

        received_gremlin = emit_gremlin.emit_code_from_ir(self.schema_info, ir_blocks)
        compare_gremlin(self, expected_gremlin, received_gremlin)

    def test_output_inside_optional_traversal(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         out_Animal_BornAt @optional {
        #             name @output(out_name: "bornat_name")
        #         }
        #     }
        # }'''
        base_location = Location(("Animal",))
        revisited_base_location = base_location.revisit()
        child_location = base_location.navigate_to_subpath("out_Animal_BornAt")
        child_name_location = child_location.navigate_to_field("name")

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_BornAt", optional=True),
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            MarkLocation(revisited_base_location),
            GlobalOperationsStart(),
            ConstructResult(
                {
                    "bornat_name": TernaryConditional(
                        BinaryComposition(
                            "!=",
                            # HACK(predrag): The type given to OutputContextVertex here is wrong,
                            #                but it shouldn't cause any trouble since it has
                            #                absolutely nothing to do with the code being tested.
                            OutputContextVertex(child_location, GraphQLString),
                            NullLiteral,
                        ),
                        OutputContextField(child_name_location, GraphQLString),
                        NullLiteral,
                    )
                }
            ),
        ]

        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .ifThenElse{it.out_Animal_BornAt == null}{null}{it.out('Animal_BornAt')}
            .as('Animal__out_Animal_BornAt___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                bornat_name: ((m.Animal__out_Animal_BornAt___1 != null) ?
                m.Animal__out_Animal_BornAt___1.name : null)
            ])}
        """

        received_gremlin = emit_gremlin.emit_code_from_ir(self.schema_info, ir_blocks)
        compare_gremlin(self, expected_gremlin, received_gremlin)

    def test_datetime_variable_representation(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     BirthEvent {
        #         name @output(out_name: "name")
        #         event_date @filter(op_name: "between", value: ["$start", "$end"])
        #     }
        # }'''
        base_location = Location(("BirthEvent",))
        base_name_location = base_location.navigate_to_field("name")

        ir_blocks = [
            QueryRoot({"BirthEvent"}),
            MarkLocation(base_location),
            Filter(
                BinaryComposition(
                    "&&",
                    BinaryComposition(
                        ">=",
                        LocalField("event_date", GraphQLDateTime),
                        Variable("$start", GraphQLDateTime),
                    ),
                    BinaryComposition(
                        "<=",
                        LocalField("event_date", GraphQLDateTime),
                        Variable("$end", GraphQLDateTime),
                    ),
                )
            ),
            GlobalOperationsStart(),
            ConstructResult({"name": OutputContextField(base_name_location, GraphQLString)}),
        ]

        expected_gremlin = """
             g.V('@class', 'BirthEvent')
            .as('BirthEvent___1')
            .filter{it, m -> ((it.event_date >= Date.parse("yyyy-MM-dd'T'HH:mm:ss", $start)) &&
                              (it.event_date <= Date.parse("yyyy-MM-dd'T'HH:mm:ss", $end)))}
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.BirthEvent___1.name
            ])}
        """

        received_gremlin = emit_gremlin.emit_code_from_ir(self.schema_info, ir_blocks)
        compare_gremlin(self, expected_gremlin, received_gremlin)

    def test_datetime_output_representation(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     BirthEvent {
        #         event_date @output(out_name: "event_date")
        #     }
        # }'''
        base_location = Location(("BirthEvent",))
        base_event_date_location = base_location.navigate_to_field("event_date")

        ir_blocks = [
            QueryRoot({"BirthEvent"}),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            ConstructResult(
                {"event_date": OutputContextField(base_event_date_location, GraphQLDateTime)}
            ),
        ]

        expected_gremlin = """
            g.V('@class', 'BirthEvent')
            .as('BirthEvent___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                event_date: m.BirthEvent___1.event_date.format("yyyy-MM-dd'T'HH:mm:ss")
            ])}
        """

        received_gremlin = emit_gremlin.emit_code_from_ir(self.schema_info, ir_blocks)
        compare_gremlin(self, expected_gremlin, received_gremlin)


class EmitCypherTests(unittest.TestCase):
    """Test emit_code_from_ir method for Cypher.

    We follow the test schema (defined in test_helpers.py) for these tests so that we can construct
    objects correctly (e.g. when setting the type field for a LocationInfo object). When we call
    schema.get_type(), we get a reference to an object, which is not the case if we wrote something
    like `GraphQLObjectType(name='Foo', fields={'name': GraphQLString}` instead. This is useful if
    we need to compare two LocationInfo objects because equality comparison compares references.
    """

    def setUp(self) -> None:
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema_info = get_common_schema_info()

    def test_simple_immediate_output(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         name @output(out_name: "animal_name")
        #     }
        # }'''
        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")
        schema = get_schema()
        base_location_info = LocationInfo(
            parent_location=None,
            type=schema.get_type("Animal"),
            coerced_from_type=None,
            optional_scopes_depth=0,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            GlobalOperationsStart(),  # necessary for Cypher. Filter/output blocks come after this.
            ConstructResult({"animal_name": OutputContextField(base_name_location, GraphQLString)}),
        ]
        query_metadata_table = QueryMetadataTable(
            root_location=base_location, root_location_info=base_location_info
        )

        cypher_query = convert_to_cypher_query(ir_blocks, query_metadata_table)
        received_cypher = emit_cypher.emit_code_from_ir(self.schema_info, cypher_query)

        expected_cypher = """
            MATCH (Animal___1:Animal)
            RETURN Animal___1.name AS `animal_name`
        """

        compare_cypher(self, expected_cypher, received_cypher)

    def test_simple_traverse_filter_output(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         name @tag(tag_name: "name")
        #              @output(out_name: "animal_name")
        #         out_Animal_BornAt {
        #             name @filter(op_name: "=", value: ["%name"])
        #         }
        #     }
        # }'''
        base_location = Location(("Animal",))
        base_name_location = base_location.navigate_to_field("name")
        schema = get_schema()
        base_location_info = LocationInfo(
            parent_location=None,
            type=schema.get_type("Animal"),
            coerced_from_type=None,
            optional_scopes_depth=0,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        child_location = base_location.navigate_to_subpath("out_Animal_BornAt")
        child_name_location = child_location.navigate_to_field("name")
        child_location_info = LocationInfo(
            parent_location=base_location,
            type=schema.get_type("BirthEvent"),
            coerced_from_type=None,
            optional_scopes_depth=1,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_BornAt"),
            CoerceType(
                {"BirthEvent"}
            ),  # see compiler.ir_lowering_cypher's insert_explicit_type_bounds method
            Filter(
                BinaryComposition(
                    "=",
                    # see compiler.ir_lowering_cypher's replace_local_fields_with_context_fields
                    # method LocalField("name", GraphQLString) gets replaced with the
                    # child_location field "name"
                    ContextField(child_name_location, GraphQLString),
                    ContextField(base_name_location, GraphQLString),
                )
            ),
            MarkLocation(child_location),
            Backtrack(base_location),
            GlobalOperationsStart(),
            ConstructResult({"animal_name": OutputContextField(base_name_location, GraphQLString)}),
        ]
        query_metadata_table = QueryMetadataTable(
            root_location=base_location, root_location_info=base_location_info
        )
        query_metadata_table.register_location(child_location, child_location_info)

        cypher_query = convert_to_cypher_query(ir_blocks, query_metadata_table)
        received_cypher = emit_cypher.emit_code_from_ir(self.schema_info, cypher_query)

        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Animal_BornAt]->(Animal__out_Animal_BornAt___1:BirthEvent)
              WHERE (Animal__out_Animal_BornAt___1.name = Animal___1.name)
            RETURN
              Animal___1.name AS `animal_name`
        """
        compare_cypher(self, expected_cypher, received_cypher)

    def test_output_inside_optional_traversal(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         out_Animal_BornAt @optional {
        #             name @output(out_name: "bornat_name")
        #         }
        #     }
        # }'''
        base_location = Location(("Animal",))
        schema = get_schema()
        base_location_info = LocationInfo(
            parent_location=None,
            type=schema.get_type("Animal"),
            coerced_from_type=None,
            optional_scopes_depth=0,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        child_location = base_location.navigate_to_subpath("out_Animal_BornAt")
        child_name_location = child_location.navigate_to_field("name")
        child_location_info = LocationInfo(
            parent_location=base_location,
            type=schema.get_type("BirthEvent"),
            coerced_from_type=None,
            optional_scopes_depth=1,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        ir_blocks = [
            QueryRoot({"Animal"}),
            MarkLocation(base_location),
            Traverse("out", "Animal_BornAt", optional=True),
            CoerceType(
                {"BirthEvent"}
            ),  # see compiler.ir_lowering_cypher's insert_explicit_type_bounds method
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            # see compiler.ir_lowering_cypher's remove_mark_location_after_optional_backtrack method
            # MarkLocation(revisited_base_location),
            GlobalOperationsStart(),
            ConstructResult(
                {
                    "bornat_name": TernaryConditional(
                        BinaryComposition(
                            "!=",
                            # HACK(predrag): The type given to OutputContextVertex here is wrong,
                            # but it shouldn't cause any trouble since it has absolutely nothing to
                            # do with the code being tested.
                            OutputContextVertex(child_location, GraphQLString),
                            NullLiteral,
                        ),
                        OutputContextField(child_name_location, GraphQLString),
                        NullLiteral,
                    )
                }
            ),
        ]
        query_metadata_table = QueryMetadataTable(
            root_location=base_location, root_location_info=base_location_info
        )
        query_metadata_table.register_location(child_location, child_location_info)

        cypher_query = convert_to_cypher_query(ir_blocks, query_metadata_table)
        received_cypher = emit_cypher.emit_code_from_ir(self.schema_info, cypher_query)

        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_BornAt]->(Animal__out_Animal_BornAt___1:BirthEvent)
            RETURN
                (CASE WHEN (Animal__out_Animal_BornAt___1 IS NOT null)
                THEN Animal__out_Animal_BornAt___1.name ELSE null END) AS `bornat_name`
        """

        compare_cypher(self, expected_cypher, received_cypher)

    def test_datetime_output_representation(self) -> None:
        # corresponds to:
        # graphql_string = '''{
        #     BirthEvent {
        #         event_date @output(out_name: "event_date")
        #     }
        # }'''
        base_location = Location(("BirthEvent",))
        base_event_date_location = base_location.navigate_to_field("event_date")
        schema = get_schema()
        base_location_info = LocationInfo(
            parent_location=None,
            type=schema.get_type("BirthEvent"),
            coerced_from_type=None,
            optional_scopes_depth=0,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        ir_blocks = [
            QueryRoot({"BirthEvent"}),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            ConstructResult(
                {"event_date": OutputContextField(base_event_date_location, GraphQLDateTime)}
            ),
        ]
        query_metadata_table = QueryMetadataTable(
            root_location=base_location, root_location_info=base_location_info
        )

        cypher_query = convert_to_cypher_query(ir_blocks, query_metadata_table)
        received_cypher = emit_cypher.emit_code_from_ir(self.schema_info, cypher_query)

        expected_cypher = """
            MATCH (BirthEvent___1:BirthEvent)
            RETURN
            BirthEvent___1.event_date AS `event_date`
        """

        compare_cypher(self, expected_cypher, received_cypher)


class EmitSQLTests(unittest.TestCase):
    """Test emit_sql from IR."""

    def setUp(self) -> None:
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema_infos = {
            "mssql": get_sqlalchemy_schema_info("mssql"),
            "postgresql": get_sqlalchemy_schema_info("postgresql"),
        }

    def test_fold_subquery_builder(self) -> None:
        dialect = MSDialect()
        table = self.schema_infos["mssql"].vertex_name_to_table["Animal"]
        join_descriptor = self.schema_infos["mssql"].join_descriptors["Animal"][
            "out_Animal_ParentOf"
        ]
        from_alias = table.alias()
        to_alias = table.alias()
        fold_scope_location = Location(("Animal",)).navigate_to_fold("out_Animal_ParentOf")

        builder = emit_sql.FoldSubqueryBuilder(dialect, from_alias, "uuid")
        builder.add_traversal(join_descriptor, from_alias, to_alias)
        builder.mark_output_location_and_fields(to_alias, fold_scope_location, {"name"})
        subquery, output_location = builder.end_fold()

        expected_mssql = """
            SELECT
                [Animal_1].uuid,
                coalesce((
                    SELECT '|' + coalesce(
                        REPLACE(
                            REPLACE(
                                REPLACE([Animal_2].name, '^', '^e'), '~', '^n'
                            ), '|', '^d'
                        ), '~'
                    )
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
                WHERE
                    [Animal_1].uuid = [Animal_2].parent
                FOR XML PATH ('')
                ), '') AS fold_output_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
        """
        string_result = print_sqlalchemy_query_string(subquery, dialect)
        compare_sql(self, expected_mssql, string_result)

        self.assertEqual({"uuid", "fold_output_name"}, set(subquery.c.keys()))
        self.assertEqual(fold_scope_location, output_location)
