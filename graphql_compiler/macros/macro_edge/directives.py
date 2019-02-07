from graphql import DirectiveLocation, GraphQLDirective


MacroEdgeDirective = GraphQLDirective(
    name='macro_edge',
    locations=[
        DirectiveLocation.FIELD,
    ]
)


MacroEdgeDefinitionDirective = GraphQLDirective(
    name='macro_edge_definition',
    locations=[
        DirectiveLocation.FIELD,
    ]
)


MacroEdgeTargetDirective = GraphQLDirective(
    name='macro_edge_target',
    locations=[
        DirectiveLocation.FIELD,
        DirectiveLocation.INLINE_FRAGMENT,
    ]
)


MACRO_EDGE_DIRECTIVES = (
    MacroEdgeDirective,
    MacroEdgeDefinitionDirective,
    MacroEdgeTargetDirective,
)
