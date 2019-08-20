# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import deepcopy

from graphql.language.ast import Argument, Directive, Field, ListValue, Name, StringValue

from graphql_compiler.ast_manipulation import get_only_query_definition, get_only_selection_from_ast
from graphql_compiler.exceptions import GraphQLCompilationError


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


def _get_nodes_for_pagination(statistics, query_ast):
    """Return a list of nodes usable for pagination belonging to the given AST node."""
    definition_ast = get_only_query_definition(query_ast, GraphQLCompilationError)
    root_node = get_only_selection_from_ast(definition_ast, GraphQLCompilationError)

    # TODO(vlad): Return a better selection of nodes for paginatino, as paginating over the root
    #             node doesn't create good pages in practice.
    return [root_node]


def _try_obtain_primary_key(pagination_ast, primary_key_field_name):
    """Given an AST node, return the primary key field if it exists, and None otherwise."""
    selections_list = pagination_ast.selection_set.selections
    for selection in selections_list:
        if selection.name.value == primary_key_field_name:
            return selection

    return None


def _create_property_field(field_name):
    """Return a property field with the given name."""
    property_field = Field(
        alias=None, name=Name(value=field_name), arguments=[], directives=[], selection_set=None
    )

    return property_field


def _get_or_create_primary_key_field(schema_graph, pagination_ast):
    """Return the primary key field for a given AST node, creating the property field if needed."""
    # HACK(vlad): Currently, information about the primary key is not stored in the Schema Graph, so
    #             the primary key is assumed to be 'uuid'.
    primary_key_field_name = 'uuid'
    primary_key_field = _try_obtain_primary_key(pagination_ast, primary_key_field_name)
    if primary_key_field is None:
        primary_key_field = _create_property_field(primary_key_field_name)
        # We make sure to prepend the primary key field,
        # to avoid inserting a property field after a vertex field.
        selections_list = pagination_ast.selection_set.selections
        selections_list.insert(0, primary_key_field)

    return primary_key_field


def _get_binary_filter(filter_operation, filter_parameter):
    """TODO Return a """
    binary_filters = ['>', '<', '>=', '<=']
    if filter_operation not in binary_filters:
        raise AssertionError(u'Could not create a filter for pagination with op_name as {}. '
                             u'Currently, only {} are supported.'
                             .format(filter_operation, binary_filters))

    filter_ast = Directive(
        Name('filter'),
        arguments=[
            Argument(Name('op_name'), StringValue(filter_operation)),
            Argument(
                Name('value'),
                ListValue(
                    [
                        StringValue('$' + filter_parameter),
                    ]
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

    if paged_upper_param in parameters.keys():
        raise AssertionError(
            u'Parameter list {} already contains parameter {}, '
            u'which is reserved for pagination.'.format(parameters, paged_upper_param))

    filter_ast = _get_binary_filter('<', paged_upper_param)
    return filter_ast


def _create_filter_for_continuation_query(vertex_name, property_field_name, parameters):
    """TODO"""
    paged_lower_param = RESERVED_PARAMETER_PREFIX + 'lower_param_on_{}_{}'.format(
        vertex_name, property_field_name
    )
    if paged_lower_param in parameters.keys():
        raise AssertionError(
            u'Parameter list {} already contains parameter {}, '
            u'which is reserved for pagination.'.format(parameters, paged_lower_param))

    filter_ast = _get_binary_filter('>=', paged_lower_param)
    return filter_ast


def _generate_next_page_query_ast(schema_graph, query_ast, pagination_vertices, pagination_parameters):
    """TODO Return an AST describing the query that will generate the next page of data.


    Args:
        query_ast: Document
    """
    for pagination_vertex, pagination_parameter in zip(pagination_vertices, pagination_parameters):
        pagination_field = _get_or_create_primary_key_field(schema_graph, pagination_vertex)
        pagination_field.directives = [pagination_parameter.related_filters, pagination_parameter.next_page_query_filter]

    # We generate the next page query by adding all filter_for_next_page_query directives.
    next_page_query_ast = deepcopy(query_ast)

    for pagination_vertex, pagination_parameter in zip(pagination_vertices, pagination_parameters):
        pagination_field = _get_or_create_primary_key_field(schema_graph, pagination_vertex)
        pagination_field.directives = pagination_parameter.related_filters

    return next_page_query_ast


def _generate_continuation_query_ast(schema_graph, query_ast, pagination_vertices, pagination_parameters):
    """TODO Return an AST describing the continuation query.

    Given a list of filters
    Args:
        query_ast: Document, query that is being paginated.
        pagination_vertices: List[Document], vertices where filters for pagination have been added.
        pagination_parameters: List[PaginationFilter], describing which filters to add
                               to paginate over query_ast's result set.

    Returns:
        Document, describing
    """
    for pagination_vertex, pagination_parameter in zip(pagination_vertices, pagination_parameters):
        pagination_field = _get_or_create_primary_key_field(schema_graph, pagination_vertex)
        pagination_field.directives = [pagination_parameter.related_filters, pagination_parameter.continuation_query_filter]

    continuation_query_ast = deepcopy(query_ast)

    for pagination_vertex, pagination_parameter in zip(pagination_vertices, pagination_parameters):
        pagination_field = _get_or_create_primary_key_field(schema_graph, pagination_vertex)
        pagination_field.directives = pagination_parameter.related_filters

    return continuation_query_ast


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

    pagination_parameters = []
    for pagination_vertex in pagination_vertices:
        pagination_field = _get_or_create_primary_key_field(schema_graph, pagination_vertex)
        related_filters = deepcopy([
            directive
            for directive in pagination_field.directives
            if directive.name.value == 'filter'
        ])

        vertex_name = pagination_vertex.name.value
        field_name = pagination_field.name.value
        filter_for_next_page_query = _create_filter_for_next_page_query(
            vertex_name, field_name, parameters
        )
        filter_for_continuation_query = _create_filter_for_continuation_query(
            vertex_name, field_name, parameters
        )

        pagination_parameter = PaginationFilter(
            vertex_name, field_name, filter_for_next_page_query, filter_for_continuation_query,
            related_filters
        )
        pagination_parameters.append(pagination_parameter)

    next_page_query_ast = _generate_next_page_query_ast(
        schema_graph, query_ast, pagination_vertices, pagination_parameters
    )
    continuation_query_ast = _generate_continuation_query_ast(
        schema_graph, query_ast, pagination_vertices, pagination_parameters
    )

    parameterized_queries = ParameterizedPaginationQueries(
        next_page_query_ast, continuation_query_ast, pagination_parameters, parameters
    )
    return parameterized_queries
