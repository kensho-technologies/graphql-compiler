# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict

from graphql import (
    DirectiveLocation, GraphQLArgument, GraphQLDirective, GraphQLNonNull, GraphQLString
)

from ...schema import (
    FilterDirective, OptionalDirective, OutputDirective, OutputSourceDirective, RecurseDirective,
    TagDirective
)


MacroEdgeDirective = GraphQLDirective(
    name='macro_edge',
    locations=[
        DirectiveLocation.FIELD,
    ],
)


MacroEdgeDefinitionDirective = GraphQLDirective(
    name='macro_edge_definition',
    args=OrderedDict([
        ('name', GraphQLArgument(
            type=GraphQLNonNull(GraphQLString),
            description='Name of the filter operation to perform.',
        )),
    ]),
    locations=[
        DirectiveLocation.FIELD,
    ],
)


MacroEdgeTargetDirective = GraphQLDirective(
    name='macro_edge_target',
    locations=[
        DirectiveLocation.FIELD,
        DirectiveLocation.INLINE_FRAGMENT,
    ],
)

MACRO_EDGE_DIRECTIVES = (
    MacroEdgeDirective,
    MacroEdgeDefinitionDirective,
    MacroEdgeTargetDirective,
)

MACRO_EDGE_ALLOWED_SUBDIRECTIVES = frozenset({
    FilterDirective.name,
    TagDirective.name,
    OptionalDirective.name,
    RecurseDirective.name,
    MacroEdgeDefinitionDirective.name,
})

MACRO_EDGE_DISALLOWED_SUBDIRECTIVES = frozenset({
    OutputDirective.name,
    OutputSourceDirective.name,
})

MACRO_EDGE_DEFINITION_DIRECTIVES = frozenset({
    MacroEdgeDefinitionDirective,
    MacroEdgeTargetDirective
})
