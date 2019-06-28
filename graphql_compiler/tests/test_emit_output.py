# Copyright 2017-present Kensho Technologies, LLC.
import unittest

from graphql import GraphQLObjectType, GraphQLString

from ..compiler import emit_cypher, emit_gremlin, emit_match
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
from ..schema import GraphQLDateTime
from .test_helpers import compare_cypher, compare_gremlin, compare_match


class EmitMatchTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None

    def test_simple_immediate_output(self):
        base_location = Location(('Foo',))
        base_name_location = base_location.navigate_to_field('name')

        ir_blocks = [
            QueryRoot({'Foo'}),
            MarkLocation(base_location),
            ConstructResult({'foo_name': OutputContextField(base_name_location, GraphQLString)}),
        ]
        match_query = convert_to_match_query(ir_blocks)
        compound_match_query = CompoundMatchQuery(match_queries=[match_query])

        expected_match = '''
            SELECT Foo___1.name AS `foo_name` FROM (
                MATCH {{
                    class: Foo,
                    as: Foo___1
                }}
                RETURN $matches
            )
        '''

        received_match = emit_match.emit_code_from_ir(compound_match_query, None)
        compare_match(self, expected_match, received_match)

    def test_simple_traverse_filter_output(self):
        base_location = Location(('Foo',))
        base_name_location = base_location.navigate_to_field('name')
        child_location = base_location.navigate_to_subpath('out_Foo_Bar')

        ir_blocks = [
            QueryRoot({'Foo'}),
            Filter(
                BinaryComposition(
                    u'=',
                    LocalField(u'name', GraphQLString),
                    Variable('$desired_name', GraphQLString),
                )
            ),
            MarkLocation(base_location),
            Traverse('out', 'Foo_Bar'),
            MarkLocation(child_location),
            QueryRoot({'Foo'}),
            MarkLocation(base_location),
            ConstructResult({'foo_name': OutputContextField(base_name_location, GraphQLString)}),
        ]
        match_query = convert_to_match_query(ir_blocks)
        compound_match_query = CompoundMatchQuery(match_queries=[match_query])

        expected_match = '''
            SELECT Foo___1.name AS `foo_name` FROM (
                MATCH {{
                    class: Foo,
                    where: ((name = {desired_name})),
                    as: Foo___1
                }}.out('Foo_Bar') {{
                    as: Foo__out_Foo_Bar___1
                }} , {{
                    class: Foo,
                    as: Foo___1
                }}
                RETURN $matches
            )
        '''

        received_match = emit_match.emit_code_from_ir(compound_match_query, None)
        compare_match(self, expected_match, received_match)

    def test_datetime_variable_representation(self):
        base_location = Location(('Event',))
        base_name_location = base_location.navigate_to_field('name')

        ir_blocks = [
            QueryRoot({'Event'}),
            Filter(
                BinaryComposition(
                    u'&&',
                    BinaryComposition(
                        u'>=',
                        LocalField('event_date', GraphQLDateTime),
                        Variable('$start', GraphQLDateTime),
                    ),
                    BinaryComposition(
                        u'<=',
                        LocalField('event_date', GraphQLDateTime),
                        Variable('$end', GraphQLDateTime),
                    ),
                )
            ),
            MarkLocation(base_location),
            ConstructResult({'name': OutputContextField(base_name_location, GraphQLString)}),
        ]
        match_query = convert_to_match_query(ir_blocks)
        compound_match_query = CompoundMatchQuery(match_queries=[match_query])

        expected_match = '''
            SELECT Event___1.name AS `name` FROM (
                MATCH {{
                    class: Event,
                    where: ((
                        (event_date >= date({start}, "yyyy-MM-dd'T'HH:mm:ssX")) AND
                        (event_date <= date({end}, "yyyy-MM-dd'T'HH:mm:ssX"))
                    )),
                    as: Event___1
                }}
                RETURN $matches
            )
        '''

        received_match = emit_match.emit_code_from_ir(compound_match_query, None)
        compare_match(self, expected_match, received_match)

    def test_datetime_output_representation(self):
        base_location = Location(('Event',))
        base_event_date_location = base_location.navigate_to_field('event_date')

        ir_blocks = [
            QueryRoot({'Event'}),
            MarkLocation(base_location),
            ConstructResult(
                {'event_date': OutputContextField(base_event_date_location, GraphQLDateTime)}
            ),
        ]
        match_query = convert_to_match_query(ir_blocks)
        compound_match_query = CompoundMatchQuery(match_queries=[match_query])

        expected_match = '''
            SELECT Event___1.event_date.format("yyyy-MM-dd'T'HH:mm:ssX") AS `event_date` FROM (
                MATCH {{
                    class: Event,
                    as: Event___1
                }}
                RETURN $matches
            )
        '''

        received_match = emit_match.emit_code_from_ir(compound_match_query, None)
        compare_match(self, expected_match, received_match)


class EmitGremlinTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None

    def test_simple_immediate_output(self):
        base_location = Location(('Foo',))
        base_name_location = base_location.navigate_to_field('name')

        ir_blocks = [
            QueryRoot({'Foo'}),
            MarkLocation(base_location),
            ConstructResult({'foo_name': OutputContextField(base_name_location, GraphQLString)}),
        ]

        expected_gremlin = '''
            g.V('@class', 'Foo')
            .as('Foo___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                foo_name: m.Foo___1.name
            ])}
        '''

        received_match = emit_gremlin.emit_code_from_ir(ir_blocks, None)
        compare_gremlin(self, expected_gremlin, received_match)

    def test_simple_traverse_filter_output(self):
        base_location = Location(('Foo',))
        base_name_location = base_location.navigate_to_field('name')
        child_location = base_location.navigate_to_subpath('out_Foo_Bar')

        ir_blocks = [
            QueryRoot({'Foo'}),
            MarkLocation(base_location),
            Traverse('out', 'Foo_Bar'),
            Filter(
                BinaryComposition(
                    u'=',
                    LocalField(u'name', GraphQLString),
                    ContextField(base_location.navigate_to_field(u'name'), GraphQLString),
                )
            ),
            MarkLocation(child_location),
            Backtrack(base_location),
            ConstructResult({'foo_name': OutputContextField(base_name_location, GraphQLString)}),
        ]

        expected_gremlin = '''
            g.V('@class', 'Foo')
            .as('Foo___1')
            .out('Foo_Bar')
            .filter{it, m -> (it.name == m.Foo___1.name)}
            .as('Foo__out_Foo_Bar___1')
            .back('Foo___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                foo_name: m.Foo___1.name
            ])}
        '''

        received_match = emit_gremlin.emit_code_from_ir(ir_blocks, None)
        compare_gremlin(self, expected_gremlin, received_match)

    def test_output_inside_optional_traversal(self):
        base_location = Location(('Foo',))
        revisited_base_location = base_location.revisit()
        child_location = base_location.navigate_to_subpath('out_Foo_Bar')
        child_name_location = child_location.navigate_to_field('name')

        ir_blocks = [
            QueryRoot({'Foo'}),
            MarkLocation(base_location),
            Traverse('out', 'Foo_Bar', optional=True),
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            MarkLocation(revisited_base_location),
            ConstructResult(
                {
                    'bar_name': TernaryConditional(
                        BinaryComposition(
                            u'!=',
                            # HACK(predrag): The type given to OutputContextVertex here is wrong,
                            # but it shouldn't cause any trouble since it has absolutely nothing to do
                            # with the code being tested.
                            OutputContextVertex(child_location, GraphQLString),
                            NullLiteral,
                        ),
                        OutputContextField(child_name_location, GraphQLString),
                        NullLiteral,
                    )
                }
            ),
        ]

        expected_gremlin = '''
            g.V('@class', 'Foo')
            .as('Foo___1')
            .ifThenElse{it.out_Foo_Bar == null}{null}{it.out('Foo_Bar')}
            .as('Foo__out_Foo_Bar___1')
            .optional('Foo___1')
            .as('Foo___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                bar_name: ((m.Foo__out_Foo_Bar___1 != null) ? m.Foo__out_Foo_Bar___1.name : null)
            ])}
        '''

        received_match = emit_gremlin.emit_code_from_ir(ir_blocks, None)
        compare_gremlin(self, expected_gremlin, received_match)

    def test_datetime_output_representation(self):
        base_location = Location(('Event',))
        base_event_date_location = base_location.navigate_to_field('event_date')

        ir_blocks = [
            QueryRoot({'Event'}),
            MarkLocation(base_location),
            ConstructResult(
                {'event_date': OutputContextField(base_event_date_location, GraphQLDateTime)}
            ),
        ]

        expected_gremlin = '''
            g.V('@class', 'Event')
            .as('Event___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                event_date: m.Event___1.event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
            ])}
        '''

        received_match = emit_gremlin.emit_code_from_ir(ir_blocks, None)
        compare_gremlin(self, expected_gremlin, received_match)


class EmitCypherTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None

    def test_simple_immediate_output(self):
        # corresponds to:
        # graphql_string = '''{
        #     Foo {
        #         name @output(out_name: "foo_name")
        #     }
        # }'''

        base_location = Location(("Foo",))
        base_name_location = base_location.navigate_to_field("name")
        base_location_info = LocationInfo(
            parent_location=None,
            type=GraphQLObjectType(name="Foo", fields={'name': GraphQLString}),
            coerced_from_type=None,
            optional_scopes_depth=0,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        ir_blocks = [
            QueryRoot({"Foo"}),
            MarkLocation(base_location),
            GlobalOperationsStart(),  # this block is necessary for Cypher. Indicates filter/output blocks after this.
            ConstructResult({"foo_name": OutputContextField(base_name_location, GraphQLString)}),
        ]
        query_metadata_table = QueryMetadataTable(
            root_location=base_location, root_location_info=base_location_info
        )

        cypher_query = convert_to_cypher_query(ir_blocks, query_metadata_table)
        received_cypher = emit_cypher.emit_code_from_ir(cypher_query, None)

        expected_cypher = """
            CYPHER 3.5
            MATCH (Foo___1:Foo)
            RETURN Foo___1.name AS `foo_name`
        """

        compare_cypher(self, expected_cypher, received_cypher)

    def test_simple_traverse_filter_output(self):
        # corresponds to:
        # graphql_string = '''{
        #     Foo {
        #         name @tag(tag_name: "name")
        #              @output(out_name: "foo_name")
        #         out_Foo_Bar {
        #             name @filter(op_name: "=", value: ["%name"])
        #         }
        #     }
        # }'''

        base_location = Location(("Foo",))
        base_name_location = base_location.navigate_to_field("name")
        base_location_info = LocationInfo(
            parent_location=None,
            type=GraphQLObjectType(name="Foo", fields={'name': GraphQLString}),
            coerced_from_type=None,
            optional_scopes_depth=0,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        child_location = base_location.navigate_to_subpath("out_Foo_Bar")
        child_location_info = LocationInfo(
            parent_location=base_location,
            type=GraphQLObjectType(name="Bar", fields={'name': GraphQLString}),
            coerced_from_type=None,
            optional_scopes_depth=1,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        ir_blocks = [
            QueryRoot({"Foo"}),
            MarkLocation(base_location),
            Traverse("out", "Foo_Bar"),
            CoerceType(
                {'Bar'}
            ),  # see compiler.ir_lowering_cypher's insert_explicit_type_bounds method
            Filter(
                BinaryComposition(
                    u"=",
                    # see compiler.ir_lowering_cypher's replace_local_fields_with_context_fields method
                    # LocalField(u"name", GraphQLString) gets replaced with the child_location field "name"
                    ContextField(child_location.navigate_to_field(u"name"), GraphQLString),
                    ContextField(base_location.navigate_to_field(u"name"), GraphQLString),
                )
            ),
            MarkLocation(child_location),
            Backtrack(base_location),
            GlobalOperationsStart(),
            ConstructResult({"foo_name": OutputContextField(base_name_location, GraphQLString)}),
        ]
        query_metadata_table = QueryMetadataTable(
            root_location=base_location, root_location_info=base_location_info
        )
        query_metadata_table.register_location(child_location, child_location_info)

        cypher_query = convert_to_cypher_query(ir_blocks, query_metadata_table)
        received_cypher = emit_cypher.emit_code_from_ir(cypher_query, None)

        expected_cypher = """
            CYPHER 3.5
            MATCH (Foo___1:Foo)
            MATCH (Foo___1)-[:Foo_Bar]->(Foo__out_Foo_Bar___1:Bar)
              WHERE (Foo__out_Foo_Bar___1.name = Foo___1.name)
            RETURN
              Foo___1.name AS `foo_name`
        """
        compare_cypher(self, expected_cypher, received_cypher)

    def test_output_inside_optional_traversal(self):
        # corresponds to:
        # graphql_string = '''{
        #     Foo {
        #         out_Foo_Bar @optional {
        #             name @output(out_name: "bar_name")
        #         }
        #     }
        # }'''
        base_location = Location(("Foo",))
        revisited_base_location = base_location.revisit()
        base_location_info = LocationInfo(
            parent_location=None,
            type=GraphQLObjectType(name="Foo", fields={'name': GraphQLString}),
            coerced_from_type=None,
            optional_scopes_depth=0,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        child_location = base_location.navigate_to_subpath("out_Foo_Bar")
        child_name_location = child_location.navigate_to_field("name")
        child_location_info = LocationInfo(
            parent_location=base_location,
            type=GraphQLObjectType(name="Bar", fields={'name': GraphQLString}),
            coerced_from_type=None,
            optional_scopes_depth=1,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        ir_blocks = [
            QueryRoot({"Foo"}),
            MarkLocation(base_location),
            Traverse("out", "Foo_Bar", optional=True),
            CoerceType(
                {'Bar'}
            ),  # see compiler.ir_lowering_cypher's insert_explicit_type_bounds method
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            # see compiler.ir_lowering_cypher's remove_mark_location_after_optional_backtrack method
            # MarkLocation(revisited_base_location),
            GlobalOperationsStart(),
            ConstructResult(
                {
                    "bar_name": TernaryConditional(
                        BinaryComposition(
                            u"!=",
                            # HACK(predrag): The type given to OutputContextVertex here is wrong,
                            # but it shouldn't cause any trouble since it has absolutely nothing to do
                            # with the code being tested.
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
        received_cypher = emit_cypher.emit_code_from_ir(cypher_query, None)

        expected_cypher = """
            CYPHER 3.5
            MATCH (Foo___1:Foo)
            OPTIONAL MATCH (Foo___1)-[:Foo_Bar]->(Foo__out_Foo_Bar___1:Bar)
            RETURN
                (CASE WHEN (Foo__out_Foo_Bar___1 IS NOT null) THEN Foo__out_Foo_Bar___1.name ELSE null END) AS `bar_name`
        """

        compare_cypher(self, expected_cypher, received_cypher)

    def test_datetime_output_representation(self):
        # corresponds to:
        # graphql_string = '''{
        #     Event {
        #         event_date @output(out_name: "event_date")
        #     }
        # }'''

        base_location = Location(("Event",))
        base_event_date_location = base_location.navigate_to_field("event_date")
        base_location_info = LocationInfo(
            parent_location=None,
            type=GraphQLObjectType(name="Foo", fields={'name': GraphQLString}),
            coerced_from_type=None,
            optional_scopes_depth=0,
            recursive_scopes_depth=0,
            is_within_fold=False,
        )

        ir_blocks = [
            QueryRoot({"Event"}),
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
        received_cypher = emit_cypher.emit_code_from_ir(cypher_query, None)

        expected_cypher = """
            CYPHER 3.5
            MATCH (Event___1:Event)
            RETURN
            Event___1.event_date AS `event_date`
        """

        compare_cypher(self, expected_cypher, received_cypher)
