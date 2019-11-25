# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

from ..ast_manipulation import get_only_query_definition, get_ast_field_name
from ..exceptions import GraphQLError

from graphql.language.ast import (
    Argument, Directive, Document, Field, InlineFragment, ListValue, Name, OperationDefinition, SelectionSet,
    StringValue
)


def _add_pagination_filters(query_ast, query_path, pagination_field, lower_page):
    if not isinstance(query_ast, (Field, InlineFragment, OperationDefinition)):
        raise AssertionError(
            u'Input AST is of type "{}", which should not be a selection.'
            u''.format(type(query_ast).__name__)
        )

    new_selections = []
    if len(query_path) == 0:
        found_field = False
        for selection_ast in query_ast.selection_set.selections:
            new_selection_ast = selection_ast
            field_name = get_ast_field_name(selection_ast)
            if field_name == pagination_field:
                found_field = True
                raise NotImplementedError(u'At field')
            new_selections.append(new_selection_ast)
        if not found_field:
            new_selections.insert(0, Field(Name(pagination_field), directives=[
                Directive(Name('filter'), arguments=[
                    Argument(Name('op_name'), StringValue('<' if lower_page else '>=')),
                    Argument(Name('value'), ListValue([StringValue('$__paged_param')])),
                ])
            ]))
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
                new_selection_ast = _add_pagination_filters(
                    selection_ast, query_path[1:], pagination_field, lower_page)
            new_selections.append(new_selection_ast)

        if not found_field:
            raise AssertionError()

    new_ast = copy(query_ast)
    new_ast.selection_set = SelectionSet(new_selections)
    return new_ast


def generate_parameterized_queries(schema_info, query_ast, query_path):
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
    pagination_field = 'uuid'  # XXX not
    next_page_type = _add_pagination_filters(query_type, query_path, pagination_field, True)
    remainder_type = _add_pagination_filters(query_type, query_path, pagination_field, False)

    next_page_ast = Document(
        definitions=[next_page_type]
    )
    remainder_ast = Document(
        definitions=[remainder_type]
    )

    return next_page_ast, remainder_ast
