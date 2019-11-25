# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

from ..ast_manipulation import get_only_query_definition, get_ast_field_name
from ..exceptions import GraphQLError

from graphql.language.ast import (
    Argument, Directive, Document, Field, InlineFragment, ListValue, Name, OperationDefinition, SelectionSet,
    StringValue
)


RESERVED_PARAMETER_PREFIX = '_paged_'

# ParameterizedPaginationQueries namedtuple, describing two query ASTs that have PaginationFilters
# describing filters with which the query result size can be controlled. Note that these filters are
# returned parameterized i.e. values for the filters' parameters have yet to be generated.
# Additionally, a dict containing user-defined parameters is stored. Since this function may modify
# the user parameters to ensure better pagination, the user_parameters dict may differ from the
# original query's parameters that were provided to the paginator.
ParameterizedPaginationQueries = namedtuple(
    'ParameterizedPaginationQueries',
    (
        'next_page_query',          # Document, AST of query that will return the next page of
                                    # results when combined with pagination parameters.
        'remainder_query',          # Document, AST of query that will return the remainder of
                                    # results when combined with pagination parameters.
        'pagination_filters',       # List[PaginationFilter], filters usable for pagination.
        'user_parameters',          # dict, parameters that the user has defined for other filters.
    ),
)

# PaginationFilter namedtuples document filters usable for pagination purposes within the larger
# context of a ParameterizedPaginationQueries namedtuple. These filters may either be added by the
# query parameterizer, or filters that the user has added whose parameter values may be modified for
# generating paginated queries.
PaginationFilter = namedtuple(
    'PaginationFilter',
    (
        'vertex_class',                 # str, vertex class to which the property field belongs to.
        'property_field',               # str, name of the property field filtering is done over.
        'next_page_query_filter',       # Directive, filter directive with '<' operator usable
                                        # for pagination in the page query.
        'remainder_query_filter',       # Directive, filter directive with '>=' operator usable
                                        # for pagination in the remainder query.
        'related_filters',              # List[Directive], filter directives that share the same
                                        # vertex and property field as the next_page_query_filter,
                                        # and are used to generate more accurate pages.
    ),
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
