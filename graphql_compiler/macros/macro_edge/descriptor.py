# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from .ast_rewriting import remove_directives_from_ast
from .directives import MacroEdgeDefinitionDirective


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
    """Remove macro edge definition directive, and return a MacroEdgeDescriptor."""
    directives_to_remove = {MacroEdgeDefinitionDirective}
    new_ast = remove_directives_from_ast(macro_definition_ast, directives_to_remove)
    return MacroEdgeDescriptor(new_ast, macro_edge_args)
