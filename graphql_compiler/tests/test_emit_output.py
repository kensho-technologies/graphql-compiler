# Copyright 2017-present Kensho Technologies, LLC.
import unittest

from graphql import GraphQLString

from ..compiler import emit_gremlin, emit_match
from ..compiler.blocks import (
    Backtrack, ConstructResult, Filter, GlobalOperationsStart, MarkLocation, QueryRoot, Traverse
)
from ..compiler.expressions import (
    BinaryComposition, ContextField, LocalField, NullLiteral, OutputContextField,
    TernaryConditional, Variable
)
from ..compiler.helpers import Location
from ..compiler.ir_lowering_common.common import OutputContextVertex
from ..compiler.ir_lowering_match.utils import CompoundMatchQuery
from ..compiler.match_query import convert_to_match_query
from ..schema import GraphQLDateTime
from .test_helpers import compare_gremlin, compare_match


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
            ConstructResult({
                'foo_name': OutputContextField(base_name_location, GraphQLString),
            }),
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
            Filter(BinaryComposition(
                u'=',
                LocalField(u'name', GraphQLString),
                Variable('$desired_name', GraphQLString))),
            MarkLocation(base_location),
            Traverse('out', 'Foo_Bar'),
            MarkLocation(child_location),

            QueryRoot({'Foo'}),
            MarkLocation(base_location),
            ConstructResult({
                'foo_name': OutputContextField(base_name_location, GraphQLString),
            }),
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
                    BinaryComposition(u'>=',
                                      LocalField('event_date', GraphQLDateTime),
                                      Variable('$start', GraphQLDateTime)),
                    BinaryComposition(u'<=',
                                      LocalField('event_date', GraphQLDateTime),
                                      Variable('$end', GraphQLDateTime))
                )
            ),
            MarkLocation(base_location),
            ConstructResult({
                'name': OutputContextField(base_name_location, GraphQLString)
            }),
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
            ConstructResult({
                'event_date': OutputContextField(base_event_date_location, GraphQLDateTime)
            }),
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
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         name @output(out_name: "animal_name")
        #     }
        # }'''
        base_location = Location(('Animal',))
        base_name_location = base_location.navigate_to_field('name')

        ir_blocks = [
            QueryRoot({'Animal'}),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            ConstructResult({
                'animal_name': OutputContextField(base_name_location, GraphQLString),
            })
        ]

        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        received_gremlin = emit_gremlin.emit_code_from_ir(ir_blocks, None)
        compare_gremlin(self, expected_gremlin, received_gremlin)

    def test_simple_traverse_filter_output(self):
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
        base_location = Location(('Animal',))
        base_name_location = base_location.navigate_to_field('name')
        child_location = base_location.navigate_to_subpath('out_Animal_BornAt')

        ir_blocks = [
            QueryRoot({'Animal'}),
            MarkLocation(base_location),
            Traverse('out', 'Animal_BornAt'),
            Filter(BinaryComposition(
                u'=',
                LocalField(u'name', GraphQLString),
                ContextField(base_location.navigate_to_field(u'name'), GraphQLString))),
            MarkLocation(child_location),
            Backtrack(base_location),
            GlobalOperationsStart(),
            ConstructResult({
                'animal_name': OutputContextField(base_name_location, GraphQLString),
            })
        ]

        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_BornAt')
            .filter{it, m -> (it.name == m.Animal___1.name)}
            .as('Animal__out_Animal_BornAt___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        received_gremlin = emit_gremlin.emit_code_from_ir(ir_blocks, None)
        compare_gremlin(self, expected_gremlin, received_gremlin)

    def test_output_inside_optional_traversal(self):
        # corresponds to:
        # graphql_string = '''{
        #     Animal {
        #         out_Animal_BornAt @optional {
        #             name @output(out_name: "bornat_name")
        #         }
        #     }
        # }'''
        base_location = Location(('Animal',))
        revisited_base_location = base_location.revisit()
        child_location = base_location.navigate_to_subpath('out_Animal_BornAt')
        child_name_location = child_location.navigate_to_field('name')

        ir_blocks = [
            QueryRoot({'Animal'}),
            MarkLocation(base_location),
            Traverse('out', 'Animal_BornAt', optional=True),
            MarkLocation(child_location),
            Backtrack(base_location, optional=True),
            MarkLocation(revisited_base_location),
            GlobalOperationsStart(),
            ConstructResult({
                'bornat_name': TernaryConditional(
                    BinaryComposition(
                        u'!=',
                        # HACK(predrag): The type given to OutputContextVertex here is wrong,
                        # but it shouldn't cause any trouble since it has absolutely nothing to do
                        # with the code being tested.
                        OutputContextVertex(child_location, GraphQLString),
                        NullLiteral),
                    OutputContextField(child_name_location, GraphQLString),
                    NullLiteral)
            })
        ]

        expected_gremlin = '''
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
        '''

        received_gremlin = emit_gremlin.emit_code_from_ir(ir_blocks, None)
        compare_gremlin(self, expected_gremlin, received_gremlin)

    def test_datetime_variable_representation(self):
        # corresponds to:
        # graphql_string = '''{
        #     BirthEvent {
        #         name @output(out_name: "name")
        #         event_date @filter(op_name: "between", value: ["$start", "$end"])
        #     }
        # }'''
        base_location = Location(('BirthEvent',))
        base_name_location = base_location.navigate_to_field('name')

        ir_blocks = [
            QueryRoot({'BirthEvent'}),
            MarkLocation(base_location),
            Filter(
                BinaryComposition(
                    u'&&',
                    BinaryComposition(u'>=',
                                      LocalField('event_date', GraphQLDateTime),
                                      Variable('$start', GraphQLDateTime)),
                    BinaryComposition(u'<=',
                                      LocalField('event_date', GraphQLDateTime),
                                      Variable('$end', GraphQLDateTime))
                )
            ),
            GlobalOperationsStart(),
            ConstructResult({
                'name': OutputContextField(base_name_location, GraphQLString)
            }),
        ]

        expected_gremlin = '''
             g.V('@class', 'BirthEvent')
            .as('BirthEvent___1')
            .filter{it, m -> ((it.event_date >= Date.parse("yyyy-MM-dd'T'HH:mm:ssX", $start)) &&
                              (it.event_date <= Date.parse("yyyy-MM-dd'T'HH:mm:ssX", $end)))}
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.BirthEvent___1.name
            ])}
        '''

        received_gremlin = emit_gremlin.emit_code_from_ir(ir_blocks, None)
        compare_gremlin(self, expected_gremlin, received_gremlin)

    def test_datetime_output_representation(self):
        # corresponds to:
        # graphql_string = '''{
        #     BirthEvent {
        #         event_date @output(out_name: "event_date")
        #     }
        # }'''
        base_location = Location(('BirthEvent',))
        base_event_date_location = base_location.navigate_to_field('event_date')

        ir_blocks = [
            QueryRoot({'BirthEvent'}),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            ConstructResult({
                'event_date': OutputContextField(base_event_date_location, GraphQLDateTime)
            })
        ]

        expected_gremlin = '''
            g.V('@class', 'BirthEvent')
            .as('BirthEvent___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                event_date: m.BirthEvent___1.event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
            ])}
        '''

        received_gremlin = emit_gremlin.emit_code_from_ir(ir_blocks, None)
        compare_gremlin(self, expected_gremlin, received_gremlin)
