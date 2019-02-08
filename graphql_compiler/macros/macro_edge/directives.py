# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict

from graphql import (
    DirectiveLocation, GraphQLArgument, GraphQLDirective, GraphQLNonNull, GraphQLString
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
