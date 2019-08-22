# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import deepcopy

from graphql.language.ast import Argument, Directive, Field, Name, StringValue, ListValue

from graphql_compiler.ast_manipulation import get_only_query_definition, get_only_selection_from_ast
from graphql_compiler.exceptions import GraphQLCompilationError
from graphql_compiler.schema import FilterDirective


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

def _get_filter_operation(filter_directive):
    """Return the @filter's op_name as a string."""
    return filter_directive.arguments[0].value.value


def _get_nodes_for_pagination(statistics, query_ast):
    """Return a list of nodes usable for pagination belonging to the given AST node."""
    definition_ast = get_only_query_definition(query_ast, GraphQLCompilationError)
    root_node = get_only_selection_from_ast(definition_ast, GraphQLCompilationError)

    # TODO(vlad): Return a better selection of nodes for pagination, as paginating over the root
    #             node doesn't create good pages in practice.
    return [root_node]


def _search_for_field(pagination_ast, property_field):
    """Return the property field with the given name if it exists, and None otherwise."""
    selections_list = pagination_ast.selection_set.selections
    for selection in selections_list:
        if selection.name.value == property_field:
            return selection

    return None


def _create_field(field_name):
    """Return a property field with the given name."""
    property_field = Field(
        alias=None, name=Name(value=field_name),
        arguments=[], directives=[], selection_set=None,
    )

    return property_field


def _get_or_create_primary_key_field(schema_graph, pagination_ast):
    """Return the primary key field for a given AST node, creating the property field if needed."""
    # HACK(vlad): Currently, information about the primary key is not stored in the Schema Graph, so
    #             the primary key is assumed to be 'uuid'.
    primary_key_field_name = 'uuid'

    primary_key_field = _search_for_field(pagination_ast, primary_key_field_name)
    if primary_key_field is None:
        primary_key_field = _create_field(primary_key_field_name)

        # We make sure to prepend the primary key field,
        # to avoid inserting a property field after a vertex field.
        selections_list = pagination_ast.selection_set.selections
        selections_list.insert(0, primary_key_field)

    return primary_key_field


def _create_binary_filter_directive(filter_operation, filter_parameter):
    """Create a FilterDirective with the given binary filter and argument name."""
    binary_inequality_filters = ['>', '<', '>=', '<=']
    if filter_operation not in binary_inequality_filters:
        raise AssertionError(u'Could not create a filter for pagination with op_name as {}.'
                             u' Currently, only {} are supported.'
                             .format(filter_operation, binary_inequality_filters))

    filter_ast = Directive(
        name=Name(value=FilterDirective.name),
        arguments=[
            Argument(
                name=Name(value='op_name'),
                value=StringValue(value=filter_operation),
            ),
            Argument(
                name=Name(value='value'),
                value=ListValue(
                    values=[
                        StringValue(value=u'$' + filter_parameter),
                    ],
                ),
            ),
        ],
    )

    return filter_ast


def _create_filter_for_next_page_query(vertex_name, property_field_name, parameters):
    """TODO Adds filters for pagination to the given vertex."""
    paged_upper_param = RESERVED_PARAMETER_PREFIX + 'upper_param_on_{}_{}'.format(
        vertex_name, property_field_name
    )

    filter_directive = _create_binary_filter_directive('<', paged_upper_param)
    return filter_directive


def _create_filter_for_remainder_query(vertex_name, property_field_name, parameters):
    """TODO"""
    paged_lower_param = RESERVED_PARAMETER_PREFIX + 'lower_param_on_{}_{}'.format(
        vertex_name, property_field_name
    )

    filter_directive = _create_binary_filter_directive('>=', paged_lower_param)
    return filter_directive


def generate_parameterized_queries(schema_graph, statistics, query_ast, parameters):
    """Generate two parameterized queries that can be used to paginate over a given query.

    In order to paginate arbitrary GraphQL queries, additional filters may need to be added to be
    able to limit the number of results in the original query. This function creates two new queries
    with additional filters stored as PaginationFilters with which the query result size can be
    controlled.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, query that is being paginated.
        parameters: dict, list of parameters for the given query.

    Returns:
        ParameterizedPaginationQueries namedtuple
    """
    pagination_vertices = _get_nodes_for_pagination(statistics, query_ast)
    pagination_fields = [
        _get_or_create_primary_key_field(schema_graph, vertex)
        for vertex in pagination_vertices
    ]

    pagination_filters = []
    filter_modifications = []
    for vertex, field in zip(pagination_vertices, pagination_fields):
        vertex_class = vertex.name.value
        property_field_name = field.name.value
        related_filters = []

        next_page_original_filter, next_page_created_filter = None, None
        remainder_original_filter, remainder_created_filter = None, None
        for directive in field.directives:
            if _get_filter_operation(directive) == '<' and next_page_original_filter is None:
                next_page_original_filter, next_page_created_filter = deepcopy(directive), _create_filter_for_next_page_query(
                    vertex_class, property_field_name, parameters
                )
                related_filters.append(deepcopy(next_page_created_filter))
            elif _get_filter_operation(directive) == '>=' and remainder_original_filter is None:
                remainder_original_filter, remainder_created_filter = deepcopy(directive), _create_filter_for_remainder_query(
                    vertex_class, property_field_name, parameters
                )
                related_filters.append(deepcopy(remainder_created_filter))
            else:
                related_filters.append(deepcopy(directive))

        if next_page_created_filter is None:
            next_page_created_filter = _create_filter_for_next_page_query(
                vertex_class, property_field_name, parameters
            )
        if remainder_created_filter is None:
            remainder_created_filter = _create_filter_for_remainder_query(
                vertex_class, property_field_name, parameters
            )

        filter_modifications.append([
            field,
            (next_page_original_filter, next_page_created_filter),
            (remainder_original_filter, remainder_created_filter),
        ])
        pagination_filters.append(PaginationFilter(
            vertex_class, property_field_name, next_page_created_filter,
            remainder_created_filter, related_filters
        ))


    for modification in filter_modifications:
        if modification[1][0] is None:
            modification[0].directives.append(modification[1][1])
        else:
            modification[0].directives[modification[0].directives.index(modification[1][0])] = modification[1][1]

    parameterized_next_page_query_ast = deepcopy(query_ast)

    for modification in filter_modifications:
        if modification[1][0] is None:
            del modification[0].directives[modification[0].directives.index(modification[1][1])]
        else:
            modification[0].directives[modification[0].directives.index(modification[1][1])] = modification[1][0]

    for modification in filter_modifications:
        if modification[2][0] is None:
            modification[0].directives.append(modification[2][1])
        else:
            modification[0].directives[modification[0].directives.index(modification[2][0])] = modification[2][1]

    parameterized_remainder_query_ast = deepcopy(query_ast)

    for modification in filter_modifications:
        if modification[2][0] is None:
            del modification[0].directives[modification[0].directives.index(modification[2][1])]
        else:
            modification[0].directives[modification[0].directives.index(modification[2][1])] = modification[2][0]

    parameterized_queries = ParameterizedPaginationQueries(
        parameterized_next_page_query_ast, parameterized_remainder_query_ast, pagination_filters,
        parameters
    )
    return parameterized_queries
