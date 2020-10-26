# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from ...schema import is_vertex_field_name
from .ast_rewriting import remove_directives_from_ast
from .directives import MacroEdgeDefinitionDirective


MacroEdgeDescriptor = namedtuple(
    "MacroEdgeDescriptor",
    (
        "base_class_name",  # str, name of GraphQL type where the macro edge is defined.
        # The macro edge exists at this type and all of its subtypes.
        "target_class_name",  # str, the name of the GraphQL type that the macro edge points to.
        "macro_edge_name",  # str, name of the vertex field corresponding to this macro edge.
        # Should start with "out_" or "in_", per GraphQL compiler convention.
        "expansion_ast",  # GraphQL AST object defining how the macro edge
        # should be expanded starting from its base type. The
        # selections must be merged (on both endpoints of the
        # macro edge) with the user-supplied GraphQL input.
        "macro_args",  # Dict[str, Any] containing any arguments required by the macro
    ),
)


def create_descriptor_from_ast_and_args(
    class_name, target_class_name, macro_edge_name, macro_definition_ast, macro_edge_args
):
    """Remove macro edge definition directive, and return a MacroEdgeDescriptor."""
    if not is_vertex_field_name(macro_edge_name):
        raise AssertionError("Received illegal macro edge name: {}".format(macro_edge_name))

    directives_to_remove = {MacroEdgeDefinitionDirective.name}
    new_ast = remove_directives_from_ast(macro_definition_ast, directives_to_remove)
    return MacroEdgeDescriptor(
        class_name, target_class_name, macro_edge_name, new_ast, macro_edge_args
    )
