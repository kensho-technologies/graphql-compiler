# Copyright 2017-present Kensho Technologies, LLC.
import unittest

from graphql import GraphQLString

from ..compiler import emit_gremlin, emit_match
from ..compiler.blocks import (Backtrack, ConstructResult, Filter, GlobalOperationsStart,
                               MarkLocation, QueryRoot, Traverse)
from ..compiler.expressions import (BinaryComposition, ContextField, LocalField, NullLiteral,
                                    OutputContextField, TernaryConditional, Variable)
from ..compiler.helpers import Location
from ..compiler.ir_lowering_common import OutputContextVertex
from ..compiler.ir_lowering_match.utils import CompoundMatchQuery, construct_where_filter_predicate
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

        received_match = emit_match.emit_code_from_ir(compound_match_query)
        compare_match(self, expected_match, received_match)

    def test_simple_traverse_filter_output(self):
        base_location = Location(('Foo',))
        base_name_location = base_location.navigate_to_field('name')
        child_location = base_location.navigate_to_subpath('out_Foo_Bar')

        ir_blocks = [
            QueryRoot({'Foo'}),
            Filter(BinaryComposition(
                u'=',
                LocalField(u'name'),
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

        received_match = emit_match.emit_code_from_ir(compound_match_query)
        compare_match(self, expected_match, received_match)

    def test_output_inside_optional_traversal(self):
        base_location = Location(('Foo',))

        child_location = base_location.navigate_to_subpath('out_Foo_Bar')
        child_location_name, _ = child_location.get_location_name()

        child_name_location = child_location.navigate_to_field('name')

        simple_optional_root_info = {
            base_location: {'inner_location_name': child_location_name, 'edge_field': 'out_Foo_Bar'}
        }

        ir_blocks = [
            QueryRoot({'Foo'}),
            MarkLocation(base_location),
            Traverse('out', 'Foo_Bar', optional=True),
            MarkLocation(child_location),

            QueryRoot({'Foo'}),
            MarkLocation(base_location),
            GlobalOperationsStart(),
            Filter(construct_where_filter_predicate(simple_optional_root_info)),
            ConstructResult({
                'bar_name': TernaryConditional(
                    BinaryComposition(
                        u'!=',
                        OutputContextVertex(child_location),
                        NullLiteral
                    ),
                    OutputContextField(child_name_location, GraphQLString),
                    NullLiteral)
            }),
        ]
        match_query = convert_to_match_query(ir_blocks)
        compound_match_query = CompoundMatchQuery(match_queries=[match_query])

        expected_match = '''
            SELECT if(
                eval("(Foo__out_Foo_Bar___1 IS NOT null)"),
                Foo__out_Foo_Bar___1.name,
                null
            ) AS `bar_name` FROM (
                MATCH {{
                    class: Foo,
                    as: Foo___1
                }}.out('Foo_Bar') {{
                    optional: true,
                    as: Foo__out_Foo_Bar___1
                }} , {{
                    class: Foo,
                    as: Foo___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Foo___1.out_Foo_Bar IS null)
                    OR
                    (Foo___1.out_Foo_Bar.size() = 0)
                )
                OR
                (Foo__out_Foo_Bar___1 IS NOT null)
            )
        '''

        received_match = emit_match.emit_code_from_ir(compound_match_query)
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
                                      LocalField('event_date'),
                                      Variable('$start', GraphQLDateTime)),
                    BinaryComposition(u'<=',
                                      LocalField('event_date'),
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

        received_match = emit_match.emit_code_from_ir(compound_match_query)
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

        received_match = emit_match.emit_code_from_ir(compound_match_query)
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
            ConstructResult({
                'foo_name': OutputContextField(base_name_location, GraphQLString),
            })
        ]

        expected_gremlin = '''
            g.V('@class', 'Foo')
            .as('Foo___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                foo_name: m.Foo___1.name
            ])}
        '''

        received_match = emit_gremlin.emit_code_from_ir(ir_blocks)
        compare_gremlin(self, expected_gremlin, received_match)

    def test_simple_traverse_filter_output(self):
        base_location = Location(('Foo',))
        base_name_location = base_location.navigate_to_field('name')
        child_location = base_location.navigate_to_subpath('out_Foo_Bar')

        ir_blocks = [
            QueryRoot({'Foo'}),
            MarkLocation(base_location),
            Traverse('out', 'Foo_Bar'),
            Filter(BinaryComposition(
                u'=',
                LocalField(u'name'),
                ContextField(base_location.navigate_to_field(u'name')))),
            MarkLocation(child_location),
            Backtrack(base_location),
            ConstructResult({
                'foo_name': OutputContextField(base_name_location, GraphQLString),
            })
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

        received_match = emit_gremlin.emit_code_from_ir(ir_blocks)
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
            ConstructResult({
                'bar_name': TernaryConditional(
                    BinaryComposition(
                        u'!=',
                        OutputContextVertex(child_location),
                        NullLiteral),
                    OutputContextField(child_name_location, GraphQLString),
                    NullLiteral)
            })
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

        received_match = emit_gremlin.emit_code_from_ir(ir_blocks)
        compare_gremlin(self, expected_gremlin, received_match)

    def test_datetime_output_representation(self):
        base_location = Location(('Event',))
        base_event_date_location = base_location.navigate_to_field('event_date')

        ir_blocks = [
            QueryRoot({'Event'}),
            MarkLocation(base_location),
            ConstructResult({
                'event_date': OutputContextField(base_event_date_location, GraphQLDateTime)
            })
        ]

        expected_gremlin = '''
            g.V('@class', 'Event')
            .as('Event___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                event_date: m.Event___1.event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
            ])}
        '''

        received_match = emit_gremlin.emit_code_from_ir(ir_blocks)
        compare_gremlin(self, expected_gremlin, received_match)
