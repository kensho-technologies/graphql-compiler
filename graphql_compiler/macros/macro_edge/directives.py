# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict
from copy import copy
from itertools import chain

from graphql import (
    DirectiveLocation, GraphQLArgument, GraphQLDirective, GraphQLNonNull, GraphQLString
)

from ...schema import (
    FilterDirective, FoldDirective, OptionalDirective, RecurseDirective, TagDirective,
    check_for_nondefault_directive_names
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
            type_=GraphQLNonNull(GraphQLString),
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

# Names of directives required present in a macro edge definition
DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION = frozenset({
    MacroEdgeDefinitionDirective.name,
    MacroEdgeTargetDirective.name
})

# Names of directives allowed within a macro edge definition
DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION = frozenset({
    FoldDirective.name,
    FilterDirective.name,
    OptionalDirective.name,
    TagDirective.name,
    RecurseDirective.name,
}.union(DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION))


def get_schema_for_macro_edge_definitions(querying_schema):
    """Given a schema object used for querying, create a schema used for macro edge definitions."""
    original_directives = querying_schema.to_kwargs()['directives']
    check_for_nondefault_directive_names(original_directives)

    directives_required_in_macro_edge_definition = [
        MacroEdgeDefinitionDirective,
        MacroEdgeTargetDirective
    ]

    new_directives = [
        directive
        for directive in chain(original_directives, directives_required_in_macro_edge_definition)
        if directive.name in DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION
    ]

    # Unfortunately, GraphQLSchema objects do not easily allow creating derived schemas,
    # since the GraphQLSchema constructor takes a "types" parameter whose value is not preserved
    # in any of the constructed object's fields. To work around this, we rely on copying and
    # altering the object's internals directly.
    macro_edge_schema = copy(querying_schema)
    # pylint: disable=protected-access
    macro_edge_schema._directives = new_directives
    # pylint: enable=protected-access

    return macro_edge_schema
