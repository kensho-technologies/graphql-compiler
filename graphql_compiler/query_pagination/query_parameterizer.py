# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy
from typing import Sequence

from graphql.language.ast import (
    ArgumentNode,
    DirectiveNode,
    DocumentNode,
    FieldNode,
    InlineFragmentNode,
    ListValueNode,
    NameNode,
    OperationDefinitionNode,
    SelectionSetNode,
    StringValueNode,
)

from ..ast_manipulation import get_ast_field_name, get_only_query_definition
from ..exceptions import GraphQLError


def _generate_new_name(base_name: str, taken_names: Sequence[str]) -> str:
    """Return a name based on the provided string that is not already taken.
    This method tries the following names:
    {base_name}_0, then {base_name}_1, etc.
    and returns the first one that's not in taken_names
    """
    index = 0
    while "{}_{}".format(base_name, index) in taken_names:
        index += 1
    return "{}_{}".format(base_name, index)


def _add_pagination_filters(query_ast, query_path, pagination_field, directive_to_add):
    if not isinstance(query_ast, (FieldNode, InlineFragmentNode, OperationDefinitionNode)):
        raise AssertionError(
            u'Input AST is of type "{}", which should not be a selection.'
            u"".format(type(query_ast).__name__)
        )

    removed_argument = None
    new_selections = []
    if len(query_path) == 0:
        found_field = False
        for selection_ast in query_ast.selection_set.selections:
            new_selection_ast = selection_ast
            field_name = get_ast_field_name(selection_ast)
            if field_name == pagination_field:
                found_field = True
                new_selection_ast = copy(selection_ast)
                new_selection_ast.directives = copy(selection_ast.directives)
                found_directive = False

                new_directives = []
                for directive in selection_ast.directives:
                    if (directive.arguments[0].value.value == directive_to_add.arguments[0].value.value):
                        removed_argument = directive.arguments[1].value.values[0].value[1:]
                    else:
                        new_directives.append(directive)
                new_directives.append(directive_to_add)
                new_selection_ast.directives = new_directives
            new_selections.append(new_selection_ast)
        if not found_field:
            new_selections.insert(
                0, FieldNode(name=NameNode(value=pagination_field), directives=[directive_to_add])
            )
    else:
        if query_ast.selection_set is None:
            raise AssertionError()

        found_field = False
        new_selections = []
        for selection_ast in query_ast.selection_set.selections:
            new_selection_ast = selection_ast
            field_name = get_ast_field_name(selection_ast)
            if field_name == query_path[0]:
                found_field = True
                new_selection_ast, sub_removed_argument = _add_pagination_filters(
                    selection_ast, query_path[1:], pagination_field, directive_to_add
                )
                if sub_removed_argument is not None:
                    removed_argument = sub_removed_argument
            new_selections.append(new_selection_ast)

        if not found_field:
            raise AssertionError()

    new_ast = copy(query_ast)
    new_ast.selection_set = SelectionSetNode(selections=new_selections)
    return new_ast, removed_argument


def _make_directive(op_name, param_name):
    return DirectiveNode(
        name=NameNode(value="filter"),
        arguments=[
            ArgumentNode(name=NameNode(value="op_name"), value=StringValueNode(value=op_name),),
            ArgumentNode(
                name=NameNode(value="value"),
                value=ListValueNode(values=[StringValueNode(value="$" + param_name)]),
            ),
        ],
    )


def generate_parameterized_queries(schema_info, query_ast, parameters, vertex_partition):
    """Generate two parameterized queries that can be used to paginate over a given query.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_ast: Document, query that is being paginated.
        parameters: dict, list of parameters for the given query.
        vertex_partition: pagination plan

    Returns:
        next_page_ast: Ast for the first page. Includes an additional filter.
        next_page_removed_params: ???
        remainder_ast: Ast for the remainder query. Includes an additional filter.
        remainder_removed_params: ???
        param_name: The parameter name used in the new filters.
    """
    query_type = get_only_query_definition(query_ast, GraphQLError)

    param_name = _generate_new_name("__paged_param", parameters.keys())
    next_page_root, next_page_removed_param_name = _add_pagination_filters(
        query_type,
        vertex_partition.query_path,
        vertex_partition.pagination_field,
        _make_directive("<", param_name),
    )
    remainder_root, remainder_removed_param_name = _add_pagination_filters(
        query_type,
        vertex_partition.query_path,
        vertex_partition.pagination_field,
        _make_directive(">=", param_name),
    )

    # TODO do something with the removed params. Let the caller know to remove them
    #      from the parameter list, and validate that parameters inserted are more
    #      selective than the pre-existing values.

    next_page_ast = DocumentNode(definitions=[next_page_root])
    remainder_ast = DocumentNode(definitions=[remainder_root])
    return next_page_ast, remainder_ast, param_name
