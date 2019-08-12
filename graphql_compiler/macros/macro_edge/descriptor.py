# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from .ast_rewriting import remove_directives_from_ast
from .directives import MACRO_EDGE_DIRECTIVES, MacroEdgeTargetDirective


MacroEdgeDescriptor = namedtuple(
    'MacroEdgeDescriptor', (
        'expansion_ast',  # GraphQL AST object defining how the macro edge
                          # should be expanded starting from its base type. The
                          # selections must be merged (on both endpoints of the
                          # macro edge) with the user-supplied GraphQL input.
        'macro_args',     # Dict[str, Any] containing any arguments required by the macro
    )
)


def create_descriptor_from_ast_and_args(macro_definition_ast, macro_edge_args):
    """Remove all macro edge directives except for the target, and return a MacroEdgeDescriptor."""
    directives_to_remove = {
        directive.name
        for directive in MACRO_EDGE_DIRECTIVES
        if directive.name != MacroEdgeTargetDirective.name
    }
    new_ast = remove_directives_from_ast(macro_definition_ast, directives_to_remove)

    return MacroEdgeDescriptor(new_ast, macro_edge_args)
