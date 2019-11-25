# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

from ..global_utils import find_new_name
from ..ast_manipulation import get_only_query_definition, get_ast_field_name
from ..exceptions import GraphQLError

from graphql.language.ast import (
    Argument, Directive, Document, Field, InlineFragment, ListValue, Name, OperationDefinition, SelectionSet,
    StringValue
)


def _add_pagination_filters(query_ast, query_path, pagination_field, lower_page, parameters):
    if not isinstance(query_ast, (Field, InlineFragment, OperationDefinition)):
        raise AssertionError(
            u'Input AST is of type "{}", which should not be a selection.'
            u''.format(type(query_ast).__name__)
        )

    # Decide what directive to add, and what existing directives to removej
    param_name = find_new_name('__paged_param', parameters.keys())
    directive_to_add = Directive(Name('filter'), arguments=[
        Argument(Name('op_name'), StringValue('<' if lower_page else '>=')),
        Argument(Name('value'), ListValue([StringValue('$' + param_name)])),
    ])

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
                for directive in selection_ast.directives:
                    if directive.arguments[0].value.value == directive_to_add.arguments[0].value.value:
                        # TODO assert only one is found
                        # TODO assert only weaker filters are removed
                        found_directive = True
                        param_name = directive.arguments[1].value.values[0].value[1:]
                if not found_directive:
                    new_selection_ast.directives.append(directive_to_add)
            new_selections.append(new_selection_ast)
        if not found_field:
            new_selections.insert(0, Field(Name(pagination_field), directives=[directive_to_add]))
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
                new_selection_ast, param_name = _add_pagination_filters(
                    selection_ast, query_path[1:], pagination_field, lower_page, parameters)
            new_selections.append(new_selection_ast)

        if not found_field:
            raise AssertionError()

    new_ast = copy(query_ast)
    new_ast.selection_set = SelectionSet(new_selections)
    return new_ast, param_name


def generate_parameterized_queries(schema_info, query_ast, parameters, vertex_partition):
    """Generate two parameterized queries that can be used to paginate over a given query.

    In order to paginate arbitrary GraphQL queries, additional filters may need to be added to be
    able to limit the number of results in the original query. This function creates two new queries
    with additional filters stored as PaginationFilters with which the query result size can be
    controlled.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_ast: Document, query that is being paginated.
        parameters: dict, list of parameters for the given query.

    Returns:
        ParameterizedPaginationQueries namedtuple
    """
    query_type = get_only_query_definition(query_ast, GraphQLError)

    next_page_type, next_page_param_name = _add_pagination_filters(
        query_type, vertex_partition.query_path, vertex_partition.pagination_field, True, parameters)
    remainder_type, remainder_param_name = _add_pagination_filters(
        query_type, vertex_partition.query_path, vertex_partition.pagination_field, False, parameters)

    next_page_ast = Document(
        definitions=[next_page_type]
    )
    remainder_ast = Document(
        definitions=[remainder_type]
    )

    return (next_page_ast, next_page_param_name), (remainder_ast, remainder_param_name)
