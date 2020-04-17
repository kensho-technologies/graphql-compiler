# Copyright 2019-present Kensho Technologies, LLC.
"""Read-only helpers for traversing AST objects."""
from graphql import GraphQLList
from graphql.language.ast import FieldNode, InlineFragmentNode, OperationDefinitionNode

from ...ast_manipulation import get_ast_field_name
from ...compiler.helpers import get_field_type_from_schema, get_vertex_field_type
from ...schema import TagDirective
from ..macro_edge.directives import MacroEdgeTargetDirective


def _yield_ast_nodes_with_directives(ast):
    """Yield the AST objects where directives appear, anywhere in the given AST.

    Args:
        ast: GraphQL library AST object, such as a Field, InlineFragment, or OperationDefinition

    Yields:
        Iterable[Tuple[AST object, Directive]], where each tuple describes an AST node together with
        the directive it contains. If an AST node contains multiple directives, the AST node will be
        returned as part of multiple tuples, in no particular order.
    """
    for directive in ast.directives:
        yield (ast, directive)

    if isinstance(ast, (FieldNode, InlineFragmentNode, OperationDefinitionNode)):
        if ast.selection_set is not None:
            for sub_selection_set in ast.selection_set.selections:
                # TODO(predrag): When we make the compiler py3-only, use a "yield from" here.
                for entry in _yield_ast_nodes_with_directives(sub_selection_set):
                    yield entry
    else:
        raise AssertionError("Unexpected AST type received: {} {}".format(type(ast), ast))


def _get_type_at_macro_edge_target_using_current_type(schema, ast, current_type):
    """Return the type at the @macro_edge_target or None if there is no target."""
    # Base case
    for directive in ast.directives:
        if directive.name.value == MacroEdgeTargetDirective.name:
            return current_type

    if not isinstance(ast, (FieldNode, InlineFragmentNode, OperationDefinitionNode)):
        raise AssertionError("Unexpected AST type received: {} {}".format(type(ast), ast))

    # Recurse
    if ast.selection_set is not None:
        for selection in ast.selection_set.selections:
            type_in_selection = None
            if isinstance(selection, FieldNode):
                if selection.selection_set is not None:
                    type_in_selection = get_vertex_field_type(current_type, selection.name.value)
            elif isinstance(selection, InlineFragmentNode):
                type_in_selection = schema.get_type(selection.type_condition.name.value)
            else:
                raise AssertionError(
                    "Unexpected selection type received: {} {}".format(type(selection), selection)
                )

            if type_in_selection is not None:
                type_at_target = _get_type_at_macro_edge_target_using_current_type(
                    schema, selection, type_in_selection
                )
                if type_at_target is not None:
                    return type_at_target

    return None  # Didn't find target


# ############
# Public API #
# ############


def get_directives_for_ast(ast):
    """Return a dict of directive name -> list of (ast, directive) where that directive is used.

    Args:
        ast: GraphQL library AST object, such as a Field, InlineFragment, or OperationDefinition

    Returns:
        Dict[str, List[Tuple[AST object, Directive]]], allowing the user to find the instances
        in this AST object where a directive with a given name appears; for each of those instances,
        we record and return the AST object where the directive was applied, together with the AST
        Directive object describing it together with any arguments that might have been supplied.
    """
    result = {}

    for ast, directive in _yield_ast_nodes_with_directives(ast):
        directive_name = directive.name.value
        result.setdefault(directive_name, []).append((ast, directive))

    return result


def get_all_tag_names(ast):
    """Return a set of strings containing tag names that appear in the query.

    Args:
        ast: GraphQL query AST object

    Returns:
        set of strings containing tag names that appear in the query
    """
    return {
        # Schema validation has ensured this exists
        directive.arguments[0].value.value
        for ast, directive in _yield_ast_nodes_with_directives(ast)
        if directive.name.value == TagDirective.name
    }


def get_type_at_macro_edge_target(schema, ast):
    """Return the GraphQL type at the @macro_edge_target or None if there is no target."""
    root_type = get_ast_field_name(ast)
    root_schema_type = get_field_type_from_schema(schema.query_type, root_type)

    # Allow list types at the query root in the schema.
    if isinstance(root_schema_type, GraphQLList):
        root_schema_type = root_schema_type.of_type

    return _get_type_at_macro_edge_target_using_current_type(schema, ast, root_schema_type)
