# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict

from graphql import (
    DirectiveLocation, GraphQLArgument, GraphQLDirective, GraphQLNonNull, GraphQLString
)

from ...schema import (
    FilterDirective, FoldDirective, OptionalDirective, RecurseDirective, TagDirective
)


MacroEdgeDirective = GraphQLDirective(
    name='macro_edge',
    locations=[
        # Used to mark edges that are defined via macros in the schema.
        DirectiveLocation.FIELD_DEFINITION,
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

# Directives allowed within a macro edge definition
DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION = frozenset({
    FoldDirective,
    FilterDirective,
    OptionalDirective,
    TagDirective,
    RecurseDirective,
}.union(DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION))
