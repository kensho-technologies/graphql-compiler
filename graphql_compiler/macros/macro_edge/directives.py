# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict

from graphql import (
    DirectiveLocation, GraphQLArgument, GraphQLDirective, GraphQLNonNull, GraphQLString
)

from ...schema import FilterDirective, OptionalDirective, RecurseDirective, TagDirective


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

# Directives reserved for macro edges
MACRO_EDGE_DIRECTIVES = (
    MacroEdgeDirective,
    MacroEdgeDefinitionDirective,
    MacroEdgeTargetDirective,
)

# Directives required present in a macro edge definition
DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION = frozenset({
    MacroEdgeDefinitionDirective,
    MacroEdgeTargetDirective
})

# Directives (excluding MACRO_EDGE_DIRECTIVES) tolerated without restrictions within a macro
# edge definition
DIRECTIVES_OPTIONAL_IN_MACRO_EDGE_DEFINITION = frozenset({
    FilterDirective,
    TagDirective,
    OptionalDirective,
    RecurseDirective,
})
