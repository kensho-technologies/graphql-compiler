# Copyright 2019-present Kensho Technologies, LLC.
from itertools import chain

from graphql.type import GraphQLSchema

from ...schema import (
    FilterDirective,
    FoldDirective,
    MacroEdgeDefinitionDirective,
    MacroEdgeDirective,
    MacroEdgeTargetDirective,
    OptionalDirective,
    RecurseDirective,
    TagDirective,
    check_for_nondefault_directive_names,
)


# Directives reserved for macro edges
MACRO_EDGE_DIRECTIVES = (
    MacroEdgeDirective,
    MacroEdgeDefinitionDirective,
    MacroEdgeTargetDirective,
)

# Names of directives required present in a macro edge definition
DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION = frozenset(
    {MacroEdgeDefinitionDirective.name, MacroEdgeTargetDirective.name}
)

# Names of directives allowed within a macro edge definition
DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION = frozenset(
    {
        FoldDirective.name,
        FilterDirective.name,
        OptionalDirective.name,
        TagDirective.name,
        RecurseDirective.name,
    }.union(DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION)
)


def get_schema_for_macro_edge_definitions(querying_schema):
    """Given a schema object used for querying, create a schema used for macro edge definitions."""
    original_directives = querying_schema.directives
    check_for_nondefault_directive_names(original_directives)

    directives_required_in_macro_edge_definition = [
        MacroEdgeDefinitionDirective,
        MacroEdgeTargetDirective,
    ]

    new_directives = [
        directive
        for directive in chain(original_directives, directives_required_in_macro_edge_definition)
        if directive.name in DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION
    ]

    schema_arguments = querying_schema.to_kwargs()
    schema_arguments["directives"] = new_directives
    macro_edge_schema = GraphQLSchema(**schema_arguments)

    return macro_edge_schema
